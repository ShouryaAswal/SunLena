from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.catalog.models import Track
from app.modules.identity.auth import get_current_user
from app.modules.identity.models import User
from app.modules.reviews.models import Review

router = APIRouter(prefix="/tracks/{track_id}/reviews", tags=["reviews"])


class ReviewInput(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str | None = Field(default=None, max_length=1000)


@router.get("")
def list_reviews(track_id: UUID, db: Session = Depends(get_db)) -> dict:
    if db.get(Track, track_id) is None:
        raise HTTPException(status_code=404, detail="Track not found.")
    rows = db.scalars(select(Review).where(Review.track_id == track_id).order_by(Review.updated_at.desc())).all()
    total, average = db.execute(
        select(func.count(Review.id), func.avg(Review.rating)).where(Review.track_id == track_id)
    ).one()
    return {
        "count": total,
        "average_rating": round(float(average), 1) if average is not None else None,
        "reviews": [
            {"id": str(row.id), "rating": row.rating, "body": row.body, "created_at": row.created_at}
            for row in rows
        ],
    }


@router.get("/mine")
def get_my_review(
    track_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict | None:
    review = db.scalar(select(Review).where(Review.track_id == track_id, Review.author_id == user.id))
    if review is None:
        return None
    return {"id": str(review.id), "rating": review.rating, "body": review.body}


@router.put("")
def upsert_review(
    track_id: UUID,
    payload: ReviewInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if db.get(Track, track_id) is None:
        raise HTTPException(status_code=404, detail="Track not found.")
    review = db.scalar(select(Review).where(Review.track_id == track_id, Review.author_id == user.id))
    if review is None:
        review = Review(track_id=track_id, author_id=user.id, rating=payload.rating, body=payload.body)
        db.add(review)
    else:
        review.rating = payload.rating
        review.body = payload.body
    db.commit()
    db.refresh(review)
    return {"id": str(review.id), "rating": review.rating, "body": review.body, "updated_at": review.updated_at}


@router.delete("", status_code=204)
def delete_review(
    track_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    review = db.scalar(select(Review).where(Review.track_id == track_id, Review.author_id == user.id))
    if review is None:
        raise HTTPException(status_code=404, detail="Your review was not found.")
    db.delete(review)
    db.commit()
