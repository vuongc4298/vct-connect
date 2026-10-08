"""Private reviewer media registry and independent annotations.

Store opaque storage keys only. Never persist external URLs, bearer tokens, or
media content in the evaluator schema.
"""
from yoyo import step

__depends__ = {"0016_review_annotation_fields"}

steps = [
    step(
        """
        CREATE TABLE review_media (
          id UUID PRIMARY KEY,
          run_id UUID NOT NULL REFERENCES llm_review_runs(id) ON DELETE CASCADE,
          review_ordinal INTEGER NOT NULL CHECK (review_ordinal >= 0),
          media_id TEXT NOT NULL CHECK (char_length(media_id) BETWEEN 1 AND 160),
          media_type TEXT NOT NULL CHECK (media_type IN ('IMAGE', 'VIDEO_FRAME')),
          private_storage_key TEXT NOT NULL CHECK (char_length(private_storage_key) BETWEEN 1 AND 512),
          mime_type TEXT NOT NULL CHECK (mime_type IN ('image/png','image/jpeg','image/webp')),
          content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
          timestamp_ms INTEGER CHECK (timestamp_ms >= 0),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (run_id, review_ordinal, media_id),
          CHECK ((media_type = 'IMAGE' AND timestamp_ms IS NULL)
             OR (media_type = 'VIDEO_FRAME' AND timestamp_ms IS NOT NULL))
        );
        CREATE INDEX review_media_case_idx ON review_media (run_id, review_ordinal);
        CREATE TABLE review_media_annotations (
          id UUID PRIMARY KEY,
          media_id UUID NOT NULL REFERENCES review_media(id) ON DELETE CASCADE,
          reviewer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          consistency TEXT NOT NULL CHECK (consistency IN
            ('SUPPORTS','PARTIALLY_SUPPORTS','CONTRADICTS','CANNOT_DETERMINE')),
          notes TEXT NOT NULL DEFAULT '' CHECK (char_length(notes) <= 2000),
          video_start_ms INTEGER CHECK (video_start_ms >= 0),
          video_end_ms INTEGER CHECK (video_end_ms >= 0),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (media_id, reviewer_id),
          CHECK ((video_start_ms IS NULL AND video_end_ms IS NULL)
             OR (video_start_ms IS NOT NULL AND video_end_ms IS NOT NULL
               AND video_end_ms >= video_start_ms))
        );
        CREATE INDEX review_media_annotations_reviewer_idx
          ON review_media_annotations (reviewer_id, created_at DESC);
        """,
        """
        DROP TABLE review_media_annotations;
        DROP TABLE review_media;
        """,
    ),
]
