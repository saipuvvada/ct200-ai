import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class SelectionCreate(BaseModel):
    """
    Payload to create a new named selection of nodes pinned to a document.
    """
    name: str = Field(..., min_length=1, max_length=255)
    document_id: int
    node_ids: List[int] = Field(..., min_length=1, description="List of node database IDs to include in the selection")

class SelectionItemResponse(BaseModel):
    """
    Represents an item within a selection.
    """
    id: int
    selection_id: int
    node_id: int

    model_config = ConfigDict(from_attributes=True)

class SelectionResponse(BaseModel):
    """
    Represents a full selection including its items.
    """
    id: int
    name: str
    document_id: int
    created_at: datetime.datetime
    items: List[SelectionItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
