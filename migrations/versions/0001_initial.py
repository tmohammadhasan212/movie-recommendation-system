"""Initial domain schema.

Revision ID: 0001
Revises:

This migration intentionally owns a frozen metadata snapshot. Importing the
application's live metadata here would make a clean migration change whenever
the ORM models evolve, causing later revisions to conflict with revision 0001.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("email", sa.String(320), nullable=False),
    sa.Column("password_hash", sa.String(255), nullable=False),
    sa.Column("profile_version", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
)
sa.Index("ix_users_email", users.c.email, unique=True)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("refresh_hash", sa.String(64), nullable=False, unique=True),
    sa.Column("csrf_hash", sa.String(64), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("device_label", sa.String(100), nullable=True),
)
sa.Index("ix_sessions_user_id", sessions.c.user_id)

movies = sa.Table(
    "movies",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("movielens_id", sa.Integer(), nullable=False),
    sa.Column("title", sa.String(500), nullable=False),
    sa.Column("release_year", sa.Integer(), nullable=True),
    sa.Column("genres", postgresql.JSONB(), nullable=False),
    sa.Column("imdb_id", sa.String(20), nullable=True),
    sa.Column("tmdb_id", sa.Integer(), nullable=True),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("source", sa.String(30), nullable=False),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
)
sa.Index("ix_movies_movielens_id", movies.c.movielens_id, unique=True)
sa.Index("ix_movies_title_lower", sa.func.lower(movies.c.title))
sa.Index("ix_movies_genres_gin", movies.c.genres, postgresql_using="gin")

sa.Table(
    "imported_ratings",
    metadata,
    sa.Column("source_user_id", sa.Integer(), primary_key=True),
    sa.Column("movielens_id", sa.Integer(), primary_key=True),
    sa.Column("rating", sa.Float(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "rating >= 0.5 AND rating <= 5.0 AND rating * 2 = floor(rating * 2)"
    ),
)

sa.Table(
    "ratings",
    metadata,
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "movie_id",
        sa.Integer(),
        sa.ForeignKey("movies.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    sa.Column("rating", sa.Float(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "rating >= 0.5 AND rating <= 5.0 AND rating * 2 = floor(rating * 2)"
    ),
)

sa.Table(
    "watchlist_items",
    metadata,
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "movie_id",
        sa.Integer(),
        sa.ForeignKey("movies.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

sa.Table(
    "genre_preferences",
    metadata,
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("genre", sa.String(60), primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

interaction_events = sa.Table(
    "interaction_events",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "movie_id",
        sa.Integer(),
        sa.ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("event_type", sa.String(30), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("request_id", sa.String(64), nullable=False),
    sa.Column("consent_source", sa.String(30), nullable=False),
)
sa.Index("ix_interaction_events_user_id", interaction_events.c.user_id)

outbox_events = sa.Table(
    "outbox_events",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("aggregate_ref", sa.String(100), nullable=False),
    sa.Column("event_type", sa.String(50), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("error_code", sa.String(60), nullable=True),
)
sa.Index("ix_outbox_events_status", outbox_events.c.status)
sa.Index("ix_outbox_events_next_attempt_at", outbox_events.c.next_attempt_at)

sa.Table(
    "processed_events",
    metadata,
    sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("consumer_name", sa.String(60), primary_key=True),
    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
)

model_versions = sa.Table(
    "model_versions",
    metadata,
    sa.Column("version_id", sa.String(80), primary_key=True),
    sa.Column("artifact_uri", sa.Text(), nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("training_manifest_uri", sa.Text(), nullable=False),
    sa.Column("evaluation", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
)
sa.Index(
    "uq_one_active_model",
    model_versions.c.active,
    unique=True,
    postgresql_where=model_versions.c.active.is_(True),
)

sa.Table(
    "data_imports",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_name", sa.String(80), nullable=False),
    sa.Column("source_version", sa.String(80), nullable=False),
    sa.Column("checksum", sa.String(64), nullable=False, unique=True),
    sa.Column("counts", sa.JSON(), nullable=False),
    sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
)

sa.Table(
    "idempotency_records",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("action", sa.String(50), nullable=False),
    sa.Column("key", sa.String(100), nullable=False),
    sa.Column("request_hash", sa.String(64), nullable=False),
    sa.Column("response", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("user_id", "action", "key"),
)


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
