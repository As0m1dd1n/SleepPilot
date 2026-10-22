# SleepPilot

SleepPilot is a sleep diary and habit analysis app for students. It tracks sleep, caffeine, screen time, activity, and mood, then turns the history into understandable insights and personalized sleep-hygiene suggestions.

## Run with Docker

```bash
docker compose up --build
```

Open http://localhost:5173. The API is available at http://localhost:8000/docs.

## Local development

### Backend

PostgreSQL is required:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://sleeppilot:sleeppilot@localhost:5432/sleeppilot
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The first API request creates a demo profile when no profile exists. AI recommendations use deterministic local rules by default; an LLM provider can be added behind `RecommendationService` without changing the API.

## Vercel deployment

The repository includes a root `vercel.json` with two services:

- `frontend` — public Vite application.
- `backend` — FastAPI service exposed publicly through the `/api/*` rewrite.

The frontend uses `/api` in production, so both services share one Vercel domain. Configure `DATABASE_URL` and `CORS_ORIGINS` in the Vercel project environment. No service binding is currently required because the frontend calls the backend from the browser through the public `/api` route, and the backend does not call another service.

For Vercel, use an external managed PostgreSQL database. The local Docker PostgreSQL container is for development only and is not reachable from Vercel. Set `DATABASE_URL` to the provider's PostgreSQL connection string and set `CORS_ORIGINS` to the Vercel deployment URL.
