from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.selection import SelectionCreate, SelectionResponse
from app.services.selection_service import SelectionService

router = APIRouter(prefix="/selections", tags=["Selections"])

@router.post("", response_model=SelectionResponse, status_code=status.HTTP_201_CREATED)
def create_selection(
    selection_in: SelectionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a named selection of nodes pinned to a specific document version.
    """
    return SelectionService.create_selection(db, selection_in)

@router.get("", response_model=List[SelectionResponse])
def get_selections(db: Session = Depends(get_db)):
    """
    Retrieve all named selections.
    """
    return SelectionService.get_selections(db)

@router.get("/{id}", response_model=SelectionResponse)
def get_selection(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific named selection by ID.
    """
    selection = SelectionService.get_selection(db, id)
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")
    return selection

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_selection(id: int, db: Session = Depends(get_db)):
    """
    Delete a named selection.
    """
    success = SelectionService.delete_selection(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Selection not found")
