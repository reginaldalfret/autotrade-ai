from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ExternalSource(BaseModel):
    source_id: str
    source_name: str
    source_type: str
    url: Optional[str] = None
    title: str
    summary: str
    symbol: Optional[str] = None
    published_at: datetime
    retrieved_at: datetime
    available_at: datetime
    content_hash: Optional[str] = None

class SourceReference(BaseModel):
    source_id: str
    decision_timestamp: datetime
    was_eligible: bool
