from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.retrieval import RetrievalResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(tags=["Retrieval"])

@router.get("/selections/{selection_id}/generations", response_model=RetrievalResponse)
def get_generations_by_selection(
    selection_id: int,
    include_staleness: bool = Query(False, description="Compute and include staleness data"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all QA generations associated with a specific selection.
    """
    return RetrievalService.get_generations_by_selection(db, selection_id, include_staleness)

@router.get("/nodes/{logical_node_id}/generations", response_model=RetrievalResponse)
def get_generations_by_node(
    logical_node_id: str,
    include_staleness: bool = Query(False, description="Compute and include staleness data"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all QA generations that include a specific logical node.
    """
    return RetrievalService.get_generations_by_node(db, logical_node_id, include_staleness)
