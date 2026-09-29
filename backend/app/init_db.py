import os

from .migrations import apply_migrations


if __name__ == "__main__":
    apply_migrations(os.environ["DATABASE_URL"])
