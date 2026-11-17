"""Add movie overviews and external rating metadata.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("overview", sa.Text(), nullable=True))
    op.add_column("movies", sa.Column("overview_source", sa.String(length=30), nullable=True))
    op.add_column("movies", sa.Column("tmdb_rating", sa.Float(), nullable=True))
    op.add_column("movies", sa.Column("tmdb_vote_count", sa.Integer(), nullable=True))
    op.add_column(
        "movies", sa.Column("tmdb_metadata_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("movies", sa.Column("imdb_rating", sa.Float(), nullable=True))
    op.add_column("movies", sa.Column("imdb_vote_count", sa.Integer(), nullable=True))
    op.add_column(
        "movies", sa.Column("imdb_rating_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_movies_tmdb_rating", "movies", "tmdb_rating IS NULL OR (tmdb_rating >= 0 AND tmdb_rating <= 10)"
    )
    op.create_check_constraint(
        "ck_movies_tmdb_vote_count", "movies", "tmdb_vote_count IS NULL OR tmdb_vote_count >= 0"
    )
    op.create_check_constraint(
        "ck_movies_imdb_rating", "movies", "imdb_rating IS NULL OR (imdb_rating >= 0 AND imdb_rating <= 10)"
    )
    op.create_check_constraint(
        "ck_movies_imdb_vote_count", "movies", "imdb_vote_count IS NULL OR imdb_vote_count >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_movies_imdb_vote_count", "movies", type_="check")
    op.drop_constraint("ck_movies_imdb_rating", "movies", type_="check")
    op.drop_constraint("ck_movies_tmdb_vote_count", "movies", type_="check")
    op.drop_constraint("ck_movies_tmdb_rating", "movies", type_="check")
    op.drop_column("movies", "imdb_rating_updated_at")
    op.drop_column("movies", "imdb_vote_count")
    op.drop_column("movies", "imdb_rating")
    op.drop_column("movies", "tmdb_metadata_updated_at")
    op.drop_column("movies", "tmdb_vote_count")
    op.drop_column("movies", "tmdb_rating")
    op.drop_column("movies", "overview_source")
    op.drop_column("movies", "overview")
