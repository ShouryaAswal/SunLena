from functools import lru_cache

import firebase_admin
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.identity.models import User

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _firebase_app():
    settings = get_settings()
    if not settings.firebase_project_id or not settings.firebase_service_account_path:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")
    try:
        return firebase_admin.get_app()
    except ValueError:
        try:
            credential = credentials.Certificate(settings.firebase_service_account_path)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Firebase service account is unavailable.") from exc
        return firebase_admin.initialize_app(
            credential, {"projectId": settings.firebase_project_id}
        )


def get_current_user(
    token: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if token is None or token.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = auth.verify_id_token(token.credentials, app=_firebase_app())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Your sign-in has expired. Please sign in again.") from exc

    uid = claims.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="The sign-in token has no user identity.")
    user = db.scalar(select(User).where(User.firebase_uid == uid))
    if user is None:
        user = User(
            firebase_uid=uid,
            email=claims.get("email"),
            display_name=claims.get("name"),
            avatar_url=claims.get("picture"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
