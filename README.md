# Student Analytics System (کارنامه)

A web app for managing student records, grades (out of 20) and attendance, with a dashboard that turns the data into charts and simple, explainable insights.

## Features
- Student CRUD with search, class filter and sorting by name, class or average
- Grades per subject and date; scores validated to 0–20 in the API **and** the database
- Attendance recorded per class and day (one record per student per day, enforced by a unique constraint)
- Dashboard: subject and class averages, term trend, grade distribution, attendance breakdown, students needing attention
- Per-student report: subject trends and plain-language findings
- Persian (RTL) interface, responsive down to mobile

## Stack
Python, FastAPI, SQLAlchemy, MySQL (SQLite works with no setup), HTML/CSS/JavaScript, Chart.js.

## Run it
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd backend
python -m app.seed                  # optional: synthetic demo data
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 (interactive API docs at `/docs`).

To use MySQL, copy `.env.example` to `.env`, create an empty database (`CREATE DATABASE student_analytics CHARACTER SET utf8mb4;`) and set `DATABASE_URL`. Tables are created on startup.

## Tests
```bash
cd backend && pytest
```
Tests run against an in-memory SQLite database and cover validation, duplicates, 404s, attendance upsert, empty-database statistics and trend detection.

## Architecture
Browser (`frontend/`) → JSON over `/api` → FastAPI routes (`app/main.py`) → SQLAlchemy models (`app/models.py`) → MySQL/SQLite.
Read-only statistics live in `app/analytics.py`; the server also serves the static frontend.

Tables: `students`, `subjects`, `grades` (FK to student and subject, `CHECK 0 ≤ score ≤ 20`), `attendance` (FK to student, `UNIQUE(student_id, day)`, status in present/late/absent).

## Design decisions
- "Late" counts as attending when computing attendance rate.
- No averages are shown when there is no data (the API returns `null`).
- Trend findings need at least 3 grades per subject and use a least-squares slope; they are descriptive, not predictions.

## Current limitations
- No login or user roles yet; do not expose it publicly with real student data.
- No machine learning yet. The insights are simple statistics.
- Demo data is synthetic.

## Roadmap
Authentication and roles → CSV import/export → evaluated ML model (pandas + scikit-learn) with reported error and limits.
