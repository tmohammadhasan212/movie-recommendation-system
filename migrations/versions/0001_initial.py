"""Initial domain schema.

Revision ID: 0001
Revises:
"""

from alembic import op

from backend.app.core import models  # noqa: F401
from backend.app.core.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
