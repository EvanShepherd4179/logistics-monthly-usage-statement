from __future__ import annotations

import html
import json
from typing import Any, Protocol

import httpx
from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .models import (
    FilingIssue,
    MonthlyStatementRequest,
    ShipmentEventKind,
    StatementResponse,
)


class StatementGateway(Protocol):
    def account_usage(self) -> dict[str, Any]:
        raise AssertionError

    def generate_statement(
        self, markdown: str, operation_id: str
    ) -> dict[str, Any]:
        raise AssertionError

    def send_statement(
        self, to: str, subject: str, html: str, operation_id: str
    ) -> dict[str, Any]:
        raise AssertionError


def filing_issues(request: MonthlyStatementRequest) -> list[FilingIssue]:
    issues: list[FilingIssue] = []
    for shipment in request.shipments:
        delivered = any(
            event.kind is ShipmentEventKind.DELIVERED for event in shipment.events
        )
        opened_at = max(
            (
                event.occurred_at
                for event in shipment.events
                if event.kind is ShipmentEventKind.EXCEPTION_OPENED
            ),
            default=None,
        )
        resolved_at = max(
            (
                event.occurred_at
                for event in shipment.events
                if event.kind is ShipmentEventKind.EXCEPTION_RESOLVED
            ),
            default=None,
        )
        if opened_at is not None and (resolved_at is None or opened_at > resolved_at):
            issues.append(
                FilingIssue(shipment_id=shipment.shipment_id, reason="open exception")
            )
        if delivered and not shipment.proof_of_delivery:
            issues.append(
                FilingIssue(
                    shipment_id=shipment.shipment_id,
                    reason="delivered shipment has no proof of delivery",
                )
            )
    return issues


def deliver_statement(
    request: MonthlyStatementRequest, gateway: StatementGateway
) -> StatementResponse:
    issues = filing_issues(request)
    if issues:
        return StatementResponse(status="review_required", issues=issues)

    usage = gateway.account_usage()
    operation_id = f"logistics-statement:{request.customer_email}:{request.statement_month}"
    markdown = _statement_markdown(request, usage)
    pdf = gateway.generate_statement(markdown, operation_id)
    pdf_url = _required_string(pdf, "url")
    email_result = gateway.send_statement(
        str(request.customer_email),
        f"Logistics usage statement for {request.statement_month}",
        (
            "<p>Your monthly logistics statement is ready to file.</p>"
            f'<p><a href="{html.escape(pdf_url, quote=True)}">Download PDF</a></p>'
        ),
        operation_id,
    )
    return StatementResponse(
        status="sent",
        pdf_url=pdf_url,
        message_id=_required_string(email_result, "message_id"),
    )


def _statement_markdown(
    request: MonthlyStatementRequest, usage: dict[str, Any]
) -> str:
    rows: list[str] = []
    for shipment in request.shipments:
        latest = max(shipment.events, key=lambda event: event.occurred_at)
        pod_names = ", ".join(
            html.escape(item.document_name) for item in shipment.proof_of_delivery
        ) or "none"
        rows.append(
            f"| {html.escape(shipment.shipment_id)} | {latest.kind.value} | "
            f"{latest.occurred_at.isoformat()} | {pod_names} |"
        )
    usage_json = json.dumps(usage, indent=2, sort_keys=True)
    return (
        f"# Logistics usage statement: {request.statement_month}\n\n"
        f"Customer: {html.escape(request.customer_name)}\n\n"
        "| Shipment | Latest event | Timestamp | Proof of delivery |\n"
        "|---|---|---|---|\n"
        + "\n".join(rows)
        + f"\n\n## Metered account usage\n\n```json\n{usage_json}\n```\n"
    )


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Infrai result did not contain {field}")
    return value


app = FastAPI(title="Logistics monthly statement")


@app.post("/statements/monthly", response_model=StatementResponse)
def create_monthly_statement(body: MonthlyStatementRequest) -> StatementResponse:
    try:
        return deliver_statement(body, InfraiClient())
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "error": exc.error},
        ) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
