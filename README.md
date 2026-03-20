# Flight BFF

FastAPI backend-for-frontend wrapper for the `easyGDS` legacy flight API. The service hides the upstream's inconsistent URL scheme, nested payloads, mixed datetime formats, duplicate fields, and fragmented error contracts behind a frontend-friendly REST API for web and mobile clients.

## What It Does

- Exposes a clean public API under `/api/v1`
- Normalizes 4 different upstream error formats into one shape
- Flattens flight search results for UI rendering
- Enriches airport, airline, cabin, payment-method, and status labels
- Normalizes multiple upstream datetime formats into ISO 8601
- Adds pagination to the upstream flight search response
- Caches airport reference data and booking retrieval summaries
- Ships with generated Swagger UI and explicit request/response examples

## Stack

- Python 3.12
- FastAPI
- httpx
- Pydantic v2
- cachetools
- tenacity
- structlog
- pytest

## Public Endpoints

- `POST /api/v1/flights/search?page=1&pageSize=10`
- `GET /api/v1/offers/{offerId}`
- `POST /api/v1/bookings`
- `GET /api/v1/bookings/{bookingReference}`
- `GET /health`

## Project Layout

- `app/main.py`: FastAPI app factory, middleware, startup wiring
- `app/api/`: route handlers and exception handlers
- `app/clients/legacy_api.py`: upstream HTTP client, retries, circuit breaker, error translation
- `app/services/`: orchestration, normalization, booking and airport caching
- `app/core/`: config, code maps, datetime handling, cache wrappers
- `app/models/api.py`: public request/response models and Swagger examples
- `tests/`: fixture-backed unit and API tests
- `assessment.md`: implementation and design write-up for the assessment

## Local Setup

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -e '.[dev]'
```

3. Start the API:

```bash
uvicorn app.main:app --reload
```

4. Open the docs:

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

## Example Requests

Flight search:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/flights/search?page=1&pageSize=2' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": "SIN",
    "destination": "BKK",
    "departureDate": "2026-04-15",
    "passengers": 1,
    "cabin": "Y"
  }'
```

Offer details:

```bash
curl 'http://127.0.0.1:8000/api/v1/offers/b441ff9174795f49'
```

Create booking:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/bookings' \
  -H 'Content-Type: application/json' \
  -d '{
    "offerId": "b441ff9174795f49",
    "contact": {
      "email": "alice@example.com",
      "phone": "+6591234567"
    },
    "passengers": [
      {
        "title": "MS",
        "firstName": "Alice",
        "lastName": "Tan",
        "dateOfBirth": "1990-05-12",
        "nationality": "SG",
        "passportNumber": "E1234567"
      }
    ]
  }'
```

Retrieve booking:

```bash
curl -i 'http://127.0.0.1:8000/api/v1/bookings/EGABE5C6'
```

## Swagger / Demo Payloads

The payloads shown in Swagger UI are defined explicitly in [app/models/api.py](/Users/truongnguyen/Projects/flight-assessment-be/app/models/api.py) and [app/api/routes.py](/Users/truongnguyen/Projects/flight-assessment-be/app/api/routes.py). If you want to change the demo request or response bodies shown in `/docs`, update the `json_schema_extra` examples on the top-level models or the `openapi_examples` attached to the POST routes.

## Testing

Run the full suite:

```bash
pytest
```

Current automated coverage includes:

- datetime normalization
- response normalizers
- search pagination
- unified error translation
- booking cache hit/miss behavior
- rate-limit, timeout, and circuit-breaker handling

Run the optional end-to-end suite against the live upstream mock:

```bash
RUN_E2E=1 pytest -m e2e
```

What this does:

- starts the BFF locally with `uvicorn` if `E2E_BASE_URL` is not set
- calls the BFF over real HTTP instead of using the mocked transport
- exercises the live upstream mock API through the full wrapper stack
- runs a search -> offer -> create booking -> retrieve booking flow

By default, E2E tests are skipped during a normal `pytest` run.

To run only non-E2E tests:

```bash
pytest -m "not e2e"
```

Optional environment overrides for E2E:

- `E2E_BASE_URL`: target an already running BFF instance instead of starting local `uvicorn`

Example against an already running instance:

```bash
RUN_E2E=1 E2E_BASE_URL=http://127.0.0.1:8000 pytest -m e2e
```

## Configuration

Supported environment variables:

- `BFF_UPSTREAM_BASE_URL`
- `BFF_CONNECT_TIMEOUT_SECONDS`
- `BFF_READ_TIMEOUT_SECONDS`
- `BFF_MAX_CONNECTIONS`
- `BFF_MAX_KEEPALIVE_CONNECTIONS`
- `BFF_RETRY_ATTEMPTS`
- `BFF_CIRCUIT_BREAKER_FAILURE_THRESHOLD`
- `BFF_CIRCUIT_BREAKER_RECOVERY_SECONDS`
- `BFF_AIRPORT_CACHE_TTL_SECONDS`
- `BFF_BOOKING_CACHE_TTL_SECONDS`
- `BFF_DEFAULT_PAGE_SIZE`
- `BFF_MAX_PAGE_SIZE`

## Notes

- Airport reference data is cached in-process for 24 hours.
- Booking retrieval responses are cached in-process for 60 seconds and return `X-Cache: MISS|HIT`.
- Booking creation is intentionally not retried to reduce duplicate booking risk.
- Search, offer lookup, airport lookup, and booking retrieval are retried on timeout, `429`, and `5xx`.
- A normalized error response always includes a `requestId`.

More detailed design and assessment notes are in [assessment.md](/Users/truongnguyen/Projects/flight-assessment-be/assessment.md).
