"""Add TMDB collection metadata for franchise-aware similarity.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("tmdb_collection_id", sa.Integer(), nullable=True))
    op.add_column(
        "movies", sa.Column("tmdb_collection_name", sa.String(length=500), nullable=True)
    )
    op.create_index(
        "ix_movies_tmdb_collection_id", "movies", ["tmdb_collection_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_movies_tmdb_collection_id", table_name="movies")
    op.drop_column("movies", "tmdb_collection_name")
    op.drop_column("movies", "tmdb_collection_id")
