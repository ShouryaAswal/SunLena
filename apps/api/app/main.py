from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.catalog.router import router as catalog_router
from app.modules.identity.router import router as identity_router
from app.modules.playlists.router import router as playlists_router
from app.modules.reviews.router import router as reviews_router
from app.modules.search.router import router as search_router

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Music search, playlists, and reviews for SunLena.",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
)

app.include_router(search_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(identity_router, prefix="/api/v1")
app.include_router(playlists_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Required service is unavailable.") from exc
    return {"status": "ready", "database": "connected"}
