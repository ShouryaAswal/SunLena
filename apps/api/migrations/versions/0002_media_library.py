"""Add catalog preview URLs and durable conversion jobs."""

from alembic import op
import sqlalchemy as sa


revision = "0002_media_library"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("preview_url", sa.String(length=2048), nullable=True))
    op.create_table(
        "media_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("output_format", sa.String(length=12), nullable=False),
        sa.Column("bitrate", sa.String(length=12), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("artist", sa.String(length=500), nullable=True),
        sa.Column("source_title", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_media_jobs_progress_range"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_jobs_owner_created", "media_jobs", ["owner_id", "created_at"])
    op.create_index("ix_media_jobs_status_created", "media_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_media_jobs_status_created", table_name="media_jobs")
    op.drop_index("ix_media_jobs_owner_created", table_name="media_jobs")
    op.drop_table("media_jobs")
    op.drop_column("tracks", "preview_url")
