from yoyo import step

__depends__ = {"0013_reports"}

steps = [
    step(
        """
        CREATE TABLE watchlist_entries (
          id UUID PRIMARY KEY,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT watchlist_user_supplier_key UNIQUE (user_id, supplier_id)
        );
        CREATE INDEX watchlist_user_created_idx
          ON watchlist_entries (user_id, created_at DESC);
        """,
        """
        DROP INDEX watchlist_user_created_idx;
        DROP TABLE watchlist_entries;
        """,
    )
]
