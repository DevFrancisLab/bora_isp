# ISPBora backend

Django and Django REST Framework API for the ISPBora operations console. The React dashboard in the repository root uses this API. Setup for the whole project is in the root [README](../README.md).

## Setup

From the repository root:

```bash
cd backend
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Environment variables

Copy `backend/.env.example` to `backend/.env`. Do not commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django secret. Use a long random value outside local development. |
| `DJANGO_DEBUG` | `True` for local development. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts. |
| `DB_ENGINE` | Local development uses `django.db.backends.sqlite3`. |
| `DB_NAME` | Optional SQLite path. Empty uses `backend/db.sqlite3`. |
| `CORS_ALLOWED_ORIGINS` | Frontend origins, including Vite on port 5173. |
| `GROQ_API_KEY` | Groq API key. Fallback provider for the assistant. Stays on the server. |
| `GROQ_MODEL` | Groq model id, for example `llama-3.3-70b-versatile`. |
| `BASIX_API_KEY` | Primary provider key. Never commit it. |
| `BASIX_BASE_URL` | Defaults to `https://llm.c.singularitynet.io/v1`. |
| `BASIX_MODEL` | Defaults to `qwen/qwen3.8-27b`. `qwen/qwen3.5-35b-a3b` was not served by the endpoint. |
| `BASIX_EMBEDDING_MODEL` | Defaults to `BAAI/bge-base-en-v1.5`. |
| `BASIX_TIMEOUT` | Seconds before a BASIX call is treated as a provider failure. |

Local development uses the SQLite file `backend/db.sqlite3`. Leave `DB_NAME` empty to use that path. Do not delete that file if it already contains demo data.

## Migrations

```bash
python manage.py migrate
```

## Demo data

```bash
python manage.py seed_demo
```

The command replaces previously seeded operational data and prints derived incident counts.

## Development server

```bash
python manage.py runserver
```

The API is served at `http://127.0.0.1:8000/`. Django admin is at `/admin/`.

## Checks and tests

```bash
python manage.py check
python manage.py test
```

## API endpoints

```text
GET    /api/subscribers/
GET    /api/subscribers/{id}/
POST   /api/subscribers/
PATCH  /api/subscribers/{id}/
DELETE /api/subscribers/{id}/

GET    /api/network/areas/
GET    /api/network/sites/
GET    /api/network/status/

GET    /api/support/cases/
GET    /api/support/cases/{id}/
POST   /api/support/cases/
PATCH  /api/support/cases/{id}/

GET    /api/incidents/
GET    /api/incidents/{id}/
POST   /api/incidents/
PATCH  /api/incidents/{id}/
POST   /api/incidents/{id}/acknowledge/
POST   /api/incidents/{id}/assign/
POST   /api/incidents/{id}/notify/
POST   /api/incidents/{id}/resolve/
POST   /api/incidents/simulate/   Demo Mode only. Opens one connectivity incident in a free service area.

GET    /api/messages/
GET    /api/notifications/
GET    /api/technicians/
GET    /api/dashboard/summary/

POST   /api/ai/assistant/        Operator assistant.
POST   /api/ai/customer/         Customer troubleshooting workflow.
POST   /ussd                     Africa's Talking USSD callback. Plain text, no trailing slash.
```

Subscriber search uses `search`. Filters: `status`, `service_area`, `connection_status`.

Support case filters: `status`, `priority`, `category`, `service_area`, `subscriber`, `source`.

Incident actions expect JSON. Assign uses `{"technician_id": 1}`. Notify uses `{"channel": "SMS"}` or `{"channel": "WHATSAPP"}`. Acknowledge and resolve take an empty POST. WhatsApp notices stay queued. SMS notices are sent through Africa's Talking when credentials are configured.

## Africa's Talking SMS setup

USSD stays on `POST /ussd`. SMS uses the same sandbox application, not a second callback.

1. Open the Africa's Talking Sandbox and use the sandbox application.
2. Copy the sandbox username.
3. Generate a sandbox API key.
4. Put those values in `backend/.env`:
   - `AFRICASTALKING_USERNAME`
   - `AFRICASTALKING_API_KEY`
   - `AFRICASTALKING_ENV=sandbox`
   - `AFRICASTALKING_SMS_SENDER_ID` only if the sandbox app requires a sender ID. Leave it empty otherwise.
5. Start Django with `python manage.py runserver 0.0.0.0:8000`.
6. Notify an incident with `POST /api/incidents/{id}/notify/` and `{"channel": "SMS"}`.
7. Resolve it with `POST /api/incidents/{id}/resolve/`. Restoration SMS uses the same affected subscribers.
8. Read `sent`, `failed`, and `skipped` on the notify response, and the Notification rows in the API or admin.
9. Confirm the messages in the Africa's Talking Sandbox SMS simulator. Do not put real credentials in this file.

Authentication and role permissions are not part of this foundation. The API currently allows unauthenticated access so the workflow can be exercised locally.
