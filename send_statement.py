import json
from pathlib import Path

from logistics_statement.infrai_client import InfraiClient
from logistics_statement.models import MonthlyStatementRequest
from logistics_statement.statement_service import deliver_statement


def main() -> None:
    payload = json.loads(Path("example-statement.json").read_text(encoding="utf-8"))
    request = MonthlyStatementRequest.model_validate(payload)
    result = deliver_statement(request, InfraiClient())
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
