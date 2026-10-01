from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ShipmentEventKind(StrEnum):
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION_OPENED = "exception_opened"
    EXCEPTION_RESOLVED = "exception_resolved"


class ShipmentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ShipmentEventKind
    occurred_at: datetime
    note: str = Field(default="", max_length=500)


class ProofOfDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_name: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ShipmentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str = Field(min_length=1, max_length=100)
    events: list[ShipmentEvent] = Field(min_length=1)
    proof_of_delivery: list[ProofOfDelivery] = Field(default_factory=list)


class MonthlyStatementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str = Field(min_length=1, max_length=200)
    customer_email: str = Field(
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254
    )
    statement_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    shipments: list[ShipmentRecord] = Field(min_length=1)


class FilingIssue(BaseModel):
    shipment_id: str
    reason: str


class StatementResponse(BaseModel):
    status: str
    pdf_url: str | None = None
    message_id: str | None = None
    issues: list[FilingIssue] = Field(default_factory=list)
