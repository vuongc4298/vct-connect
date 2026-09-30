from contextlib import nullcontext
from datetime import datetime, timezone
import logging
import os
import time
from uuid import UUID

from backend.app.config import Settings
from backend.app.fixture import FIXTURE_URL, fixture_result
from backend.app.extraction import extract_1688, extract_taobao, source_platform
from backend.app.queue import AzureQueue
from backend.app.storage import LeaseLost, ResultConflict, Store

log = logging.getLogger(__name__)


def _limits(settings: Settings | None) -> tuple[int, int, int]:
    if settings is None:
        return 5, 300, 300
    return (
        settings.processing_max_attempts,
        settings.processing_lease_seconds,
        settings.azure_lock_renewal_seconds,
    )


def _failure_code(error: Exception) -> str:
    if isinstance(error, LeaseLost):
        return "LEASE_LOST"
    return "PROCESSING_ERROR"


def _compute_claim(claim: dict, compute) -> dict:
    if compute is not None:
        return compute(claim["source_url"])
    if claim["source_url"] == FIXTURE_URL:
        return fixture_result(claim["source_url"])
    adapter = extract_taobao if source_platform(claim["source_url"]) == "TAOBAO" else extract_1688
    return adapter(claim["source_url"], analysis_mode=claim.get("mode") or "ACCOUNT_PUBLIC")


def dispatch_outbox_once(store: Store, queue: AzureQueue, settings: Settings) -> bool:
    claim = store.claim_outbox(settings.outbox_lease_seconds, settings.outbox_max_attempts)
    if claim is None:
        return False
    if claim["outcome"] == "exhausted":
        log.warning("Outbox publication exhausted analysis_id=%s", claim["analysis_id"])
        return True
    try:
        queue.publish(claim["message_id"])
    except Exception:
        final = store.record_outbox_failure(
            claim["analysis_id"],
            claim["lease_token"],
            max_attempts=settings.outbox_max_attempts,
            base_backoff_seconds=settings.outbox_base_backoff_seconds,
            max_backoff_seconds=settings.outbox_max_backoff_seconds,
        )
        log.warning(
            "Outbox publish failed analysis_id=%s outcome=%s",
            claim["analysis_id"],
            "final" if final else "retry",
        )
        return True
    store.mark_outbox_published(claim["analysis_id"], claim["lease_token"])
    return True


def process_local_once(
    store: Store,
    settings: Settings | None = None,
    *,
    compute=None,
) -> bool:
    max_attempts, lease_seconds, _ = _limits(settings)
    local_claim = store.claim_local(lease_seconds)
    if local_claim is None:
        return False
    analysis_id = local_claim["analysis_id"]
    claim = store.claim_processing(analysis_id, lease_seconds, max_attempts)
    if claim["outcome"] in {"busy", "waiting"}:
        store.release_local(analysis_id, local_claim["claim_token"])
        return True
    if claim["outcome"] in {"completed", "final", "unknown"}:
        store.finish_local(analysis_id, local_claim["claim_token"])
        return True
    try:
        payload = _compute_claim(claim, compute)
        store.complete_processing(analysis_id, claim["token"], payload)
        store.finish_local(analysis_id, local_claim["claim_token"])
    except ResultConflict:
        store.record_result_conflict(analysis_id)
        store.finish_local(analysis_id, local_claim["claim_token"])
        log.warning("Local result conflict analysis_id=%s code=RESULT_CONFLICT", analysis_id)
    except Exception as exc:
        code = _failure_code(exc)
        final = store.record_processing_failure(
            analysis_id,
            claim["token"],
            failure_code=code,
            max_attempts=max_attempts,
            retry_delay_seconds=min(2 ** claim["attempt"], 60),
            local_claim_token=local_claim["claim_token"],
        )
        log.warning(
            "Local processing failed analysis_id=%s code=%s outcome=%s",
            analysis_id,
            code,
            "final" if final else "retry",
        )
    return True


def _dead_letter(receiver, message, reason: str, description: str) -> None:
    receiver.dead_letter_message(
        message,
        reason=reason[:64],
        error_description=description[:256],
    )


def _complete_message(receiver, message, analysis_id: UUID) -> None:
    try:
        receiver.complete_message(message)
    except Exception:
        log.error("Azure completion settlement failed analysis_id=%s", analysis_id)
        raise


def _dead_letter_and_confirm(
    store: Store,
    receiver,
    message,
    analysis_id: UUID,
    reason: str,
    description: str,
) -> None:
    try:
        _dead_letter(receiver, message, reason, description)
    except Exception:
        log.error(
            "Azure dead-letter settlement failed analysis_id=%s reason=%s",
            analysis_id,
            reason,
        )
        raise
    try:
        store.mark_dead_lettered(analysis_id)
    except Exception:
        log.error(
            "Azure dead-letter confirmation failed analysis_id=%s reason=%s",
            analysis_id,
            reason,
        )
        raise


