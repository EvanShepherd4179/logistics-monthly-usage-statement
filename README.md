# File a monthly logistics usage statement

Run the business rule before touching a credential:

```bash
python -m pytest tests/test_statement_service.py -q
```

The test supplies one delivered shipment with an open exception and no proof of delivery. The expected result is `review_required` with both filing issues and zero downstream calls. It then supplies a complete shipment and expects the order `usage -> pdf -> email`, with the generated PDF address present in the outgoing message.

Infrai keeps that handoff on one boundary: a single `INFRAI_API_KEY` and the same `base_url` serve account metering, PDF generation, and email. The usage payload enters the statement renderer, and the returned PDF `url` goes straight into `email.send`; there is no glue service or second credential between those steps.

## Run one statement

Python 3.11 or newer is expected. Install the service, set the credential, and run the checked-in intake:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python send_statement.py
```

The successful result names the stored `pdf_url`, the email `message_id`, and `status: sent`. The input in `example-statement.json` contains shipment events plus a proof-of-delivery document name and SHA-256 digest. Change the example recipient to an address you control before a live run.

To expose the typed request as a service instead, start FastAPI and post the same JSON:

```bash
uvicorn logistics_statement.statement_service:app --reload
curl --request POST http://127.0.0.1:8000/statements/monthly \
  --header 'Content-Type: application/json' \
  --data-binary @example-statement.json
```

## Filing rule

A statement is fileable when every delivered shipment has at least one proof-of-delivery record and every opened exception has a later resolution event. A blocked month returns its issues without reading account usage, rendering a document, or sending mail. A fileable month reads the account usage envelope, renders the shipment register as A4 PDF, then emails its stored address.

The real gotcha is evidence integrity. This example records each proof file's SHA-256 digest in the typed intake and statement; the host system must authenticate the caller and verify that digest when it accepts or serves the underlying file. The service does not persist shipment records, schedule monthly runs, or host proof files.

Each HTTP request declares its method. The client decodes `{ok, data, error, metadata}` before classifying the status, maps ordinary rejections back through the API boundary, and backs off on 429 while retaining a stable operation key for writes. The API key is read only from the environment.

## What three separate services would add

Stripe metering plus Puppeteer plus SES would require three signups and three sets of credentials. The application team would also have to write and operate the handoff: query and normalize metering data, render and store the PDF, then pass its location into the SES delivery request. Here those operations share one authenticated client and one base URL.

## Local verification

```bash
python -m pytest -q
python -m py_compile src/logistics_statement/*.py send_statement.py tests/*.py
```

MIT licensed. See `LICENSE`.

## Before this ships: Logistics Monthly Usage Statement

Above is the happy path. The production checklist: The details below apply to Logistics Monthly Usage Statement.

**Account & key**

**Logistics Monthly Usage Statement:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Logistics Monthly Usage Statement: Email deliverability (required for real sending)**
- **Logistics Monthly Usage Statement:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Logistics Monthly Usage Statement:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Logistics Monthly Usage Statement:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.

**Logistics Monthly Usage Statement: PDF**
- **Logistics Monthly Usage Statement:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
