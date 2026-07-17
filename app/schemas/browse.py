import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class DocumentResponse(BaseModel):
    """
    Schema for listing documents.
    """
    id: int
    document_name: str = Field(alias="filename")
    version: str
    created_at: datetime.datetime
    total_nodes: int = 0

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class SectionResponse(BaseModel):
    """
    Schema representing root-level document sections.
    """
    id: int
    logical_node_id: str
    heading: Optional[str] = None
    level: int
    content_hash: str
    has_children: bool = False

    model_config = ConfigDict(from_attributes=True)

class NodeResponse(BaseModel):
    """
    Schema representing document sections and contents recursively.
    """
    id: int
    logical_node_id: str
    document_id: int
    parent_id: Optional[int] = None
    heading: Optional[str] = None
    level: int
    body: Optional[str] = None
    order_index: int
    content_hash: str
    node_type: str
    matched_score: Optional[float] = None
    matching_status: str
    document_version: Optional[str] = None
    children: List["NodeResponse"] = []

    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    """
    Schema representing a search result.
    """
    node_id: int
    heading: Optional[str] = None
    snippet: str
    document_version: str
    logical_node_id: str

    model_config = ConfigDict(from_attributes=True)

class DiffSummary(BaseModel):
    heading_changed: bool
    body_changed: bool
    hash_changed: bool

class ChangeResponse(BaseModel):
    """
    Schema representing the historical state change of a logical node across document versions.
    """
    changed: bool
    change_type: Optional[str] = None
    current_version: Optional[str] = None
    previous_version: Optional[str] = None
    diff_summary: Optional[DiffSummary] = None

    model_config = ConfigDict(from_attributes=True)
