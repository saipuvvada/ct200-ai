from typing import Optional, List
from pydantic import BaseModel
from app.schemas.generation import GenerationResponse
from app.schemas.staleness import GenerationStalenessResponse

class GenerationWithStaleness(GenerationResponse):
    staleness: Optional[GenerationStalenessResponse] = None

class RetrievalResponse(BaseModel):
    data: List[GenerationWithStaleness]
