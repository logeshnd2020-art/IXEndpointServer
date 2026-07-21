# AGENTS.md — AI coding agent instructions

Purpose
-------
Provide a short, actionable orientation for AI coding agents working on this repository.

Quick start (what an agent needs to know)
---------------------------------------
- **Run (dev)**: The project is a FastAPI app. A common local run command is:

  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

- **Dependencies**: See [requirements.txt](requirements.txt#L1-L30).
- **DB / Migrations**: Alembic migrations live in [alembic/versions](alembic/versions). See [alembic/README](alembic/README) for migration notes.

Key files and locations
-----------------------
- **Application entry**: [app/main.py](app/main.py#L1-L40)
- **API routers**: [app/api](app/api)
- **Models (ORM)**: [app/models](app/models)
- **DB (SQLAlchemy)**: [app/core/database.py](app/core/database.py#L1-L60)
- **Simple sqlite initializer**: [database.py](database.py#L1-L200)
- **Services / Repositories**: [services](services) and [repositories](repositories)
- **Migrations**: [alembic](alembic)
- **Runtime folder**: [runtime/database](runtime/database) (used by `database.py`)

Conventions & architecture notes
-------------------------------
- The code separates `api` (FastAPI routers), `services` (business logic), `repositories` (DB access), and `models` (ORM/schema). Prefer making changes in the smallest focused layer.
- Use Alembic for schema migrations rather than manual table edits where SQLAlchemy models are used.
- There are two DB approaches in the repo: a simple `database.py` that creates an sqlite file under `runtime/database`, and a SQLAlchemy-based setup in `app/core/database.py` driven by `DATABASE_URL` from `app/core/config.py`.

How the agent should behave
--------------------------
- Be minimal and link to existing docs rather than copying large blocks. When modifying code, create focused changes with tests when possible.
- For any DB schema work, prefer adding an Alembic migration. Ask before applying destructive changes to production data.
- If you need to run or modify the server, use the `uvicorn` command above unless the user provides an alternative.

Next recommended customizations
------------------------------
- Add a short `/.github/copilot-instructions.md` pointing to this file if you want organization-wide GitHub AI hints.
- Consider a small skill to automate common tasks: `create-migration`, `run-server`, and `list-endpoints`.

If anything here is incorrect or you want the agent to follow stricter rules (tests required, commit message style, etc.), tell me what to add or change.
