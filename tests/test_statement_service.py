from typing import Any

from logistics_statement.models import MonthlyStatementRequest
from logistics_statement.statement_service import deliver_statement


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.email_html = ""

    def account_usage(self) -> dict[str, Any]:
        self.calls.append("usage")
        return {"period": "2026-09", "requests": 42}

    def generate_statement(
        self, markdown: str, operation_id: str
    ) -> dict[str, Any]:
        self.calls.append("pdf")
        assert "SHP-CLEAR" in markdown
        assert operation_id.endswith(":2026-09")
        return {"url": "https://documents.example/statement.pdf"}

    def send_statement(
        self, to: str, subject: str, html: str, operation_id: str
    ) -> dict[str, Any]:
        self.calls.append("email")
        self.email_html = html
        assert to == "records@example.com"
        return {"message_id": "msg_1042"}


def request_with_shipments(shipments: list[dict[str, Any]]) -> MonthlyStatementRequest:
    return MonthlyStatementRequest.model_validate(
        {
            "customer_name": "Northwind Cold Chain",
            "customer_email": "records@example.com",
            "statement_month": "2026-09",
            "shipments": shipments,
        }
    )


def test_only_fileable_month_is_rendered_and_emailed() -> None:
    blocked = request_with_shipments(
        [
            {
                "shipment_id": "SHP-BLOCKED",
                "events": [
                    {"kind": "delivered", "occurred_at": "2026-09-04T16:40:00Z"},
                    {
                        "kind": "exception_opened",
                        "occurred_at": "2026-09-04T17:00:00Z",
                        "note": "temperature review",
                    },
                ],
                "proof_of_delivery": [],
            }
        ]
    )
    blocked_gateway = RecordingGateway()

    blocked_result = deliver_statement(blocked, blocked_gateway)

    assert blocked_result.status == "review_required"
    assert {issue.reason for issue in blocked_result.issues} == {
        "open exception",
        "delivered shipment has no proof of delivery",
    }
    assert blocked_gateway.calls == []

    ready = request_with_shipments(
        [
            {
                "shipment_id": "SHP-CLEAR",
                "events": [
                    {
                        "kind": "exception_resolved",
                        "occurred_at": "2026-09-05T09:00:00Z",
                    },
                    {
                        "kind": "delivered",
                        "occurred_at": "2026-09-05T10:00:00Z",
                    },
                    {
                        "kind": "exception_opened",
                        "occurred_at": "2026-09-05T08:00:00Z",
                    }
                ],
                "proof_of_delivery": [
                    {"document_name": "signed.pdf", "sha256": "b" * 64}
                ],
            }
        ]
    )
    ready_gateway = RecordingGateway()

    ready_result = deliver_statement(ready, ready_gateway)

    assert ready_result.status == "sent"
    assert ready_gateway.calls == ["usage", "pdf", "email"]
    assert ready_result.pdf_url in ready_gateway.email_html
    assert ready_result.message_id == "msg_1042"
