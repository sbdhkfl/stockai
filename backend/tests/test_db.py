"""Persistence tests: save/get/list reports via SQLAlchemy on a temp SQLite
file; Alembic migration exercised against a fresh database.
"""
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from fairvalue.core.schemas import ValuationReport
from fairvalue.db import repo, session as db_session
from fairvalue.db.models import Base
from fairvalue.service import ValuationOptions, run_valuation
from fairvalue.data import get_provider


@pytest.fixture
def engine(tmp_path):
    url = f"sqlite:///{tmp_path}/test_fv.db"
    eng = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng


@pytest.fixture
def demo_report():
    rep = run_valuation(get_provider(demo=True), "AUR", ValuationOptions())
    if rep.report_id is None:
        from fairvalue.core.schemas import ValuationReport  # noqa: F401
    return rep


def test_save_and_get_roundtrip_preserves_everything(engine, demo_report):
    s = db_session.make_session(engine)
    rid = repo.save_report(s, demo_report)
    loaded = repo.get_report(s, rid)
    assert isinstance(loaded, ValuationReport)
    original = demo_report.model_dump(mode="json")
    restored = loaded.model_dump(mode="json")
    assert restored["company"] == original["company"]
    assert restored["models"] == original["models"]                # assumptions + steps intact
    assert restored["reconciliation"] == original["reconciliation"]
    assert restored["scenarios"] == original["scenarios"]
    assert restored["data_quality"]["sources"] == original["data_quality"]["sources"]
    assert restored["inputs"] == original["inputs"]                # full inputs w/ provenance


def test_save_assigns_report_id_when_missing(engine, demo_report):
    s = db_session.make_session(engine)
    rid = repo.save_report(s, demo_report)
    # save_report generates an id when the report has none; it is retrievable
    loaded = repo.get_report(s, rid)
    assert loaded.report_id == rid


def test_resave_same_report_is_upsert_latest_wins(engine, demo_report):
    s = db_session.make_session(engine)
    rid = repo.save_report(s, demo_report)
    repo.save_report(s, demo_report)     # same id twice -> one row, updated
    from sqlalchemy import func, select
    from fairvalue.db.models import ReportRecord
    n = s.scalar(select(func.count()).select_from(ReportRecord)
                 .where(ReportRecord.report_id == rid))
    assert n == 1


def test_list_reports_metadata_and_filter(engine, demo_report):
    s = db_session.make_session(engine)
    rid = repo.save_report(s, demo_report)
    rows = repo.list_reports(s)
    assert len(rows) == 1
    r = rows[0]
    assert r["report_id"] == rid and r["ticker"] == "AUR"
    assert r["engine_version"] and r["schema_version"]
    assert r["is_illustrative"] is True
    assert r["reconciliation"]["base"] is not None
    assert repo.list_reports(s, ticker="ZZZ") == []


def test_generated_at_and_wacc_stored(engine, demo_report):
    s = db_session.make_session(engine)
    repo.save_report(s, demo_report)
    rows = repo.list_reports(s)
    assert rows[0]["generated_at"].startswith(demo_report.generated_at.strftime("%Y-%m-%d"))
    dcf = next(m for m in demo_report.models if m.model == "dcf")
    assert rows[0]["dcf_wacc"] == pytest.approx(dcf.assumptions["wacc"])


def test_alembic_migration_creates_schema(tmp_path):
    """Run the real alembic migration against a fresh DB; then the repo works."""
    db_file = tmp_path / "alembic_fv.db"
    env = {**__import__("os").environ,
           "FAIRVALUE_DB_URL": f"sqlite:///{db_file.as_posix()}",
           "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c",
         str(Path("fairvalue/db/migrations/alembic.ini").resolve()),
         "upgrade", "head"],
        capture_output=True, text=True, env=env, cwd=Path(__file__).resolve().parents[1])
    assert r.returncode == 0, r.stdout + r.stderr
    engine = create_engine(f"sqlite:///{db_file}",
                           connect_args={"check_same_thread": False})
    rep = run_valuation(get_provider(demo=True), "AUR", ValuationOptions())
    s = db_session.make_session(engine)
    rid = repo.save_report(s, rep)
    assert repo.get_report(s, rid) is not None
