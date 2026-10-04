"""Allow direct URL media jobs and require each job to have a source."""

from alembic import op
import sqlalchemy as sa

revision = "0003_cobalt_media_sources"
down_revision = "0002_media_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("media_jobs", "track_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("media_jobs", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.create_check_constraint("ck_media_jobs_has_source", "media_jobs", "track_id IS NOT NULL OR source_url IS NOT NULL")


def downgrade() -> None:
    op.drop_constraint("ck_media_jobs_has_source", "media_jobs", type_="check")
    op.drop_column("media_jobs", "source_url")
    op.alter_column("media_jobs", "track_id", existing_type=sa.Uuid(), nullable=False)
