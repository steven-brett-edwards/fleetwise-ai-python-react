"""End-to-end CLI test -- subprocess invocation of fleetwise-etl ingest --json.

Uses ``--db-url`` to point at a one-shot SQLite file under tmp_path so
the test is fully isolated from the dev DB.

Two flavors of test:

- subprocess via ``python -m fleetwise.etl.cli`` for the full real-world
  flow (argv parsing, async runner, print output);
- in-process via ``cli.main([...])`` so coverage actually tracks the
  branches we exercise.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from fleetwise.etl import cli


def test_cli_ingest_emits_structured_json_and_exits_zero(tmp_path: Path) -> None:
    csv = tmp_path / "input.csv"
    csv.write_text(
        textwrap.dedent("""\
            asset_number,inspected_at,inspector_name,mileage,passed,findings
            V-2020-0015,2026-03-15,Maria Alvarez,49100,Pass,Routine inspection.
        """)
    )
    db_path = tmp_path / "scratch.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "fleetwise.etl.cli",
            "ingest",
            str(csv),
            "--db-url",
            db_url,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload["totals"]["loaded"] == 1
    assert payload["totals"]["rejected"] == 0
    [file_report] = payload["files"]
    assert file_report["rows_total"] == 1


def test_cli_ingest_in_process_human_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cover the human-readable print path. Same flow, no subprocess."""
    csv = tmp_path / "input.csv"
    csv.write_text(
        "asset_number,inspected_at,inspector_name,mileage,passed,findings\n"
        "V-2020-0015,2026-03-15,Maria Alvarez,49100,Pass,Routine.\n"
    )
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'scratch.db'}"

    rc = cli.main(["ingest", str(csv), "--db-url", db_url])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ETL ingest report" in out
    assert "rows loaded      : 1" in out
    assert "Totals: loaded=1" in out


def test_cli_ingest_in_process_json_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON output path. Same as the subprocess test, but in-process."""
    csv = tmp_path / "input.csv"
    csv.write_text(
        "asset_number,inspected_at,inspector_name,mileage,passed,findings\n"
        "V-2020-0015,2026-03-15,Maria Alvarez,49100,Pass,Routine.\n"
    )
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'scratch.db'}"

    rc = cli.main(["ingest", str(csv), "--db-url", db_url, "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["totals"]["loaded"] == 1


def test_cli_no_matching_paths_in_process(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(["ingest", str(tmp_path / "nope-*.csv")])
    err = capsys.readouterr().err
    assert rc == 1
    assert "No matching files" in err


def test_cli_ingest_with_no_matching_paths_exits_one(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "fleetwise.etl.cli",
            "ingest",
            str(tmp_path / "nope-*.csv"),
            "--db-url",
            f"sqlite+aiosqlite:///{tmp_path / 'scratch.db'}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "No matching files" in proc.stderr
