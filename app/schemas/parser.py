from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict

class ParsedNode(BaseModel):
    """
    Pydantic schema representing a node extracted during PDF parsing.
    Supports a recursive tree structure via the children list.
    """
    heading: Optional[str] = None
    level: int = 1
    body: Optional[str] = None
    node_type: str = Field(description="Type of node: heading, paragraph, table, list, image")
    order_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    children: List["ParsedNode"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

# Resolve self-referencing forward references in Pydantic v2
ParsedNode.model_rebuild()
