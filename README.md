# ISPBora

ISPBora is an operations console for ISP staff. Operators use it to watch service areas, work support cases, follow incidents, and ask an internal assistant about live network data.

The dashboard is for ISP operators. It is not a customer portal and it does not store billing balances, invoices, or M-Pesa transactions.

## What is included

- Network overview, subscribers, support cases, and a service-area map
- Incident acknowledgement, technician assignment, customer notification, and resolution
- Africa's Talking USSD callback and SMS notices for affected subscribers
- An operator assistant that reads and updates ISPBora data through controlled tools

The assistant can look up subscribers, incidents, and support cases, find technicians who are currently available, and assign an open incident. It keeps the recent conversation so a follow-up such as “assign this” refers to the incident just discussed. Starting a new chat clears that memory.

## Stack

| Part | Technology |
| --- | --- |
| Dashboard | React, TypeScript, Vite, Tailwind CSS |
| API | Django, Django REST Framework |
| Local database | SQLite |
| Assistant | LangGraph and Groq |
| Messaging | Africa's Talking USSD and SMS |

## Requirements

- Python 3.12 or newer
- Node.js 20 or newer

## Run locally

Use two terminals from the repository root.

### API

Windows:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

macOS or Linux:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

The API is at `http://127.0.0.1:8000/`. `seed_demo` replaces previously seeded operational data.

### Dashboard

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:5173/dashboard`. The dashboard calls `http://127.0.0.1:8000` unless `VITE_API_BASE_URL` is set.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Do not commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django secret. Use a long random value outside local development. |
| `DJANGO_DEBUG` | `True` for local development. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts. |
| `DB_ENGINE` | Local development uses SQLite. |
| `DB_NAME` | Optional SQLite path. Empty uses `backend/db.sqlite3`. |
| `CORS_ALLOWED_ORIGINS` | Frontend origins, including Vite on port 5173. |
| `AFRICASTALKING_USERNAME` | Sandbox username for SMS. |
| `AFRICASTALKING_API_KEY` | Sandbox API key. Leave the sender ID empty unless the sandbox requires one. |
| `GROQ_API_KEY` | Groq key for the operator assistant. It stays on the server. |
| `GROQ_MODEL` | Groq model id, for example `llama-3.3-70b-versatile`. |

The dashboard still runs when the Groq values are empty. The assistant then reports that it is not configured.

Optional map tiles:

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | API origin. Defaults to `http://127.0.0.1:8000`. |
| `VITE_MAP_STREET_URL` | Street tile URL. |
| `VITE_MAP_SATELLITE_URL` | Satellite tile URL. |

## Operator assistant

`POST /api/ai/assistant/` accepts `{ "message": "...", "channel": "dashboard" }` and an optional `history` of recent turns. The model can call Django tools. It does not write to the database directly.

Available tools cover subscriber lookup, subscriber context, active incidents, open support cases, support-case creation, customer notification, incident and support summaries, technician availability, incident assignment context, and assignment. A technician is available only when their status is `AVAILABLE`. An incident that already has a technician is not replaced unless the operator asks to reassign.

## Checks

```bash
cd backend
python manage.py check
python manage.py test
```

From the repository root:

```bash
npx tsc --noEmit
npm run build
```

## Project layout

```text
src/                 React dashboard
backend/             Django API, USSD callback, and assistant
backend/apps/ai/     LangGraph assistant, tools, and tests
backend/.env.example Environment template
```

API paths, SMS setup, and incident actions are documented in [backend/README.md](backend/README.md).

## Local access

The API currently allows unauthenticated requests so the console can be used in local development. Do not expose it on a public network without authentication.
