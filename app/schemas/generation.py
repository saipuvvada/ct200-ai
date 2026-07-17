import datetime
from typing import List
from pydantic import BaseModel, Field, ConfigDict

class QAItem(BaseModel):
    """
    A single generated Question and Answer pair.
    """
    question: str = Field(..., description="The generated question based on the selected content.")
    answer: str = Field(..., description="The correct answer to the generated question.")

class GenerationResult(BaseModel):
    """
    The structured output expected from the LLM.
    """
    items: List[QAItem] = Field(description="A list of question and answer pairs.", default_factory=list)

class GenerationResponse(BaseModel):
    """
    API Response containing the generated content and its metadata.
    """
    id: str = Field(..., alias="_id", description="MongoDB document ID")
    selection_id: int
    document_version: str
    prompt_version: str
    created_at: datetime.datetime
    status: str
    items: List[QAItem]

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime.datetime: lambda v: v.isoformat()}
    )
