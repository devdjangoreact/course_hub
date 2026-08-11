"""multi-bot subdomain tables and order attribution

Revision ID: 0003_multi_bot_subdomain
Revises: 0002_multilingual_search
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_multi_bot_subdomain"
down_revision: str | None = "0002_multilingual_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON_DEFAULT = sa.text("'{}'")


def _extra() -> sa.Column:
    return sa.Column("extra", sa.JSON(), server_default=_JSON_DEFAULT, nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "bots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False, server_default=""),
        sa.Column("webhook_secret", sa.String(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("notes", sa.String(), nullable=False, server_default=""),
        _extra(),
        *_timestamps(),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_bots_username", "bots", ["username"])
    op.create_index("ix_bots_is_active", "bots", ["is_active"])

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_id", sa.Integer(), sa.ForeignKey("bots.id"), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("discussion_group_id", sa.BigInteger(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("discussion_is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("invite_link", sa.String(), nullable=False, server_default=""),
        sa.Column("discussion_invite_link", sa.String(), nullable=False, server_default=""),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("slug", sa.String(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_channels_bot_id", "channels", ["bot_id"])
    op.create_index("ix_channels_telegram_chat_id", "channels", ["telegram_chat_id"])
    op.create_index("ix_channels_is_active", "channels", ["is_active"])

    op.create_table(
        "channel_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        _extra(),
        sa.UniqueConstraint("channel_id", "course_id"),
    )
    op.create_index("ix_channel_courses_channel_id", "channel_courses", ["channel_id"])
    op.create_index("ix_channel_courses_course_id", "channel_courses", ["course_id"])

    op.add_column("orders", sa.Column("bot_id", sa.Integer(), sa.ForeignKey("bots.id"), nullable=True))
    op.add_column(
        "orders", sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id"), nullable=True)
    )
    op.create_index("ix_orders_bot_id", "orders", ["bot_id"])
    op.create_index("ix_orders_channel_id", "orders", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_channel_id", table_name="orders")
    op.drop_index("ix_orders_bot_id", table_name="orders")
    op.drop_column("orders", "channel_id")
    op.drop_column("orders", "bot_id")
    op.drop_table("channel_courses")
    op.drop_table("channels")
    op.drop_table("bots")
