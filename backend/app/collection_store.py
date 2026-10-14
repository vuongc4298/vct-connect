"""Transactional single-admission collection and deadline fallback."""
import json
from uuid import uuid4
from .storage_errors import CollectionConflict


class CollectionStoreMixin:
    def begin_collection(self, analysis_id, user_id, payload, digest, *, customer_limit,
                         trial_limit, window_seconds, guided=False):
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(analysis_id),))
            old = conn.execute("""SELECT a.user_id, j.initial_digest FROM extension_collection_jobs j
                                  JOIN analyses a ON a.id=j.analysis_id WHERE j.analysis_id=%s""",
                               (analysis_id,)).fetchone()
            if old:
                if old["user_id"] != user_id or old["initial_digest"] != digest:
                    raise CollectionConflict("Collection identity conflicts")
                return analysis_id
            if conn.execute("SELECT id FROM analyses WHERE id=%s", (analysis_id,)).fetchone():
                raise CollectionConflict("Collection identity conflicts")
            self._admit(conn, "CUSTOMER", str(user_id),
                        self._customer_quota(conn, user_id, customer_limit, trial_limit), window_seconds)
            self._insert_analysis(conn, analysis_id, payload["source_url"], user_id, actor_type="CUSTOMER")
            conn.execute("""UPDATE analyses SET status='PROCESSING', mode='EXTENSION_ENHANCED',
                            extraction_method='EXTENSION_DOM', processing_claim_token=%s,
                            attempt_count=1 WHERE id=%s""", (uuid4(), analysis_id))
            self._event(conn, analysis_id, "PROCESSING", 1)
            conn.execute("""INSERT INTO extension_collection_jobs(analysis_id, initial_digest, initial_payload, expires_at)
                            VALUES (%s,%s,%s::jsonb,now() + %s * interval '1 second')""",
                         (analysis_id, digest, json.dumps(payload), 1800 if guided else 60))
        return analysis_id

    def _finish_collection(self, conn, row, payload, digest, azure):
        self._complete_processing(conn, row["analysis_id"], row["processing_claim_token"], payload,
                                  handoff_to_assessment=True)
        conn.execute("UPDATE analyses SET attempt_count=0 WHERE id=%s", (row["analysis_id"],))
        conn.execute("UPDATE extension_collection_jobs SET finished=true, final_digest=%s WHERE analysis_id=%s",
                     (digest, row["analysis_id"]))
        if azure:
            conn.execute("INSERT INTO analysis_outbox(analysis_id,message_id) VALUES (%s,%s)",
                         (row["analysis_id"], row["analysis_id"]))
        else:
            conn.execute("INSERT INTO local_queue(analysis_id) VALUES (%s)", (row["analysis_id"],))

    def finish_collection(self, analysis_id, user_id, payload, digest, *, azure=False):
        with self.connect() as conn:
            row = conn.execute("""SELECT j.*, a.user_id, a.source_url, a.processing_claim_token,
                                   j.expires_at <= now() AS expired
                                   FROM extension_collection_jobs j JOIN analyses a ON a.id=j.analysis_id
                                   WHERE j.analysis_id=%s AND a.user_id=%s FOR UPDATE OF j""",
                               (analysis_id, user_id)).fetchone()
            if not row:
                raise LookupError("Collection not found")
            if row["finished"]:
                if row["final_digest"] not in {digest, "TIMEOUT"}:
                    raise CollectionConflict("Collection already finalized with different evidence")
                return
            if payload["source_url"] != row["source_url"]:
                raise CollectionConflict("Product changed during collection")
            from .extraction.supplier_bundle import shop_identity
            from .extraction.alibaba_browser import alibaba_company_url
            initial_shop = row["initial_payload"]["raw_payload"]["linked_collection"].get("shop_url")
            final_shop = payload["raw_payload"]["linked_collection"].get("shop_url")
            initial_platform = row["initial_payload"]["supplier_data"]["platform"]
            if payload["supplier_data"]["platform"] != initial_platform:
                raise CollectionConflict("Supplier platform changed during collection")
            identity = alibaba_company_url if initial_platform == "ALIBABA" else shop_identity
            if (identity(initial_shop) if initial_shop else None) != (identity(final_shop) if final_shop else None):
                raise CollectionConflict("Supplier shop changed during collection")
            if row["expired"]:
                payload, digest = self._collection_fallback(row), "TIMEOUT"
            self._finish_collection(conn, row, payload, digest, azure)

    @staticmethod
    def _collection_fallback(row):
        payload = row["initial_payload"]
        payload["raw_payload"]["collection_deadline_fallback"] = True
        payload["raw_payload"]["linked_collection"]["outcomes"] = [
            {"page": page, "status": "TIMEOUT"} for page in ("SHOP", "FACTORY")]
        payload["supplier_data"]["collection_status"] = payload["raw_payload"]["linked_collection"]["outcomes"]
        return payload

    def finish_expired_collections(self, *, azure=False):
        with self.connect() as conn:
            rows = conn.execute("""SELECT j.*, a.processing_claim_token FROM extension_collection_jobs j
                                    JOIN analyses a ON a.id=j.analysis_id
                                    WHERE NOT j.finished AND j.expires_at <= now()
                                    ORDER BY j.expires_at LIMIT 10 FOR UPDATE OF j SKIP LOCKED""").fetchall()
            for row in rows:
                self._finish_collection(conn, row, self._collection_fallback(row), "TIMEOUT", azure)
        return len(rows)
