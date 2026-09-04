from typing import Literal
from pydantic import BaseModel, Field


class AuditRequest(BaseModel):
    resource_id: str


class FinOpsAudit(BaseModel):

    resource_id: str

    resource_type: str

    issue_type: Literal[
        "IDLE_RESOURCE",
        "LEGACY_STORAGE",
        "ORPHANED_STORAGE"
    ]

    monthly_cost: float

    recommendation: str

    estimated_savings: float = Field(
        ge=0
    )

    source: str
