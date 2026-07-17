from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.staleness import GenerationStalenessResponse
from app.services.staleness_service import StalenessService

router = APIRouter(prefix="/generations", tags=["Staleness"])

@router.get("/{generation_id}/staleness", response_model=GenerationStalenessResponse)
def get_generation_staleness(
    generation_id: str,
    db: Session = Depends(get_db)
):
    """
    Check the staleness of a previously generated QA test case.
    Compares the generated node hashes against the latest document version.
    """
    return StalenessService.get_generation_staleness(db, generation_id)
