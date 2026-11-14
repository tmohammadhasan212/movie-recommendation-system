"""Record the time a browser session last authenticated.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("sessions")}
    if "authenticated_at" not in columns:
        op.add_column(
            "sessions",
            sa.Column(
                "authenticated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.alter_column("sessions", "authenticated_at", server_default=None)


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("sessions")}
    if "authenticated_at" in columns:
        op.drop_column("sessions", "authenticated_at")
