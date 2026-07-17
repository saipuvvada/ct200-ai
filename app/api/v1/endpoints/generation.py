from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.generation import GenerationResponse
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/selections", tags=["Generations"])

@router.post("/{selection_id}/generate", response_model=GenerationResponse)
def generate_qa_for_selection(
    selection_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate Question and Answer pairs from a selection of document nodes using the Groq API.
    The resulting generation is automatically validated and persisted to MongoDB.
    """
    return GenerationService.generate_for_selection(db, selection_id)
