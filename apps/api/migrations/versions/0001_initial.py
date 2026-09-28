"""Create the initial user, catalog, playlist, and review tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("firebase_uid", name="uq_users_firebase_uid"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "tracks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("artist", sa.String(length=500), nullable=False),
        sa.Column("album", sa.String(length=500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("artwork_url", sa.String(length=2048), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tracks"),
        sa.UniqueConstraint("source_key", name="uq_tracks_source_key"),
    )

    op.create_table(
        "playlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("visibility", sa.String(length=12), nullable=False),
        sa.Column("share_token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE", name="fk_playlists_owner_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_playlists"),
        sa.UniqueConstraint("share_token_hash", name="uq_playlists_share_token_hash"),
    )
    op.create_index("ix_playlists_owner_id", "playlists", ["owner_id"])

    op.create_table(
        "playlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("playlist_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE", name="fk_playlist_items_playlist_id_playlists"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="RESTRICT", name="fk_playlist_items_track_id_tracks"),
        sa.PrimaryKeyConstraint("id", name="pk_playlist_items"),
        sa.UniqueConstraint("playlist_id", "position", name="uq_playlist_items_playlist_id"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE", name="fk_reviews_author_id_users"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE", name="fk_reviews_track_id_tracks"),
        sa.PrimaryKeyConstraint("id", name="pk_reviews"),
        sa.UniqueConstraint("track_id", "author_id", name="uq_reviews_track_id"),
    )
    op.create_index("ix_reviews_author_id", "reviews", ["author_id"])
    op.create_index("ix_reviews_track_id", "reviews", ["track_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_track_id", table_name="reviews")
    op.drop_index("ix_reviews_author_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("playlist_items")
    op.drop_index("ix_playlists_owner_id", table_name="playlists")
    op.drop_table("playlists")
    op.drop_table("tracks")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
