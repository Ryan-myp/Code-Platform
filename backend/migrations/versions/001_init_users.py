"""add users table with authentication fields

Revision ID: init_users
Revises:
Create Date: 2024-01-01

This migration adds the users table for JWT-based authentication.
"""

import sqlalchemy as sa
from alembic import op

revision = "init_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("username", sa.Text(), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="user"),
        sa.Column("created_at", sa.Text()),
        sa.Column("active", sa.Integer(), server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("users")
