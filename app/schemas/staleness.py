from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum

class StalenessStatusEnum(str, Enum):
    FRESH = "Fresh"
    MODIFIED = "Modified"
    REMOVED = "Removed"

class NodeStaleness(BaseModel):
    logical_node_id: str
    status: StalenessStatusEnum
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)

class GenerationStalenessResponse(BaseModel):
    generation_id: str
    is_stale: bool
    overall_status: StalenessStatusEnum
    latest_document_version: str
    original_document_version: str
    node_details: List[NodeStaleness]

    model_config = ConfigDict(use_enum_values=True)
