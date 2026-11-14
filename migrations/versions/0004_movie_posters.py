"""Add optional poster enrichment metadata.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("poster_path", sa.String(length=200), nullable=True))
    op.add_column("movies", sa.Column("poster_source", sa.String(length=30), nullable=True))
    op.add_column(
        "movies", sa.Column("poster_updated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("movies", "poster_updated_at")
    op.drop_column("movies", "poster_source")
    op.drop_column("movies", "poster_path")
