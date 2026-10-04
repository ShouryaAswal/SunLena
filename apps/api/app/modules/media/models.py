from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class MediaJob(Base):
    __tablename__ = "media_jobs"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_media_jobs_progress_range"),
        CheckConstraint("(track_id IS NOT NULL) OR (source_url IS NOT NULL)", name="ck_media_jobs_has_source"),
        Index("ix_media_jobs_owner_created", "owner_id", "created_at"),
        Index("ix_media_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    track_id: Mapped[UUID | None] = mapped_column(ForeignKey("tracks.id", ondelete="RESTRICT"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(80), default="Waiting in queue")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    output_format: Mapped[str] = mapped_column(String(12), default="auto")
    bitrate: Mapped[str] = mapped_column(String(12), default="192")
    title: Mapped[str | None] = mapped_column(String(500))
    artist: Mapped[str | None] = mapped_column(String(500))
    source_title: Mapped[str | None] = mapped_column(String(500))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(2048))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
