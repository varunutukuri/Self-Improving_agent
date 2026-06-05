# Self-Improving Agent

## Quick Start

1. Copy env file: `cp backend/.env.example backend/.env` — fill in your values
2. Start services: `docker compose up --build`
3. Open: `http://localhost:5173`

## Local Dev (no Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## Run Tests

```bash
cd backend
pytest tests/ -v
```