def process_azure_once(
    store: Store,
    queue: AzureQueue,
    settings: Settings | None = None,
    *,
    compute=None,
    sleep=time.sleep,
    clock=time.monotonic,
) -> bool:
    max_attempts, lease_seconds, renewal_seconds = _limits(settings)
    with queue.receive() as receiver:
        messages = receiver.receive_messages(max_message_count=1, max_wait_time=5)
        if not messages:
            return False
        message = messages[0]
        try:
            analysis_id = UUID(str(message.message_id))
        except (TypeError, ValueError, AttributeError):
            try:
                _dead_letter(
                    receiver, message, "InvalidMessageId", "MessageId must be an analysis UUID"
                )
            except Exception:
                log.error("Azure dead-letter settlement failed reason=InvalidMessageId")
                raise
            log.warning("Dead-lettered message with invalid MessageId")
            return True

        renewal = (
            queue.renew_lock(receiver, message, renewal_seconds)
            if hasattr(queue, "renew_lock")
            else nullcontext()
        )
        with renewal:
            settle_deadline = clock() + max(1, renewal_seconds - 15)
            store.observe_delivery(analysis_id)
            while True:
                if clock() >= settle_deadline:
                    log.warning("Azure lock renewal budget elapsed analysis_id=%s", analysis_id)
                    return True
                claim = store.claim_processing(analysis_id, lease_seconds, max_attempts)
                if claim["outcome"] == "unknown":
                    if clock() >= settle_deadline:
                        return True
                    try:
                        _dead_letter(
                            receiver, message, "UnknownAnalysis", "No durable analysis exists"
                        )
                    except Exception:
                        log.error(
                            "Azure dead-letter settlement failed analysis_id=%s reason=UnknownAnalysis",
                            analysis_id,
                        )
                        raise
                    log.warning("Dead-lettered unknown analysis_id=%s", analysis_id)
                    return True
                if claim["outcome"] == "completed":
                    if clock() >= settle_deadline:
                        return True
                    _complete_message(receiver, message, analysis_id)
                    return True
                if claim["outcome"] == "final":
                    if clock() >= settle_deadline:
                        return True
                    _dead_letter_and_confirm(
                        store,
                        receiver,
                        message,
                        analysis_id,
                        "AnalysisFailedFinal",
                        "Analysis reached its retry limit",
                    )
                    return True
                if claim["outcome"] in {"busy", "waiting"}:
                    remaining = (
                        claim["available_at"] - datetime.now(timezone.utc)
                    ).total_seconds()
                    budget = settle_deadline - clock()
                    if budget <= 0:
                        return True
                    sleep(min(max(remaining, 1), lease_seconds, budget))
                    continue

                try:
                    payload = _compute_claim(claim, compute)
                    store.complete_processing(analysis_id, claim["token"], payload)
                except ResultConflict:
                    store.record_result_conflict(analysis_id)
                    if clock() >= settle_deadline:
                        return True
                    _dead_letter_and_confirm(
                        store,
                        receiver,
                        message,
                        analysis_id,
                        "RESULT_CONFLICT",
                        "Duplicate result conflicts with the immutable stored result",
                    )
                    log.warning(
                        "Azure result conflict analysis_id=%s code=RESULT_CONFLICT",
                        analysis_id,
                    )
                    return True
                except Exception as exc:
                    code = _failure_code(exc)
                    final = store.record_processing_failure(
                        analysis_id,
                        claim["token"],
                        failure_code=code,
                        max_attempts=max_attempts,
                        retry_delay_seconds=min(2 ** claim["attempt"], 60),
                    )
                    log.warning(
                        "Azure processing failed analysis_id=%s code=%s outcome=%s",
                        analysis_id,
                        code,
                        "final" if final else "retry",
                    )
                    if final:
                        if clock() >= settle_deadline:
                            return True
                        _dead_letter_and_confirm(
                            store,
                            receiver,
                            message,
                            analysis_id,
                            code,
                            "Analysis reached its retry limit",
                        )
                        return True
                    # Keep this Peek-Lock and its renewer alive. The next loop waits
                    # for the durable retry time without consuming a broker delivery.
                    continue

                # Persistence has committed. A settlement failure is replayable:
                # redelivery observes COMPLETED and never recomputes the result.
                if clock() >= settle_deadline:
                    return True
                _complete_message(receiver, message, analysis_id)
                return True


def _run_forever(store: Store, queue: AzureQueue | None, settings: Settings, mode: str) -> None:
    retry_delay = 2
    while True:
        try:
            if mode == "dispatcher":
                did_work = dispatch_outbox_once(store, queue, settings)
            elif queue:
                did_work = dispatch_outbox_once(store, queue, settings)
                did_work = process_azure_once(store, queue, settings) or did_work
            else:
                did_work = process_local_once(store, settings)
            if not did_work:
                time.sleep(1)
            retry_delay = 2
        except Exception:
            log.error("Worker infrastructure operation failed; retrying")
            if queue:
                queue.reconnect()
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("azure").setLevel(logging.WARNING)
    settings = Settings.from_env()
    store = Store(settings.database_url)
    queue = (
        AzureQueue(
            settings.azure_service_bus_connection_string,
            settings.azure_service_bus_queue,
            namespace=settings.azure_service_bus_namespace,
        )
        if settings.queue_transport == "azure" else None
    )
    mode = os.getenv("WORKER_MODE", "combined")
    if mode not in {"combined", "dispatcher", "job"}:
        raise ValueError("WORKER_MODE must be combined, dispatcher, or job")
    if mode != "combined" and queue is None:
        raise ValueError("Dispatcher and Job require Azure queue transport")
    if mode == "job":
        # The scaler may race with another execution. An empty receive still exits.
        process_azure_once(store, queue, settings)
        return
    _run_forever(store, queue, settings, mode)


if __name__ == "__main__":
    main()
