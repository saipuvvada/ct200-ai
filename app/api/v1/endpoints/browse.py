from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.browse import (
    DocumentResponse, SectionResponse, NodeResponse, 
    SearchResponse, ChangeResponse
)
from app.services.browse_service import BrowseService

router = APIRouter(tags=["Browse"])

@router.get("/documents", response_model=List[DocumentResponse])
def get_documents(db: Session = Depends(get_db)):
    """
    List all uploaded and parsed documents and their version strings.
    """
    return BrowseService.list_documents(db)

@router.get("/documents/{document_id}/sections", response_model=List[SectionResponse])
def get_sections(
    document_id: int,
    version: Optional[str] = Query(None, description="Optional version to filter by (e.g. 'latest' or '2')"),
    db: Session = Depends(get_db)
):
    """
    Retrieve root-level document nodes.
    """
    sections = BrowseService.get_sections(db, document_id, version)
    if sections is None:
        raise HTTPException(status_code=404, detail="Document or matching version not found")
    return sections

@router.get("/node/{id}", response_model=NodeResponse)
def get_node(id: int, db: Session = Depends(get_db)):
    """
    Retrieve details for a single document hierarchy node by its database ID, including children recursively.
    """
    node = BrowseService.get_node_details(db, id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found for ID {id}")
    return node

@router.get("/search", response_model=List[SearchResponse])
def search_nodes(
    q: str = Query(..., min_length=1, description="Text keyword query string", alias="query"),
    version: Optional[str] = Query(None, description="Optional document version"),
    heading_only: bool = Query(False, description="Search headings only"),
    db: Session = Depends(get_db)
):
    """
    Fuzzy search for keyword occurrences within the headings or body text of a document version.
    """
    return BrowseService.search(db, q, version, heading_only)

@router.get("/node/{id}/changes", response_model=ChangeResponse)
def get_node_changes(id: int, db: Session = Depends(get_db)):
    """
    Returns the historical modifications of a section across previous document version
    sharing the same logical_node_id.
    """
    change = BrowseService.get_node_changes(db, id)
    if not change:
        raise HTTPException(status_code=404, detail="Node not found")
    return change
