# APRS — Autonomous Product Research System Frontend

Modern desktop web application for APRS V6 Pro, built with Next.js (App Router), React, TypeScript, and Tailwind CSS.

## Architecture

```
Next.js Frontend (Port 3000)
    ↓  (HTTP REST)
FastAPI Backend (Port 8000)
    ↓
Python Business Logic & Engines
    ↓
SQLite Database (data/research_engine.db)
```

## Access Model

APRS is an unauthenticated, free direct-access product.
- No login or registration
- No auth tokens or sessions
- No paywalls or subscriptions
- Instant direct access to all evaluation data

## Running the Frontend

```bash
# Install dependencies
npm install

# Start local development server
npm run dev

# Or build and start production server
npm run build
npm run start
```

Default local address: [http://localhost:3000](http://localhost:3000)  
FastAPI backend required at: [http://localhost:8000](http://localhost:8000)
