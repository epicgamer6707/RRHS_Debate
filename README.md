---
title: RRHS Debate
emoji: 🐉
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8080
pinned: false
---

# RRHS Debate

Team workspace for the Round Rock High School debate team: dashboard + stats,
Card Finder / Card Analyzer / Citation Maker, a per-user Library, competition
sign-up, and a Classroom board.

Runs as a Docker app. On Hugging Face Spaces it uses an external Postgres
database (Supabase) via the `DATABASE_URL` secret. See `.env.example` for the
full list of environment variables/secrets.
