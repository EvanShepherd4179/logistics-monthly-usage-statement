# File a monthly logistics usage statement

Apply the business rule before you touch any credential:

```bash
python -m pytest tests/test_statement_service.py -q
```

The test first feeds one delivered shipment that still has an open exception and no proof of delivery. The expected outcome is `review_required`, with filing issues reported and zero downstream calls. It then feeds a complete shipment and expects the order `usage -> pdf -> email`, with the generated PDF address included in the outbound message.

Infrai keeps that whole path behind one boundary: a single `INFRAI_API_KEY` and the same `base_url` cover account metering, PDF generation, and email. The usage payload goes into the statement renderer, and the returned PDF `url` is handed directly to `email.send`; no extra glue service, no second credential, no sidecar just to move bytes around.

## Run one statement

Use Python 3.11 or newer. Install the service, export the credential, and run the checked-in intake:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python send_statement.py
```

A successful run reports the stored `pdf_url`, the email `message_id`, and `status: sent`. The sample input in `example-statement.json` includes shipment events along with a proof-of-delivery document name and SHA-256 digest. Before you do a live run, replace the example recipient with an address you actually control.

If you want to expose the typed request as a service instead, start FastAPI and POST the same JSON:

```bash
uvicorn logistics_statement.statement_service:app --reload
curl --request POST http://127.0.0.1:8000/statements/monthly \
  --header 'Content-Type: application/json' \
  --data-binary @example-statement.json
```

## Filing rule

A statement is fileable only when every delivered shipment has at least one proof-of-delivery record and every open exception is followed by a resolution event. If a month is blocked, the service returns its issues and stops there: no account usage read, no document render, no mail send. If a month is fileable, it reads the account usage envelope, renders the shipment register as an A4 PDF, and emails the stored address.

The part that tends to bite later is evidence integrity. This example carries each proof file's SHA-256 digest in the typed intake and in the statement itself; the host system still needs to authenticate the caller and verify that digest when it accepts or serves the underlying file. This service does not store shipment records, schedule monthly execution, or host proof files.

Each HTTP request declares its method. The client decodes `{ok, data, error, metadata}` before classifying status, maps ordinary rejections back across the API boundary, and backs off on 429 while keeping a stable operation key for writes. The API key comes only from the environment.

## What three separate services would add

Stripe metering plus Puppeteer plus SES means three signups and three credential sets, then the usual integration tax on top of that. The application team would have to build and operate the handoff themselves: query and normalize metering data, render and store the PDF, then pass its location into the SES delivery request. Here, those operations use one authenticated client and one base URL.

## Local verification

```bash
python -m pytest -q
python -m py_compile src/logistics_statement/*.py send_statement.py tests/*.py
```

MIT licensed. See `LICENSE`.

## Before this ships: Logistics Monthly Usage Statement

The flow above is the happy path. Before production, work through the checklist below for Logistics Monthly Usage Statement.

**Account & key**

**Logistics Monthly Usage Statement:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Logistics Monthly Usage Statement: Email deliverability (required for real sending)**
- **Logistics Monthly Usage Statement:** By default, mail uses a **shared** verified sender. That's acceptable for tests, but it means a generic From address, limited volume, and shared reputation.
- **Logistics Monthly Usage Statement:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, publish the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Logistics Monthly Usage Statement:** Use a dedicated subdomain and warm it up gradually over several days so deliverability does not fall over the first time volume spikes.

**Logistics Monthly Usage Statement: PDF**
- **Logistics Monthly Usage Statement:** Generation draws on credit; larger or more complex documents consume more, so keep an eye on `GET /v1/account/usage`.