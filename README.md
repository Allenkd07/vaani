# Vaani — real-time multilingual speech to text

*Vaani* (वाणी) is Hindi and Sanskrit for "speech" or "voice". It transcribes what you say **live, as you speak**, in your language or a mix of languages, saves each transcription, and gives you a searchable history you can edit, play back and delete.

- **Live demo:** *link added after deployment* (Render free tier: the first request after idle can take ~30 s)
- **Stack:** FastAPI · PostgreSQL · SQLAlchemy 2 + Alembic · React 19 + Vite + TypeScript · Gemini Live API (`gemini-3.5-transcribe-live`) · Docker · Render

---

## Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Getting started](#getting-started)
6. [Configuration](#configuration)
7. [API reference](#api-reference)
8. [Data model](#data-model)
9. [Privacy, security and abuse protection](#privacy-security-and-abuse-protection)
10. [Testing](#testing)
11. [Deployment](#deployment)
12. [Design decisions](#design-decisions)
13. [Known limitations](#known-limitations)

---

## Features

**Live transcription**
- Words appear while you speak. Partial text is shown in grey and settles into final text at the end of each spoken segment.
- **Multilingual and code-switching:** the language is auto-detected per segment, so you can switch mid-sentence (e.g. Hindi ↔ English, Malayalam ↔ English). Detected languages appear live as chips ("Hindi, English detected").
- A mic button whose halo follows your voice level, plus a timer and clear status ("Listening…", "Finishing up…", "Couldn't start").

**Saving and history**
- **Auto-save:** a transcription is saved as soon as you stop, so nothing is lost if you navigate away. The recording session also keeps running if you switch pages mid-recording.
- **History** with full CRUD: entries grouped by date (Today, Yesterday, This week, by month), relative times, search with highlighted matches, inline expand, edit dialog, delete confirmation and pagination.
- **Listen:** text-to-speech playback with a voice chosen for the detected language, plus copy to clipboard.

**Experience**
- Light and dark themes (follows the system, with a manual switch; no flash on load).
- Responsive down to phone widths, keyboard accessible, and respects reduced-motion settings.

---

## How it works

```mermaid
flowchart TB
    subgraph Browser
        Mic["Microphone"] --> Worklet["AudioWorklet<br/>16 kHz PCM16, 100 ms chunks"]
        UI["React UI<br/>live transcript, history"]
    end

    subgraph Server["FastAPI container"]
        WS["/ws/transcribe<br/>WebSocket proxy + rate limiter"] --> Adapter["SpeechToTextProvider<br/>Gemini Live adapter"]
        REST["/api/transcriptions<br/>router → service → repository"]
    end

    Gemini["Gemini Live API"]
    DB[("PostgreSQL")]

    Worklet -- "audio over WSS" --> WS
    WS -. "interim / final + language" .-> UI
    UI -- "auto-save, CRUD over HTTPS" --> REST
    Adapter <-- "audio ⇄ text" --> Gemini
    REST --> DB
```

The same container also serves the built React app (gzip, long-lived cache for hashed assets), so the whole product is one deployable unit behind one URL.

1. **Capture.** The browser records the mic with echo cancellation, noise suppression and auto gain. An `AudioWorklet` running on the audio thread resamples it from the device rate (usually 48 kHz) to **16 kHz mono 16-bit PCM**, which is what the model expects, and sends a chunk every **100 ms**. Resampling in the worklet (rather than creating a 16 kHz `AudioContext`) works in every browser, including Firefox.
2. **Proxy.** Audio streams over a WebSocket to FastAPI, which forwards it to Gemini Live. **The API key never reaches the browser.** The proxy runs two tasks concurrently (client → Gemini audio, Gemini → client text) and reacts to whichever finishes first. A provider failure is reported immediately instead of after the user presses stop.
3. **Transcribe.** Gemini returns partial (`interim`) and finished (`final`) text, each with the BCP-47 language code it detected.
4. **Save.** When the session ends, the frontend saves the transcript, its detected languages and its duration through the REST API.

### A live session, end to end

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant B as Browser
    participant S as FastAPI
    participant G as Gemini Live
    participant DB as PostgreSQL

    User->>B: Tap the mic
    B->>S: Open WebSocket /ws/transcribe (owner cookie)
    alt Over a rate limit
        S-->>B: error, close 1008
        Note over B: Shows "Couldn't start"
    else Allowed
        S->>G: Open Live session (API key stays on the server)
        S-->>B: ready
        B->>B: Start mic and AudioWorklet
        loop Every 100 ms while speaking
            B->>S: PCM16 audio chunk
            S->>G: Audio
            G-->>S: interim / final text + language
            S-->>B: interim / final
        end
        User->>B: Tap stop
        B->>S: stop
        S->>G: End of audio
        G-->>S: Last final segments
        S-->>B: Remaining text, then done
        B->>S: POST /api/transcriptions (auto-save)
        S->>DB: INSERT owner_id, text, languages, duration
        S-->>B: 201 Created
    end
```

If Gemini fails at any point (quota, outage), the server sends a user-safe `error` and closes with 1011. Text received before the failure is kept and saved.

### WebSocket protocol — `/ws/transcribe`

| Direction | Message | Meaning |
|---|---|---|
| server → client | `{"type":"ready"}` | Gemini session is open; the client starts the mic |
| client → server | *binary frame* | ~100 ms of PCM16 audio, 16 kHz mono |
| server → client | `{"type":"interim","text":"…","language":"hi-IN"}` | Partial text that may still change |
| server → client | `{"type":"final","text":"…","language":"hi-IN"}` | A finished speech segment |
| client → server | `{"type":"stop"}` | No more audio; the server flushes the remaining text (up to 10 s) |
| server → client | `{"type":"done"}` | Session finished; socket closes normally |
| server → client | `{"type":"error","message":"…"}` | Always a user-safe message. Closes with **1008** if a rate limit rejected the session, **1011** otherwise |

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python 3.13, FastAPI, uvicorn** | Native async WebSockets for the audio proxy, Pydantic validation, and auto-generated OpenAPI docs at `/docs` |
| Database | **PostgreSQL 17, SQLAlchemy 2, Alembic, psycopg 3** | Relational storage with versioned migrations |
| Speech-to-text | **Gemini Live API**, `gemini-3.5-transcribe-live`, via `google-genai` | A transcription-only live model: streaming partial and final text, per-segment language detection and code-switching |
| Frontend | **React 19, Vite, TypeScript, React Router** | Builds to static files that FastAPI serves, so the whole app is one deployable unit |
| Text-to-speech | **Browser `speechSynthesis`** | Free, works offline, and uses whatever voices the device has installed |
| Packaging | **Docker** (multi-stage), **Docker Compose** for local Postgres | Reproducible builds; same image locally and in production |
| Hosting | **Render** (Blueprint: web service + Postgres) | Free tier, supports WebSockets, HTTPS and custom domains, deploys from GitHub |

The frontend has **no runtime dependencies beyond React and React Router**. Mic capture, resampling, WebSockets, speech synthesis, dialogs (`<dialog>`), date formatting (`Intl`) and language names (`Intl.DisplayNames`) all use built-in browser APIs. Styling is plain CSS with design tokens.

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # dependency wiring: owner id, services, STT provider, rate limiter
│   │   │   └── routes/
│   │   │       ├── transcriptions.py  # REST CRUD
│   │   │       └── live.py            # WebSocket audio proxy
│   │   ├── core/
│   │   │   ├── config.py            # settings from env / backend/.env (required values fail fast)
│   │   │   ├── owner.py             # anonymous owner cookie middleware
│   │   │   ├── rate_limit.py        # live-session limiter
│   │   │   └── exceptions.py        # domain errors → 404 / 422
│   │   ├── db/session.py            # engine, session, get_db
│   │   ├── models/                  # SQLAlchemy models
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── repositories/            # all SQL, owner-scoped
│   │   ├── services/                # business rules
│   │   ├── stt/
│   │   │   ├── base.py              # provider interface (Strategy), TranscriptEvent, SpeechToTextError
│   │   │   ├── factory.py           # picks the provider from STT_PROVIDER
│   │   │   └── gemini_live.py       # Gemini adapter + error mapping
│   │   └── main.py                  # app setup, middleware, static frontend
│   ├── alembic/versions/            # 0001 create table, 0002 add owner_id
│   ├── tests/                       # pytest suite
│   ├── requirements.txt             # pinned runtime dependencies
│   ├── requirements-dev.txt         # + pytest, httpx
│   └── .env.example
├── frontend/
│   ├── public/
│   │   ├── pcm-recorder.worklet.js  # audio-thread resampler
│   │   └── favicon.svg
│   └── src/
│       ├── api/                     # typed HTTP client
│       ├── audio/micCapture.ts      # mic + AudioContext + worklet lifecycle
│       ├── hooks/                   # all stateful logic (live session, history, speech, theme, toasts)
│       ├── components/              # Layout, Logo, Icon, dialogs, Highlight, session provider
│       ├── pages/                   # RecordPage, DashboardPage (render only)
│       ├── lib/                     # language and time helpers
│       └── styles.css               # design tokens, light + dark themes
├── Dockerfile                       # builds the frontend, then serves it from the Python image
├── docker-compose.yml               # local Postgres (and optionally the app)
└── render.yaml                      # Render Blueprint
```

---

## Getting started

### Prerequisites

- **Python 3.13**, **Node 22**, **Docker** (for PostgreSQL)
- A **Gemini API key**, free from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Database

```bash
docker compose up -d db
```

Postgres 17 is exposed on host port **5433**, so it doesn't clash with a locally installed Postgres on 5432.

### 2. Backend

```bash
cd backend
cp .env.example .env                # set GEMINI_API_KEY (see Configuration)
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload       # http://localhost:8000, API docs at /docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

Vite proxies `/api` and `/ws` to `localhost:8000`, so the app uses the same relative URLs in development and production, and no CORS setup is needed. The microphone works on `localhost` without HTTPS.

### Everything in containers

```bash
docker compose up --build           # http://localhost:8000
```

The app container builds the frontend, runs migrations on start and serves everything on one port. It reads `backend/.env` for the Gemini key.

---

## Configuration

All environment-specific settings come from environment variables, or from `backend/.env` locally. **There are no hardcoded fallbacks:** if a required variable is missing, the app refuses to start and names it.

| Variable | Required | Example | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg://postgres:postgres@localhost:5433/speech_to_text` | Render's `postgres://` URLs are converted automatically |
| `STT_PROVIDER` | yes | `gemini` | Speech-to-text implementation (Strategy) |
| `GEMINI_API_KEY` | yes | — | Server-side only; never sent to the browser |
| `GEMINI_MODEL` | yes | `gemini-3.5-transcribe-live` | Live transcription model |
| `STT_MODE` | yes | `VERBATIM` | `VERBATIM` keeps every word; `SMART` removes fillers and formats |
| `STT_LANGUAGES` | no | *(empty)* | Comma-separated BCP-47 hints, e.g. `hi-IN,en-IN`. **Empty = automatic detection** (recommended; it handles code-switching) |
| `CORS_ORIGINS` | no | *(empty)* | Only needed if a different origin calls the API. Empty = same origin only |

`backend/.env` is git-ignored; `backend/.env.example` documents every variable.

---

## API reference

Interactive OpenAPI docs: **`/docs`**. All `/api/transcriptions` endpoints are **scoped to the caller's anonymous owner cookie** (see [Privacy](#privacy-security-and-abuse-protection)).

| Method | Path | Description | Responses |
|---|---|---|---|
| `GET` | `/api/health` | Liveness check (used by Render) | `200 {"status":"ok"}` |
| `GET` | `/api/transcriptions?search=&page=&size=` | Your transcriptions, newest first. Case-insensitive search over title and text. `page` ≥ 1, `size` 1–100 (default 20) | `200` page object |
| `POST` | `/api/transcriptions` | Create. `title` is generated from the first 8 words if omitted | `201`, `422` blank text or bad input |
| `GET` | `/api/transcriptions/{id}` | Read one | `200`, `404` |
| `PUT` | `/api/transcriptions/{id}` | Partial update; only fields sent are changed | `200`, `404`, `422` |
| `DELETE` | `/api/transcriptions/{id}` | Delete | `204`, `404` |
| `WS` | `/ws/transcribe` | Live transcription | See [protocol](#websocket-protocol--wstranscribe) |

**Create / update body**

```json
{
  "title": "Standup notes",
  "text": "Aaj ka standup 10 baje hai",
  "languages": "hi,en",
  "duration_sec": 42
}
```

`languages` is a comma-separated list of ISO 639 primary language codes (`^[a-z]{2,3}(,[a-z]{2,3})*$`, up to 50 characters); malformed values return `422`.

**List response**

```json
{
  "items": [
    {
      "id": 7,
      "title": "Standup notes",
      "text": "Aaj ka standup 10 baje hai",
      "languages": "hi,en",
      "duration_sec": 42,
      "created_at": "2026-10-23T09:41:00Z",
      "updated_at": "2026-10-23T09:41:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20
}
```

---

## Data model

```sql
CREATE TABLE transcriptions (
  id            SERIAL PRIMARY KEY,
  owner_id      VARCHAR(64)  NOT NULL,          -- SHA-256 of the browser's owner cookie
  title         VARCHAR(200) NOT NULL,          -- generated from the text if not given
  text          TEXT         NOT NULL,
  languages     VARCHAR(50),                    -- e.g. "hi,en,ml"
  duration_sec  INTEGER,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_transcriptions_owner_created ON transcriptions (owner_id, created_at);
```

Every query filters by `owner_id` and sorts by `created_at`, which is what the composite index serves. Schema changes are versioned with Alembic (`backend/alembic/versions`) and applied automatically when the container starts.

---

## Privacy, security and abuse protection

**Private history without accounts.**
- On the first visit, the server issues a random 256-bit token in a `vaani_owner` cookie: `HttpOnly` (not readable by scripts), `SameSite=Lax`, `Secure` over HTTPS, valid for one year.
- Records store only the token's **SHA-256 hash**, so a database leak doesn't expose usable cookies.
- Every repository query is filtered by owner. Another owner's record ID returns **404, not 403**, so IDs reveal nothing.

**API key protection.** The Gemini key lives only on the server. All audio is proxied, and the browser never talks to Google directly.

**Rate limiting.** Live sessions use the speech-to-text quota, so they are limited:

| Scope | Concurrent sessions | Sessions per hour |
|---|---|---|
| Per browser (owner cookie) | 1 | 20 |
| Per IP (offices and NAT share an IP) | 3 | 60 |
| Whole app | 10 | — |

A rejected session gets a clear message ("A recording is already running in another tab…", "You've reached 20 recordings this hour…") and the UI shows **"Couldn't start"**. The global cap is the hard bound; per-client keys are best effort.

**Safe error messages.** Provider failures are mapped to plain messages: quota or exhausted credits → "Vaani has reached its transcription limit for now…"; anything else → "Transcription is unavailable right now…". Raw exception text is never sent to the client; details go to the server log only.

**Other hardening**
- Pydantic validation on all inputs, including length limits and the language-code format.
- A path-traversal guard on static file serving.
- Required configuration is validated at startup.
- Direct Python dependencies are pinned; the frontend is locked by `package-lock.json`.

---

## Testing

```bash
cd backend
pytest
```

**29 tests** cover:

- **CRUD:** create, generated titles, blank-text rejection, read and 404, search (including Devanagari) and pagination, partial update, delete.
- **Privacy:** cookie issued once with `HttpOnly` and `SameSite`, invalid cookies replaced, another browser gets 404 on read, update and delete and sees an empty list.
- **Live WebSocket:** full `ready → interim/final → done` flow with a fake provider, and rejection after the hourly limit.
- **Rate limiter:** concurrent and hourly limits, window reset, shared IP, global cap, release on error (fake clock).
- **Error mapping:** Gemini quota, credit, auth and network errors → user-safe messages; internal details never reach the client.
- **Multilingual:** any valid language codes accepted, malformed ones rejected, `language` carried over the WebSocket.
- **Static serving:** hashed assets are cached immutably and gzipped; `index.html` and client routes are revalidated.

Tests use in-memory SQLite and a fake STT provider, injected through FastAPI dependency overrides, so they need **no database, network or API key**. Frontend type checking runs as part of `npm run build` (`tsc -b`).

---

## Deployment

### Render (Blueprint)

1. Push the repository to GitHub.
2. In Render: **New → Blueprint**, then select the repository. `render.yaml` creates:
   - **`vaani`**: a Docker web service (free plan), health-checked at `/api/health`
   - **`vaani-db`**: a PostgreSQL database (free plan), wired in as `DATABASE_URL`
3. Enter **`GEMINI_API_KEY`** when prompted. The other settings are defined in `render.yaml`.

On start, the container runs `alembic upgrade head` and then uvicorn on `$PORT` with `--proxy-headers`, so the app sees the real client IP and HTTPS scheme.

**No nginx needed.** Render's proxy handles TLS, the HTTP→HTTPS redirect, WebSocket upgrades and forwarding headers. The app itself compresses responses (gzip) and sets cache headers: Vite's content-hashed `assets/*` are cached for a year (`immutable`), while `index.html` and other files are revalidated, so new deploys appear immediately.

### Custom domain

1. Render → web service → **Settings → Custom Domains → Add** your subdomain, e.g. `app.example.com`.
2. At the DNS provider, add a `CNAME` record: name `app`, target the service's `*.onrender.com` host.
3. Click **Verify** in Render. The TLS certificate is issued automatically.

### Cost controls

- Use a Gemini API key whose usage you control. Lowering the API's **per-minute and per-day quotas** in Google Cloud is a hard cap; budgets only send alerts.
- The app's rate limiter caps concurrent and hourly sessions.

---

## Design decisions

| Decision | Reason |
|---|---|
| **Layered backend** (router → service → repository → model) | Each layer has one job. Routes only handle HTTP, services hold the rules, repositories are the only SQL |
| **Strategy + Adapter + Factory** for speech-to-text | The WebSocket route depends only on an interface, so swapping Gemini for e.g. self-hosted Whisper means adding one class and changing `STT_PROVIDER` |
| **Dependency injection** (`Depends`) | Tests replace the database, provider and limiter without touching application code |
| **Vite SPA served by FastAPI** (not Next.js) | One container, one URL, no CORS. Serverless platforms can't hold long-lived WebSockets, and SSR adds nothing for a mic app |
| **Backend audio proxy** | Keeps the API key off the client and allows rate limiting and error mapping |
| **Auto-detect languages** instead of fixed hints | Code-switching works out of the box; the model reports the language per segment |
| **Session state above the routes** (React context) | Recording and auto-save survive page navigation |
| **Anonymous cookie ownership** instead of login | Private history with no sign-up friction for a demo; real accounts are the natural next step |
| **In-memory rate limiter** | Fits a single instance with zero extra infrastructure; Redis would be the multi-instance upgrade |

---

## Known limitations

- **Session length:** Gemini Live sessions are limited to about 10 minutes of continuous audio. Text captured up to that point is kept and saved; automatic reconnection is not implemented.
- **Script choice is the model's:** mixed Hindi and English usually comes out romanized (Hinglish), while Malayalam and most other languages stay in their native script even when mixed with English.
- **Language fallback:** if the model reports no language, it is guessed from the script, which can't distinguish languages that share one (e.g. Hindi and Marathi).
- **Text-to-speech** depends on the voices installed on the device; without a matching voice the browser default is used.
- **History is per browser:** clearing cookies or switching device starts an empty history.
- **Rate limits** are in memory: they reset on restart and aren't shared across instances.
- **Free tiers:** Render's free service sleeps when idle (~30 s cold start). On the Gemini API free tier, Google may use submitted content to improve its products, so avoid recording anything sensitive.
- **Browser requirements:** microphone access needs HTTPS (or `localhost`) and a browser with `AudioWorklet` support (all current major browsers).
