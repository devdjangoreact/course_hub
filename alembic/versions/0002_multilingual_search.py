"""multilingual catalog and parser workflow

Revision ID: 0002_multilingual_search
Revises: 0001_initial
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_multilingual_search"
down_revision: str | None = "0001_initial"
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
    op.add_column(
        "bot_users",
        sa.Column("preferred_language", sa.String(), nullable=False, server_default="uk"),
    )
    op.create_index("ix_bot_users_preferred_language", "bot_users", ["preferred_language"])

    op.create_table(
        "supported_languages",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("native_name", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
    )
    op.create_index("ix_supported_languages_is_default", "supported_languages", ["is_default"])
    op.create_index("ix_supported_languages_is_active", "supported_languages", ["is_active"])

    op.create_table(
        "category_translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column(
            "language_code", sa.String(), sa.ForeignKey("supported_languages.code"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        _extra(),
        sa.UniqueConstraint("category_id", "language_code"),
    )
    op.create_index(
        "ix_category_translations_category_id", "category_translations", ["category_id"]
    )
    op.create_index(
        "ix_category_translations_language_code", "category_translations", ["language_code"]
    )
    op.create_index("ix_category_translations_name", "category_translations", ["name"])

    op.create_table(
        "course_translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "language_code", sa.String(), sa.ForeignKey("supported_languages.code"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        _extra(),
        sa.UniqueConstraint("course_id", "language_code"),
    )
    op.create_index("ix_course_translations_course_id", "course_translations", ["course_id"])
    op.create_index(
        "ix_course_translations_language_code", "course_translations", ["language_code"]
    )
    op.create_index("ix_course_translations_name", "course_translations", ["name"])

    op.create_table(
        "parser_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_status", sa.String(), nullable=True),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_parser_sources_name", "parser_sources", ["name"])
    op.create_index("ix_parser_sources_source_type", "parser_sources", ["source_type"])
    op.create_index("ix_parser_sources_is_active", "parser_sources", ["is_active"])

    op.create_table(
        "parser_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("parser_sources.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(), nullable=True),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_parser_jobs_source_id", "parser_jobs", ["source_id"])
    op.create_index("ix_parser_jobs_status", "parser_jobs", ["status"])

    op.create_table(
        "imported_catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parser_job_id", sa.Integer(), sa.ForeignKey("parser_jobs.id"), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("language_code", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=_JSON_DEFAULT, nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column(
            "matched_category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True
        ),
        sa.Column("matched_course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
        _extra(),
        *_timestamps(),
        sa.UniqueConstraint("parser_job_id", "fingerprint"),
    )
    op.create_index(
        "ix_imported_catalog_items_parser_job_id", "imported_catalog_items", ["parser_job_id"]
    )
    op.create_index("ix_imported_catalog_items_item_type", "imported_catalog_items", ["item_type"])
    op.create_index(
        "ix_imported_catalog_items_external_id", "imported_catalog_items", ["external_id"]
    )
    op.create_index(
        "ix_imported_catalog_items_fingerprint", "imported_catalog_items", ["fingerprint"]
    )
    op.create_index(
        "ix_imported_catalog_items_language_code", "imported_catalog_items", ["language_code"]
    )
    op.create_index("ix_imported_catalog_items_status", "imported_catalog_items", ["status"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS localized_catalog_fts
            USING fts5(item_type, item_id UNINDEXED, language_code, title, body)
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TABLE IF EXISTS localized_catalog_fts")
    op.drop_table("imported_catalog_items")
    op.drop_table("parser_jobs")
    op.drop_table("parser_sources")
    op.drop_table("course_translations")
    op.drop_table("category_translations")
    op.drop_table("supported_languages")
    op.drop_index("ix_bot_users_preferred_language", table_name="bot_users")
    op.drop_column("bot_users", "preferred_language")
