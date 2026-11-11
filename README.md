# TradeStream

TradeStream is a React dashboard backed by a FastAPI trade puller and a
paginated Mock BSE service. It saves trades in SQLite and streams saved rows to
the dashboard over WebSockets.

## Architecture

```mermaid
flowchart LR
    BSE[Mock BSE] --> Backend[Main Backend]
    Backend --> Dashboard[Dashboard]
```

## Mock BSE API

`GET /getTrades` returns a server-sized page of deterministic seeded trades.
Pass the optional opaque `cursor` query parameter from a prior response to
retrieve the next page; omit it to start a pull.

```json
{
  "trades": [],
  "next_cursor": "opaque-string-or-null",
  "total": 5000,
  "page": 1,
  "total_pages": 50
}
```

The mock uses `SEED` (default `42`), `TOTAL_TRADES` (default `5000`),
`PAGE_SIZE` (default `100`), and `PULL_DELAY_SECONDS` (default `900`). The
delay is split across pages so each request remains below the connection limit.

## Pull mechanism

The main backend starts a background pull when it starts and can also be
triggered with `POST /pull`. It requests Mock BSE one page at a time, saves
each page to SQLite immediately, and resumes from the last saved cursor after
a restart. This avoids holding an HTTP connection open beyond the 30-second
network limit; `GET /pull/status` reports progress and `GET /trades` returns
already saved data while the pull continues.

## Data layer

SQLite stores trades and pull runs. It uses WAL mode, a five-second busy
timeout, and indexes on `trades.timestamp` and `trades.pulled_at`. Duplicate
trade IDs are ignored safely during repeat pulls. Every trade response includes
its SQLite `seq` value, allowing incremental clients to request rows newer than
an `after_seq` value.

## Real-time updates

The dashboard can connect to `WS /ws` instead of polling. Pages are saved to
SQLite before their trades are broadcast, and clients can reconnect with
`after_seq` for sequence-based catch-up; replay buffering closes the gap
between replay and live broadcasts. The server sends a heartbeat ping every
20 seconds to keep otherwise idle WebSocket connections alive. For local
verification, `scripts/ws_live_verify.py` is a development-only WebSocket
client.

## Dashboard

The React dashboard loads the latest 200 saved trades and current pull status
once, then receives trade and progress updates through `WS /ws`. It deduplicates
by `seq`, reconnects with sequence-based catch-up if the backend restarts, and
offers filtering by symbol or client without polling or refreshing the page.

## Run with Docker

From the repository root:

```bash
cp .env.example .env  # PowerShell: Copy-Item .env.example .env
docker compose up --build
```

Open <http://localhost:5173>. Health endpoints are available at:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

Stop the services with `docker compose down`.

The Compose backend always uses `http://mock_bse:8001` internally. The browser
uses `http://localhost:8000` and derives `ws://localhost:8000/ws` from it.

## Measuring Mock BSE page requests

With Mock BSE running, use the development-only `scripts/measure_requests.py`
tool to time every paginated request:

```bash
python scripts/measure_requests.py http://localhost:8001
```

For the default 5,000 trades and 100-trade pages, each page delay is 18 seconds
(`900 / 50`), below the 30-second connection limit. The main backend uses a
25-second request timeout, leaving room for the response while staying below
that limit.

## Run without Docker

Use three terminals from the repository root.

```bash
# Terminal 1: Mock BSE
cd backend/mock_bse
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
uvicorn app:app --reload --port 8001
```

```bash
# Terminal 2: Main backend
cd backend/main
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
$env:MOCK_BSE_URL = "http://localhost:8001"  # optional; this is the default
uvicorn app:app --reload --port 8000
```

```bash
# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

The frontend development server listens on <http://localhost:5173> and connects
to the main backend at <http://localhost:8000>.
