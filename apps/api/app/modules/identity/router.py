from fastapi import APIRouter, Depends

from app.modules.identity.auth import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/me", tags=["identity"])


@router.get("")
def get_profile(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }
