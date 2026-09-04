import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parent.parent

PRIOR_HEAD_REVISION = "0c1a1d4a40c0"  # head before this fix
DURATION_REVISION = "c3a9f1e2b4d6"  # add_duration_seconds_to_sessions


def _alembic_config(db_path):
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(REPO_ROOT / "alembic"),
    )
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{db_path}",
    )
    return config


def _columns(db_path, table):
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        conn.close()
    return {row[1]: row for row in rows}  # name -> (cid, name, type, notnull, default, pk)


def test_migration_adds_nullable_duration_seconds_column(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_fresh.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    config = _alembic_config(db_path)
    command.upgrade(config, "head")

    columns = _columns(db_path, "sessions")

    assert "duration_seconds" in columns
    _, _, col_type, notnull, _, _ = columns["duration_seconds"]
    assert col_type.upper() == "INTEGER"
    assert notnull == 0  # nullable


def test_migration_preserves_existing_session_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_preserve.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    config = _alembic_config(db_path)

    # Build the schema as it existed before this fix, then seed data,
    # mirroring the real production database's current state.
    command.upgrade(config, PRIOR_HEAD_REVISION)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO devices (id, hostname, serial_number, username, is_registered) "
            "VALUES (1, 'test-mac', 'SERIAL-XYZ', 'jdoe', 0)"
        )
        conn.execute(
            "INSERT INTO sessions "
            "(id, device_id, local_session_id, username, login_time, logout_time, status) "
            "VALUES (1, 1, 1, 'jdoe', '2026-09-01 09:00:00', '2026-09-01 17:00:00', 'LOGOUT')"
        )
        conn.commit()
    finally:
        conn.close()

    command.upgrade(config, "head")

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT id, device_id, username, login_time, logout_time, status, duration_seconds "
            "FROM sessions WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        1,
        1,
        "jdoe",
        "2026-09-01 09:00:00",
        "2026-09-01 17:00:00",
        "LOGOUT",
        None,
    )


def test_migration_is_idempotent_when_column_already_present(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_idempotent.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    config = _alembic_config(db_path)

    # Get to the schema state just before this fix, then simulate the
    # column already having been added out-of-band (e.g. a prior partial
    # run, or a hand patch) without alembic's version table knowing.
    command.upgrade(config, PRIOR_HEAD_REVISION)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO devices (id, hostname, serial_number, username, is_registered) "
            "VALUES (1, 'test-mac', 'SERIAL-XYZ', 'jdoe', 0)"
        )
        conn.execute(
            "INSERT INTO sessions "
            "(id, device_id, local_session_id, username, login_time, status) "
            "VALUES (1, 1, 1, 'jdoe', '2026-09-01 09:00:00', 'ACTIVE')"
        )
        conn.execute(
            "ALTER TABLE sessions ADD COLUMN duration_seconds INTEGER"
        )
        conn.commit()
    finally:
        conn.close()

    # Must not raise "duplicate column name" even though the column is
    # already there -- this is the idempotency guarantee.
    command.upgrade(config, "head")

    columns = _columns(db_path, "sessions")
    assert "duration_seconds" in columns

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT id, username, status, duration_seconds FROM sessions WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()

    assert row == (1, "jdoe", "ACTIVE", None)


def test_downgrade_then_upgrade_round_trip(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_roundtrip.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    config = _alembic_config(db_path)
    command.upgrade(config, "head")
    assert "duration_seconds" in _columns(db_path, "sessions")

    command.downgrade(config, PRIOR_HEAD_REVISION)
    assert "duration_seconds" not in _columns(db_path, "sessions")

    command.upgrade(config, "head")
    assert "duration_seconds" in _columns(db_path, "sessions")
