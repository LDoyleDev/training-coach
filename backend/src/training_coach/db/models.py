"""ORM models. Import every model here so Alembic autogenerate sees it.

Phase 1 adds the plan, session queue and log tables (docs/specs/phase-1-daily-loop.md).
"""

from training_coach.db.base import Base

__all__ = ["Base"]
