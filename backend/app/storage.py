from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from .extraction.urls import source_platform, normalize_source_url
from .extraction.extension_merge import merge_extension_evidence, reject_sensitive_page_state
from .extraction.renormalize import UnsupportedRawEvidence, renormalize_public_fields


class LeaseLost(RuntimeError):
    pass


class ResultConflict(RuntimeError):
    pass


class AdmissionDenied(RuntimeError):
    pass


class Store:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def connect(self):
        from .migrations import psycopg_url

        parameters = psycopg.conninfo.conninfo_to_dict(psycopg_url(self.database_url))
        options = parameters.get("options", "")
        parameters["options"] = f"{options} -c timezone=UTC".strip()
        return psycopg.connect(**parameters, row_factory=dict_row)

    def initialize(self):
        from .migrations import apply_migrations

        apply_migrations(self.database_url)

    def resolve_user(self, clerk_user_id: str, email: str | None = None) -> dict:
        user_id = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """INSERT INTO users (id, clerk_user_id, email, role)
                       VALUES (%s, %s, %s, 'CUSTOMER')
                       ON CONFLICT (clerk_user_id) DO NOTHING
                       RETURNING id, clerk_user_id, email, role""",
                    (user_id, clerk_user_id, email),
                ).fetchone()
                if row is None:
                    row = conn.execute(
                        """SELECT id, clerk_user_id, email, role
                           FROM users WHERE clerk_user_id = %s""",
                        (clerk_user_id,),
                    ).fetchone()
                if email and row["email"] != email:
                    row = conn.execute(
                        """UPDATE users SET email = %s, updated_at = now()
                           WHERE id = %s RETURNING id, clerk_user_id, email, role""",
                        (email, row["id"]),
                    ).fetchone()
        return row

    def get_account_state(
        self, user_id: UUID, *, customer_limit: int, window_seconds: int,
    ) -> dict | None:
        """Return the signed-in customer's current plan, trial and admission usage."""
        with self.connect() as conn:
            user = conn.execute(
                """SELECT id, clerk_user_id, email, role
                   FROM users WHERE id = %s""",
                (user_id,),
            ).fetchone()
            if user is None:
                return None
            trial = conn.execute(
                """SELECT entitlement, source, starts_at, expires_at, status,
                          (status = 'ACTIVE'
                           AND starts_at <= now()
                           AND (expires_at IS NULL OR expires_at > now())) AS active
                   FROM entitlements
                   WHERE user_id = %s
                     AND entitlement = 'ANALYSIS_ACCESS'
                     AND source = 'MVP_TRIAL'
                   ORDER BY (status = 'ACTIVE'
                             AND starts_at <= now()
                             AND (expires_at IS NULL OR expires_at > now())) DESC,
                            starts_at DESC
                   LIMIT 1""",
                (user_id,),
            ).fetchone()
            usage = conn.execute(
                """WITH current_window AS (
                     SELECT floor(extract(epoch FROM now()) / %s)::bigint AS n
                   )
                   SELECT COALESCE(ac.used, 0)::int AS used,
                          to_timestamp(cw.n * %s) AS starts_at,
                          to_timestamp((cw.n + 1) * %s) AS resets_at
                   FROM current_window cw
                   LEFT JOIN admission_counters ac
                     ON ac.scope = 'CUSTOMER'
                    AND ac.subject = %s
                    AND ac.window_number = cw.n""",
                (window_seconds, window_seconds, window_seconds, str(user_id)),
            ).fetchone()
        used = int(usage["used"])
        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"],
            },
            "plan": "MVP_TRIAL" if trial and trial["active"] else "FREE",
            "trial": {
                "active": bool(trial and trial["active"]),
                "starts_at": trial["starts_at"] if trial else None,
                "expires_at": trial["expires_at"] if trial else None,
                "status": trial["status"] if trial else None,
            },
            "usage": {
                "used": used,
                "limit": customer_limit,
                "remaining": max(customer_limit - used, 0),
                "window_seconds": window_seconds,
                "starts_at": usage["starts_at"],
                "resets_at": usage["resets_at"],
            },
        }

    @staticmethod
    def _event(
        conn,
        analysis_id: UUID,
        status: str,
        attempt: int,
        *,
        failure_code: str | None = None,
        next_retry_at=None,
        disposition: str | None = None,
    ) -> None:
        conn.execute(
            """INSERT INTO analysis_status_events
                 (analysis_id, status, attempt, failure_code, next_retry_at, disposition)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (analysis_id, status, attempt, failure_code, next_retry_at, disposition),
        )

    def _insert_analysis(
        self, conn, analysis_id: UUID, source_url: str, user_id: UUID | None,
        *, guest_key_hash: str | None = None, actor_type: str = "LEGACY",
    ):
        mode = "ACCOUNT_PUBLIC" if user_id is not None else "GUEST_PUBLIC"
        extraction_method = "FIXTURE" if source_url.endswith("/123456789012.html") else "PUBLIC_HTTP"
        conn.execute(
            """INSERT INTO analyses
                 (id, source_url, status, user_id, guest_key_hash, mode,
                  actor_type, extraction_method, scoring_version)
               VALUES (%s, %s, 'QUEUED', %s, %s, %s, %s, %s, 'v0.1.0')""",
            (analysis_id, source_url, user_id, guest_key_hash, mode, actor_type, extraction_method),
        )
        self._event(conn, analysis_id, "QUEUED", 0)

    @staticmethod
    def _admit(conn, scope: str, subject: str, limit: int, window_seconds: int) -> None:
        row = conn.execute(
            """INSERT INTO admission_counters (scope, subject, window_number, used)
               VALUES (%s, %s, floor(extract(epoch FROM now()) / %s)::bigint, 1)
               ON CONFLICT (scope, subject, window_number)
               DO UPDATE SET used = admission_counters.used + 1
                 WHERE admission_counters.used < %s
               RETURNING used""",
            (scope, subject, window_seconds, limit),
        ).fetchone()
        if row is None:
            raise AdmissionDenied("Submission limit reached")

    def _submit(
        self, source_url: str, user_id: UUID | None, *, azure: bool,
        guest_key_hash: str | None = None, actor_type: str = "LEGACY",
        browser_limit: int | None = None, global_limit: int | None = None,
        customer_limit: int | None = None, window_seconds: int = 86400,
    ) -> UUID:
        analysis_id = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                if actor_type == "GUEST":
                    assert guest_key_hash is not None and browser_limit is not None and global_limit is not None
                    self._admit(conn, "GUEST_BROWSER", guest_key_hash, browser_limit, window_seconds)
                    self._admit(conn, "GUEST_GLOBAL", "all", global_limit, window_seconds)
                elif actor_type == "CUSTOMER":
                    assert user_id is not None and customer_limit is not None
                    self._admit(conn, "CUSTOMER", str(user_id), customer_limit, window_seconds)
                self._insert_analysis(
                    conn, analysis_id, source_url, user_id,
                    guest_key_hash=guest_key_hash, actor_type=actor_type,
                )
                if azure:
                    conn.execute(
                        "INSERT INTO analysis_outbox (analysis_id, message_id) VALUES (%s, %s)",
                        (analysis_id, analysis_id),
                    )
                else:
                    conn.execute("INSERT INTO local_queue (analysis_id) VALUES (%s)", (analysis_id,))
        return analysis_id

    def submit_local(self, source_url: str, user_id: UUID | None = None) -> UUID:
        return self._submit(source_url, user_id, azure=False)

    def submit_azure(self, source_url: str, user_id: UUID | None = None) -> UUID:
        """Atomically create customer-visible work and its publication record."""
        return self._submit(source_url, user_id, azure=True)

    def submit_guest(
        self, source_url: str, guest_key: str, *, azure: bool,
        browser_limit: int, global_limit: int, window_seconds: int,
    ) -> UUID:
        return self._submit(
            source_url, None, azure=azure, guest_key_hash=sha256(guest_key.encode()).hexdigest(),
            actor_type="GUEST", browser_limit=browser_limit,
            global_limit=global_limit, window_seconds=window_seconds,
        )

    def submit_customer(
        self, source_url: str, user_id: UUID, *, azure: bool,
        customer_limit: int, window_seconds: int,
    ) -> UUID:
        return self._submit(
            source_url, user_id, azure=azure, actor_type="CUSTOMER",
            customer_limit=customer_limit, window_seconds=window_seconds,
        )

    _SELECT = """
        SELECT a.id, a.source_url, a.status, a.created_at, a.completed_at,
               a.attempt_count, a.failure_code, a.next_retry_at,
               a.final_disposition, a.mode, a.actor_type, a.extraction_method,
               a.scoring_version, r.payload AS result,
               s.id AS supplier_snapshot_id, s.normalized_data AS supplier_data,
               s.raw_payload AS raw_evidence,
               COALESCE((SELECT jsonb_agg(rv.payload ORDER BY rv.ordinal)
                 FROM supplier_reviews rv WHERE rv.snapshot_id = s.id), '[]'::jsonb) AS reviews,
               COALESCE((
                 SELECT jsonb_agg(jsonb_build_object(
                   'status', e.status, 'attempt', e.attempt,
                   'failure_code', e.failure_code, 'next_retry_at', e.next_retry_at,
                   'disposition', e.disposition, 'created_at', e.created_at
                 ) ORDER BY e.id)
                 FROM analysis_status_events e WHERE e.analysis_id = a.id
               ), '[]'::jsonb) AS events
        FROM analyses a LEFT JOIN analysis_results r ON r.analysis_id = a.id
        LEFT JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
    """

    def list_analysis_history(self, user_id: UUID, *, limit: int = 100) -> list[dict]:
        """List one customer's analyses newest-first with compact persisted report state."""
        bounded_limit = max(1, min(limit, 100))
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT a.id, a.source_url, a.status, a.created_at, a.completed_at,
                          a.mode, a.extraction_method, a.scoring_version,
                          COALESCE(r.payload->>'supplier_name',
                                   s.normalized_data->>'supplier_name') AS supplier_name,
                          COALESCE(r.payload->>'platform',
                                   s.normalized_data->>'platform') AS platform,
                          (r.id IS NOT NULL) AS report_available,
                          r.payload->'risk'->>'label' AS risk_label,
                          NULLIF(r.payload->'risk'->>'overall_risk', '')::double precision AS overall_risk,
                          NULLIF(r.payload->'risk'->>'confidence', '')::double precision AS confidence,
                          NULLIF(r.payload->'risk'->>'coverage', '')::double precision AS coverage
                   FROM analyses a
                   LEFT JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
                   LEFT JOIN reports r ON r.analysis_id = a.id
                   WHERE a.user_id = %s AND a.actor_type = 'CUSTOMER'
                   ORDER BY a.created_at DESC, a.id DESC
                   LIMIT %s""",
                (user_id, bounded_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, analysis_id: UUID) -> dict | None:
        with self.connect() as conn:
            return conn.execute(self._SELECT + " WHERE a.id = %s", (analysis_id,)).fetchone()

    def get_for_user(self, analysis_id: UUID, user_id: UUID) -> dict | None:
        with self.connect() as conn:
            return conn.execute(
                self._SELECT + " WHERE a.id = %s AND a.user_id = %s",
                (analysis_id, user_id),
            ).fetchone()

    def get_report_for_user(self, analysis_id: UUID, user_id: UUID) -> dict | None:
        """Return a completed full report only to its owning customer."""
        with self.connect() as conn:
            return conn.execute(
                """SELECT r.payload, r.created_at
                   FROM reports r
                   JOIN analyses a ON a.id = r.analysis_id
                   WHERE a.id = %s AND a.user_id = %s
                     AND a.actor_type = 'CUSTOMER'
                     AND a.status = 'COMPLETED'""",
                (analysis_id, user_id),
            ).fetchone()

    def get_for_guest(self, analysis_id: UUID, guest_key: str) -> dict | None:
        key_hash = sha256(guest_key.encode()).hexdigest()
        with self.connect() as conn:
            return conn.execute(
                self._SELECT + " WHERE a.id = %s AND a.guest_key_hash = %s"
                " AND a.actor_type = 'GUEST'"
                " AND a.created_at >= now() - 2592000 * interval '1 second'",
                (analysis_id, key_hash),
            ).fetchone()

    def list_watchlist(self, user_id: UUID) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT w.id, w.created_at, s.id AS supplier_id, s.platform,
                          s.platform_supplier_id, s.name, s.source_url,
                          latest.analysis_id, latest.status AS analysis_status,
                          latest.report_available, latest.risk_label,
                          latest.overall_risk, latest.confidence, latest.coverage
                   FROM watchlist_entries w
                   JOIN suppliers s ON s.id = w.supplier_id
                   LEFT JOIN LATERAL (
                     SELECT a.id AS analysis_id, a.status,
                            (r.id IS NOT NULL) AS report_available,
                            r.payload->'risk'->>'label' AS risk_label,
                            NULLIF(r.payload->'risk'->>'overall_risk', '')::double precision AS overall_risk,
                            NULLIF(r.payload->'risk'->>'confidence', '')::double precision AS confidence,
                            NULLIF(r.payload->'risk'->>'coverage', '')::double precision AS coverage
                     FROM analyses a
                     JOIN supplier_snapshots ss ON ss.id = a.supplier_snapshot_id
                     LEFT JOIN reports r ON r.analysis_id = a.id
                     WHERE a.user_id = w.user_id
                       AND a.actor_type = 'CUSTOMER'
                       AND ss.supplier_id = w.supplier_id
                     ORDER BY a.created_at DESC, a.id DESC
                     LIMIT 1
                   ) latest ON TRUE
                   WHERE w.user_id = %s
                   ORDER BY w.created_at DESC, w.id DESC""",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_watchlist_from_analysis(self, user_id: UUID, analysis_id: UUID) -> dict | None:
        entry_id = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT s.id AS supplier_id
                       FROM analyses a
                       JOIN supplier_snapshots ss ON ss.id = a.supplier_snapshot_id
                       JOIN suppliers s ON s.id = ss.supplier_id
                       WHERE a.id = %s AND a.user_id = %s
                         AND a.actor_type = 'CUSTOMER'""",
                    (analysis_id, user_id),
                ).fetchone()
                if row is None:
                    return None
                existing = conn.execute(
                    """INSERT INTO watchlist_entries (id, user_id, supplier_id)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, supplier_id) DO UPDATE
                       SET user_id = EXCLUDED.user_id
                       RETURNING id, created_at""",
                    (entry_id, user_id, row["supplier_id"]),
                ).fetchone()
        return {"id": existing["id"], "created_at": existing["created_at"]}

    def remove_watchlist_entry(self, user_id: UUID, entry_id: UUID) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """DELETE FROM watchlist_entries
                   WHERE id = %s AND user_id = %s
                   RETURNING id""",
                (entry_id, user_id),
            ).fetchone()
        return row is not None

    def get_report_for_guest(self, analysis_id: UUID, guest_key: str) -> dict | None:
        """Return a completed report only to the guest browser that created the analysis."""
        key_hash = sha256(guest_key.encode()).hexdigest()
        with self.connect() as conn:
            return conn.execute(
                """SELECT r.payload, r.created_at
                   FROM reports r
                   JOIN analyses a ON a.id = r.analysis_id
                   WHERE a.id = %s AND a.guest_key_hash = %s
                     AND a.actor_type = 'GUEST'
                     AND a.status = 'COMPLETED'
                     AND a.created_at >= now() - 2592000 * interval '1 second'""",
                (analysis_id, key_hash),
            ).fetchone()

    def claim_outbox(self, lease_seconds: int, max_attempts: int) -> dict | None:
        token = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT analysis_id, attempts FROM analysis_outbox
                       WHERE state = 'PENDING' AND next_attempt_at <= now()
                         AND (leased_until IS NULL OR leased_until < now())
                       ORDER BY next_attempt_at, analysis_id
                       FOR UPDATE SKIP LOCKED LIMIT 1"""
                ).fetchone()
                if row is None:
                    return None
                if row["attempts"] >= max_attempts:
                    self._finalize_outbox(conn, row["analysis_id"])
                    return {"outcome": "exhausted", "analysis_id": row["analysis_id"]}
                return conn.execute(
                    """UPDATE analysis_outbox
                       SET lease_token = %s,
                           leased_until = now() + %s * interval '1 second',
                           attempts = attempts + 1, updated_at = now()
                       WHERE analysis_id = %s
                       RETURNING 'claimed' AS outcome, analysis_id, message_id,
                                 attempts, lease_token""",
                    (token, lease_seconds, row["analysis_id"]),
                ).fetchone()

    def mark_outbox_published(self, analysis_id: UUID, token: UUID) -> None:
        with self.connect() as conn:
            row = conn.execute(
                """UPDATE analysis_outbox
                   SET state = 'PUBLISHED', published_at = now(), lease_token = NULL,
                       leased_until = NULL, last_error_code = NULL, updated_at = now()
                   WHERE analysis_id = %s AND lease_token = %s AND state = 'PENDING'
                   RETURNING analysis_id""",
                (analysis_id, token),
            ).fetchone()
            if row is None:
                raise LeaseLost("Outbox lease is no longer current")

    def _finalize_outbox(self, conn, analysis_id: UUID, token: UUID | None = None) -> None:
        condition = "analysis_id = %s AND state = 'PENDING'"
        parameters: tuple = (analysis_id,)
        if token is not None:
            condition += " AND lease_token = %s"
            parameters = (analysis_id, token)
        changed = conn.execute(
            f"""UPDATE analysis_outbox SET state = 'FAILED_FINAL',
                      lease_token = NULL, leased_until = NULL,
                      last_error_code = 'OUTBOX_PUBLISH_EXHAUSTED', updated_at = now()
                   WHERE {condition} RETURNING analysis_id""",
            parameters,
        ).fetchone()
        if changed is None:
            raise LeaseLost("Outbox lease is no longer current")
        analysis = conn.execute(
            """UPDATE analyses
               SET status = 'FAILED_FINAL', failure_code = 'OUTBOX_PUBLISH_EXHAUSTED',
                   final_disposition = 'PUBLICATION_FAILED', next_retry_at = NULL
               WHERE id = %s AND status = 'QUEUED'
               RETURNING attempt_count""",
            (analysis_id,),
        ).fetchone()
        if analysis:
            self._event(
                conn, analysis_id, "FAILED_FINAL", analysis["attempt_count"],
                failure_code="OUTBOX_PUBLISH_EXHAUSTED",
                disposition="PUBLICATION_FAILED",
            )

    def record_outbox_failure(
        self,
        analysis_id: UUID,
        token: UUID,
        *,
        max_attempts: int,
        base_backoff_seconds: int,
        max_backoff_seconds: int,
    ) -> bool:
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT attempts FROM analysis_outbox
                       WHERE analysis_id = %s AND lease_token = %s AND state = 'PENDING'
                       FOR UPDATE""",
                    (analysis_id, token),
                ).fetchone()
                if row is None:
                    raise LeaseLost("Outbox lease is no longer current")
                final = row["attempts"] >= max_attempts
                if final:
                    self._finalize_outbox(conn, analysis_id, token)
                else:
                    delay = min(
                        base_backoff_seconds * (2 ** max(row["attempts"] - 1, 0)),
                        max_backoff_seconds,
                    )
                    conn.execute(
                        """UPDATE analysis_outbox
                           SET lease_token = NULL, leased_until = NULL,
                               next_attempt_at = now() + %s * interval '1 second',
                               last_error_code = 'OUTBOX_PUBLISH_RETRY', updated_at = now()
                           WHERE analysis_id = %s AND lease_token = %s""",
                        (delay, analysis_id, token),
                    )
                return final

    def observe_delivery(self, analysis_id: UUID) -> None:
        """Reconcile an accepted message with any ambiguous publisher outcome."""
        with self.connect() as conn:
            with conn.transaction():
                conn.execute(
                    """UPDATE analysis_outbox
                       SET state = 'PUBLISHED', published_at = COALESCE(published_at, now()),
                           lease_token = NULL, leased_until = NULL,
                           last_error_code = NULL, updated_at = now()
                       WHERE analysis_id = %s""",
                    (analysis_id,),
                )
                reopened = conn.execute(
                    """UPDATE analyses SET status = 'QUEUED', failure_code = NULL,
                              final_disposition = NULL, next_retry_at = NULL
                       WHERE id = %s AND status = 'FAILED_FINAL'
                         AND failure_code = 'OUTBOX_PUBLISH_EXHAUSTED'
                         AND final_disposition = 'PUBLICATION_FAILED'
                       RETURNING attempt_count""",
                    (analysis_id,),
                ).fetchone()
                if reopened:
                    self._event(conn, analysis_id, "QUEUED", reopened["attempt_count"])

    def claim_local(self, lease_seconds: int = 300) -> dict | None:
        token = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT analysis_id FROM local_queue
                       WHERE available_at <= now() AND (claimed_until IS NULL OR claimed_until < now())
                       ORDER BY available_at, analysis_id FOR UPDATE SKIP LOCKED LIMIT 1"""
                ).fetchone()
                if row is None:
                    return None
                return conn.execute(
                    """UPDATE local_queue
                       SET claimed_until = now() + %s * interval '1 second',
                           claim_token = %s, attempts = attempts + 1
                       WHERE analysis_id = %s
                       RETURNING analysis_id, claim_token, attempts""",
                    (lease_seconds, token, row["analysis_id"]),
                ).fetchone()

    def claim_processing(
        self, analysis_id: UUID, lease_seconds: int, max_attempts: int
    ) -> dict:
        token = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT a.id, a.source_url, a.mode, a.status, a.attempt_count, a.next_retry_at,
                              a.processing_claimed_until, a.supplier_snapshot_id,
                              EXISTS (
                                SELECT 1 FROM analysis_assessments aa
                                WHERE aa.analysis_id = a.id
                              ) AS has_assessment
                       FROM analyses a WHERE a.id = %s FOR UPDATE""",
                    (analysis_id,),
                ).fetchone()
                if row is None:
                    return {"outcome": "unknown"}
                if row["status"] == "COMPLETED":
                    return {"outcome": "completed"}
                if row["status"] == "FAILED_FINAL":
                    return {"outcome": "final"}
                now = datetime.now(timezone.utc)
                if row["processing_claimed_until"] and row["processing_claimed_until"] > now:
                    return {
                        "outcome": "busy",
                        "available_at": row["processing_claimed_until"],
                    }
                if row["next_retry_at"] and row["next_retry_at"] > now:
                    return {"outcome": "waiting", "available_at": row["next_retry_at"]}
                if row["attempt_count"] >= max_attempts:
                    conn.execute(
                        """UPDATE analyses SET status = 'FAILED_FINAL',
                                  failure_code = 'PROCESSING_ATTEMPTS_EXHAUSTED',
                                  next_retry_at = NULL, final_disposition = 'DLQ_PENDING',
                                  processing_claim_token = NULL,
                                  processing_claimed_until = NULL
                           WHERE id = %s""",
                        (analysis_id,),
                    )
                    self._event(
                        conn, analysis_id, "FAILED_FINAL", row["attempt_count"],
                        failure_code="PROCESSING_ATTEMPTS_EXHAUSTED",
                        disposition="DLQ_PENDING",
                    )
                    return {"outcome": "final"}
                attempt = row["attempt_count"] + 1
                if row["has_assessment"]:
                    phase_status = "REPORTING"
                elif row["supplier_snapshot_id"] is not None:
                    phase_status = "ASSESSING"
                else:
                    phase_status = "PROCESSING"
                conn.execute(
                    """UPDATE analyses SET status = %s, attempt_count = %s,
                           processing_claim_token = %s,
                           processing_claimed_until = now() + %s * interval '1 second',
                           processing_started_at = COALESCE(processing_started_at, now()),
                           failure_code = NULL, next_retry_at = NULL, final_disposition = NULL
                       WHERE id = %s""",
                    (phase_status, attempt, token, lease_seconds, analysis_id),
                )
                self._event(conn, analysis_id, phase_status, attempt)
                return {
                    "outcome": "acquired", "analysis_id": analysis_id,
                    "source_url": row["source_url"], "mode": row["mode"],
                    "attempt": attempt, "token": token,
                    "phase": (
                        "reporting" if phase_status == "REPORTING"
                        else "assessment" if phase_status == "ASSESSING"
                        else "extraction"
                    ),
                }

    def record_result_conflict(self, analysis_id: UUID) -> None:
        """Keep the first result and leave durable evidence for the duplicate."""
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT a.attempt_count
                       FROM analyses a JOIN analysis_results r ON r.analysis_id = a.id
                       WHERE a.id = %s FOR UPDATE OF a""",
                    (analysis_id,),
                ).fetchone()
                if row is None:
                    raise LookupError(f"No stored result for analysis {analysis_id}")
                conn.execute(
                    """UPDATE analyses SET status = 'COMPLETED',
                              completed_at = COALESCE(completed_at, now()),
                              failure_code = 'RESULT_CONFLICT', next_retry_at = NULL,
                              final_disposition = NULL, processing_claim_token = NULL,
                              processing_claimed_until = NULL
                       WHERE id = %s""",
                    (analysis_id,),
                )
                self._event(
                    conn, analysis_id, "COMPLETED", row["attempt_count"],
                    failure_code="RESULT_CONFLICT",
                )

    def complete_processing(self, analysis_id: UUID, token: UUID, payload: dict) -> str:
        with self.connect() as conn:
            with conn.transaction():
                return self._complete_processing(conn, analysis_id, token, payload)

    def complete_extraction_for_assessment(
        self, analysis_id: UUID, token: UUID, payload: dict
    ) -> str:
        """Persist immutable extraction evidence while retaining the worker lease."""
        with self.connect() as conn:
            with conn.transaction():
                return self._complete_processing(
                    conn, analysis_id, token, payload, handoff_to_assessment=True
                )

    def import_customer_page(
        self, source_url: str, user_id: UUID, payload: dict, *,
        customer_limit: int, window_seconds: int,
    ) -> UUID:
        """Admit and persist an in-memory upload in one transaction, without a queue."""
        supplier_data = payload.get("supplier_data")
        if payload.get("source_url") != source_url or (
            payload.get("extraction_status") in {"SUCCESS", "PARTIAL"}
            and (not isinstance(supplier_data, dict)
                 or supplier_data.get("extraction_method") != "USER_UPLOAD"
                 or supplier_data.get("analysis_mode") != "ACCOUNT_PUBLIC"
                 or supplier_data.get("platform") != source_platform(source_url))
        ):
            raise ValueError("Upload result has mismatched provenance")
        analysis_id = uuid4()
        token = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                self._admit(conn, "CUSTOMER", str(user_id), customer_limit, window_seconds)
                self._insert_analysis(conn, analysis_id, source_url, user_id, actor_type="CUSTOMER")
                conn.execute(
                    """UPDATE analyses SET status = 'PROCESSING', attempt_count = 1,
                              extraction_method = 'USER_UPLOAD', processing_claim_token = %s
                       WHERE id = %s""",
                    (token, analysis_id),
                )
                self._event(conn, analysis_id, "PROCESSING", 1)
                self._complete_processing(conn, analysis_id, token, payload)
        return analysis_id

    def capture_customer_page(
        self, source_url: str, user_id: UUID, payload: dict, *,
        customer_limit: int, window_seconds: int,
    ) -> UUID:
        """Admit and persist selected browser evidence atomically without a queue."""
        reject_sensitive_page_state(payload.get("raw_payload", {}))
        supplier_data = payload.get("supplier_data")
        if payload.get("source_url") != source_url or (
            payload.get("extraction_status") in {"SUCCESS", "PARTIAL"}
            and (not isinstance(supplier_data, dict)
                 or supplier_data.get("extraction_method") != "EXTENSION_DOM"
                 or supplier_data.get("analysis_mode") != "EXTENSION_ENHANCED"
                 or supplier_data.get("platform") != source_platform(source_url))
        ):
            raise ValueError("Capture has mismatched provenance")
        analysis_id = uuid4()
        token = uuid4()
        with self.connect() as conn:
            with conn.transaction():
                self._admit(conn, "CUSTOMER", str(user_id), customer_limit, window_seconds)
                previous = conn.execute(
                    """SELECT s.id AS supplier_snapshot_id, s.normalized_data AS supplier_data,
                              s.raw_payload AS raw_payload
                       FROM analyses a JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
                       WHERE a.user_id = %s AND a.actor_type = 'CUSTOMER'
                         AND a.status = 'COMPLETED' AND a.source_url = %s
                       ORDER BY a.completed_at DESC, a.id DESC LIMIT 1""",
                    (user_id, source_url),
                ).fetchone()
                if previous is not None and supplier_data is not None:
                    payload = merge_extension_evidence(payload, previous)
                self._insert_analysis(conn, analysis_id, source_url, user_id, actor_type="CUSTOMER")
                conn.execute(
                    """UPDATE analyses SET status = 'PROCESSING', attempt_count = 1,
                              mode = 'EXTENSION_ENHANCED', extraction_method = 'EXTENSION_DOM',
                              processing_claim_token = %s WHERE id = %s""",
                    (token, analysis_id),
                )
                self._event(conn, analysis_id, "PROCESSING", 1)
                self._complete_processing(conn, analysis_id, token, payload)
        return analysis_id

    def renormalize_customer_snapshot(
        self, source_analysis_id: UUID, user_id: UUID, *,
        customer_limit: int, window_seconds: int,
    ) -> UUID:
        """Create an owned analysis from retained public fields without a crawl."""
        with self.connect() as conn:
            with conn.transaction():
                source = conn.execute(
                    """SELECT a.source_url, a.mode, a.extraction_method, a.status,
                              a.supplier_snapshot_id, r.payload AS result,
                              s.raw_payload, s.normalized_data, s.extracted_at,
                              s.extractor_version, s.supplier_id,
                              supplier.platform AS supplier_platform,
                              supplier.platform_supplier_id
                       FROM analyses a
                       JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
                       JOIN suppliers supplier ON supplier.id = s.supplier_id
                       JOIN analysis_results r ON r.analysis_id = a.id
                       WHERE a.id = %s AND a.user_id = %s AND a.actor_type = 'CUSTOMER'
                       FOR UPDATE OF a""",
                    (source_analysis_id, user_id),
                ).fetchone()
                if source is None:
                    raise LookupError("Owned source analysis not found")
                old = source["normalized_data"]
                if (source["status"] != "COMPLETED"
                        or source["result"].get("extraction_status") not in {"SUCCESS", "PARTIAL"}
                        or not isinstance(old, dict)
                        or old.get("source_url") != source["source_url"]
                        or old.get("analysis_mode") != source["mode"]
                        or old.get("extraction_method") != source["extraction_method"]
                        or old.get("extractor_version") != source["extractor_version"]
                        or old.get("extracted_at") != source["extracted_at"].isoformat()):
                    raise UnsupportedRawEvidence("Incompatible source snapshot")
                reject_sensitive_page_state(source["raw_payload"])
                outcome = renormalize_public_fields(
                    raw_payload=source["raw_payload"], source_url=source["source_url"],
                    extraction_method=source["extraction_method"],
                    analysis_mode=source["mode"], extracted_at=old["extracted_at"],
                    source_snapshot_id=source["supplier_snapshot_id"],
                    source_extractor_version=source["extractor_version"],
                )
                revised = outcome["supplier_data"]
                if (revised["platform"] != source["supplier_platform"]
                        or revised["platform_supplier_id"] != source["platform_supplier_id"]):
                    raise UnsupportedRawEvidence("Replay cannot change supplier identity")
                self._admit(conn, "CUSTOMER", str(user_id), customer_limit, window_seconds)
                analysis_id, token = uuid4(), uuid4()
                self._insert_analysis(conn, analysis_id, source["source_url"], user_id, actor_type="CUSTOMER")
                conn.execute(
                    """UPDATE analyses SET status = 'PROCESSING', attempt_count = 1,
                              extraction_method = %s, processing_claim_token = %s
                       WHERE id = %s""",
                    (source["extraction_method"], token, analysis_id),
                )
                self._event(conn, analysis_id, "PROCESSING", 1)
                self._complete_processing(conn, analysis_id, token, outcome,
                                          existing_supplier_id=source["supplier_id"])
                return analysis_id

    def _complete_processing(self, conn, analysis_id: UUID, token: UUID, payload: dict,
                             *, existing_supplier_id: UUID | None = None,
                             handoff_to_assessment: bool = False) -> str:
        public_payload = {key: value for key, value in payload.items()
                          if key not in {"raw_payload", "reviews", "supplier_data"}}
        row = conn.execute(
            """SELECT a.status, a.source_url, a.mode, a.extraction_method, a.supplier_snapshot_id,
                      a.processing_claim_token, a.attempt_count, r.payload
               FROM analyses a LEFT JOIN analysis_results r ON r.analysis_id = a.id
               WHERE a.id = %s FOR UPDATE OF a""",
            (analysis_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Unknown analysis {analysis_id}")
        extracted = payload.get("extraction_status") in {"SUCCESS", "PARTIAL"}
        supplier_data = payload.get("supplier_data")
        platform = source_platform(row["source_url"]) if extracted else None
        browser_transition = (extracted and isinstance(supplier_data, dict)
                              and row["status"] == "PROCESSING" and row["processing_claim_token"] == token
                              and row["extraction_method"] == "PUBLIC_HTTP"
                              and supplier_data.get("extraction_method") == "PUBLIC_BROWSER"
                              and row["mode"] in {"GUEST_PUBLIC", "ACCOUNT_PUBLIC"})
        if extracted and (
            not isinstance(supplier_data, dict)
            or not isinstance(payload.get("raw_payload"), dict)
            or not isinstance(payload.get("reviews"), list)
            or supplier_data.get("source_url") != row["source_url"]
            or supplier_data.get("analysis_mode") != row["mode"]
            or normalize_source_url(row["source_url"]) != row["source_url"]
            or payload.get("source_url") != row["source_url"]
            or supplier_data.get("platform") != platform
            or (supplier_data.get("extraction_method") != row["extraction_method"] and not browser_transition)
            or (supplier_data.get("extraction_method"), row["mode"]) not in {
                ("PUBLIC_HTTP", "GUEST_PUBLIC"), ("PUBLIC_HTTP", "ACCOUNT_PUBLIC"),
                ("PUBLIC_BROWSER", "GUEST_PUBLIC"), ("PUBLIC_BROWSER", "ACCOUNT_PUBLIC"),
                ("USER_UPLOAD", "ACCOUNT_PUBLIC"), ("EXTENSION_DOM", "EXTENSION_ENHANCED")}
        ):
            raise ValueError("Extracted result is missing matching supplier evidence")
        if row["status"] == "COMPLETED":
            if row["payload"] != public_payload:
                raise ResultConflict("Completed analysis has a different immutable result")
            if extracted:
                snapshot = conn.execute(
                    "SELECT raw_payload, normalized_data FROM supplier_snapshots WHERE id = %s",
                    (row["supplier_snapshot_id"],),
                ).fetchone()
                reviews = conn.execute(
                    "SELECT payload FROM supplier_reviews WHERE snapshot_id = %s ORDER BY ordinal",
                    (row["supplier_snapshot_id"],),
                ).fetchall()
                if (snapshot is None or snapshot["raw_payload"] != payload["raw_payload"]
                        or snapshot["normalized_data"] != supplier_data
                        or [item["payload"] for item in reviews] != payload["reviews"]):
                    raise ResultConflict("Completed analysis has different supplier evidence")
            elif row["supplier_snapshot_id"] is not None:
                raise ResultConflict("Completed analysis has a supplier snapshot")
            return "replay"
        if row["processing_claim_token"] != token or row["status"] != "PROCESSING":
            raise LeaseLost("Processing lease is no longer current")
        inserted = conn.execute(
            """INSERT INTO analysis_results (analysis_id, payload)
               VALUES (%s, %s::jsonb) ON CONFLICT (analysis_id) DO NOTHING
               RETURNING payload""",
            (analysis_id, json.dumps(public_payload)),
        ).fetchone()
        if inserted is None:
            stored = conn.execute(
                "SELECT payload FROM analysis_results WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["payload"]
            if stored != public_payload:
                raise ResultConflict("Stored result conflicts with computed result")
        if extracted:
            supplier_id = existing_supplier_id or uuid4()
            external_id = supplier_data.get("platform_supplier_id")
            if existing_supplier_id is not None:
                # A replay derives older captured evidence. Reuse its supplier
                # without overwriting the supplier's more recent display data.
                pass
            elif external_id:
                if supplier_data["extraction_method"] in {"USER_UPLOAD", "EXTENSION_DOM"}:
                    supplier = conn.execute(
                        """INSERT INTO suppliers (id, platform, platform_supplier_id, name, source_url)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (platform, platform_supplier_id) DO NOTHING
                           RETURNING id""",
                        (supplier_id, platform, external_id, supplier_data.get("supplier_name"), supplier_data["source_url"]),
                    ).fetchone()
                    if supplier is None:
                        supplier = conn.execute(
                            "SELECT id FROM suppliers WHERE platform = %s AND platform_supplier_id = %s",
                            (platform, external_id),
                        ).fetchone()
                else:
                    supplier = conn.execute(
                        """INSERT INTO suppliers (id, platform, platform_supplier_id, name, source_url)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (platform, platform_supplier_id)
                           DO UPDATE SET name = COALESCE(EXCLUDED.name, suppliers.name),
                                         source_url = EXCLUDED.source_url,
                                         updated_at = now()
                           RETURNING id""",
                        (supplier_id, platform, external_id, supplier_data.get("supplier_name"), supplier_data["source_url"]),
                    ).fetchone()
                supplier_id = supplier["id"]
            else:
                conn.execute(
                    """INSERT INTO suppliers (id, platform, name, source_url)
                       VALUES (%s, %s, %s, %s)""",
                    (supplier_id, platform, supplier_data.get("supplier_name"), supplier_data["source_url"]),
                )
            snapshot_id = uuid4()
            conn.execute(
                """INSERT INTO supplier_snapshots
                     (id, supplier_id, analysis_id, extracted_at, raw_payload,
                      normalized_data, completeness, missing_fields,
                      extraction_method, analysis_mode, extractor_version)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s,
                           %s::jsonb, %s, %s, %s)""",
                (snapshot_id, supplier_id, analysis_id, supplier_data["extracted_at"],
                 json.dumps(payload["raw_payload"]), json.dumps(supplier_data),
                 supplier_data["completeness"], json.dumps(supplier_data["missing_fields"]),
                 supplier_data["extraction_method"], supplier_data["analysis_mode"],
                 supplier_data["extractor_version"]),
            )
            for ordinal, review in enumerate(payload.get("reviews") or []):
                conn.execute(
                    """INSERT INTO supplier_reviews (id, snapshot_id, ordinal, payload)
                       VALUES (%s, %s, %s, %s::jsonb)""",
                    (uuid4(), snapshot_id, ordinal, json.dumps(review)),
                )
            conn.execute(
                """UPDATE analyses SET supplier_snapshot_id = %s,
                          extraction_method = %s WHERE id = %s""",
                (snapshot_id, supplier_data["extraction_method"], analysis_id),
            )
        if handoff_to_assessment and extracted:
            updated = conn.execute(
                """UPDATE analyses SET status = 'ASSESSING',
                       failure_code = NULL, next_retry_at = NULL, final_disposition = NULL
                   WHERE id = %s AND processing_claim_token = %s
                   RETURNING id""",
                (analysis_id, token),
            ).fetchone()
            if updated is None:
                raise LeaseLost("Processing lease is no longer current")
            self._event(conn, analysis_id, "ASSESSING", row["attempt_count"])
            return "assessing"
        conn.execute(
            """UPDATE analyses SET status = 'COMPLETED', completed_at = now(),
                   failure_code = NULL, next_retry_at = NULL, final_disposition = NULL,
                   processing_claim_token = NULL, processing_claimed_until = NULL
               WHERE id = %s AND processing_claim_token = %s""",
            (analysis_id, token),
        )
        self._event(conn, analysis_id, "COMPLETED", row["attempt_count"])
        return "completed"

    def record_processing_failure(
        self,
        analysis_id: UUID,
        token: UUID,
        *,
        failure_code: str,
        max_attempts: int,
        retry_delay_seconds: int,
        local_claim_token: UUID | None = None,
    ) -> bool:
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """SELECT status, attempt_count FROM analyses
                       WHERE id = %s AND processing_claim_token = %s FOR UPDATE""",
                    (analysis_id, token),
                ).fetchone()
                if row is None or row["status"] not in {"PROCESSING", "ASSESSING", "REPORTING"}:
                    raise LeaseLost("Processing lease is no longer current")
                final = row["attempt_count"] >= max_attempts
                status = "FAILED_FINAL" if final else "FAILED_RETRYABLE"
                disposition = "DLQ_PENDING" if final else None
                updated = conn.execute(
                    """UPDATE analyses SET status = %s, failure_code = %s,
                           next_retry_at = CASE WHEN %s THEN NULL
                             ELSE now() + %s * interval '1 second' END,
                           final_disposition = %s,
                           processing_claim_token = NULL, processing_claimed_until = NULL
                       WHERE id = %s AND processing_claim_token = %s
                       RETURNING next_retry_at""",
                    (status, failure_code, final, retry_delay_seconds, disposition,
                     analysis_id, token),
                ).fetchone()
                if local_claim_token is not None:
                    if final:
                        result = conn.execute(
                            "DELETE FROM local_queue WHERE analysis_id = %s AND claim_token = %s",
                            (analysis_id, local_claim_token),
                        )
                    else:
                        result = conn.execute(
                            """UPDATE local_queue SET claim_token = NULL, claimed_until = NULL,
                                      available_at = %s
                               WHERE analysis_id = %s AND claim_token = %s""",
                            (updated["next_retry_at"], analysis_id, local_claim_token),
                        )
                    if result.rowcount != 1:
                        raise LeaseLost("Local queue lease is no longer current")
                self._event(
                    conn, analysis_id, status, row["attempt_count"],
                    failure_code=failure_code, next_retry_at=updated["next_retry_at"],
                    disposition=disposition,
                )
                return final

    def finish_local(self, analysis_id: UUID, claim_token: UUID) -> None:
        with self.connect() as conn:
            result = conn.execute(
                "DELETE FROM local_queue WHERE analysis_id = %s AND claim_token = %s",
                (analysis_id, claim_token),
            )
            if result.rowcount != 1:
                raise LeaseLost("Local queue lease is no longer current")

    def release_local(self, analysis_id: UUID, claim_token: UUID, delay_seconds: int = 2) -> None:
        with self.connect() as conn:
            result = conn.execute(
                """UPDATE local_queue SET claim_token = NULL, claimed_until = NULL,
                          available_at = now() + %s * interval '1 second'
                   WHERE analysis_id = %s AND claim_token = %s""",
                (delay_seconds, analysis_id, claim_token),
            )
            if result.rowcount != 1:
                raise LeaseLost("Local queue lease is no longer current")

    def mark_dead_lettered(self, analysis_id: UUID) -> bool:
        with self.connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """UPDATE analyses SET final_disposition = 'DEAD_LETTERED'
                       WHERE id = %s AND status = 'FAILED_FINAL'
                         AND final_disposition IS DISTINCT FROM 'DEAD_LETTERED'
                       RETURNING attempt_count, failure_code""",
                    (analysis_id,),
                ).fetchone()
                if row is None:
                    return False
                self._event(
                    conn, analysis_id, "FAILED_FINAL", row["attempt_count"],
                    failure_code=row["failure_code"], disposition="DEAD_LETTERED",
                )
                return True
