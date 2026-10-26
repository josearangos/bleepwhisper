import json
from pathlib import Path

from bleeper.core.models import ReportEntry, Span
from bleeper.core.report import to_report, write_report

SCHEMA = Path(__file__).parents[2] / "specs/001-cli-word-masking/contracts/report-schema.json"


def test_to_report_joins_words_and_rounds_times() -> None:
    spans = [Span(30720, 41280, ("heck",)), Span(65601, 80480, ("shut up", "darn"))]
    assert to_report(spans, 16000) == [
        ReportEntry("heck", 1.92, 2.58),
        ReportEntry("shut up darn", 4.1, 5.03),
    ]


def test_to_report_orders_by_start() -> None:
    entries = to_report([Span(200, 300, ("b",)), Span(0, 100, ("a",))], 1000)
    assert [e.word for e in entries] == ["a", "b"]


def assert_matches_schema(data: object) -> None:
    item_schema = json.loads(SCHEMA.read_text(encoding="utf-8"))["items"]
    assert isinstance(data, list)
    for item in data:
        assert set(item) == set(item_schema["required"])
        assert isinstance(item["word"], str)
        assert 0 <= item["start"] < item["end"]


def test_write_report_matches_schema_and_keeps_unicode(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    write_report(path, [ReportEntry("señor", 1.92, 2.58)])
    text = path.read_text(encoding="utf-8")
    assert "señor" in text
    data = json.loads(text)
    assert data == [{"word": "señor", "start": 1.92, "end": 2.58}]
    assert_matches_schema(data)
    assert list(tmp_path.iterdir()) == [path]


def test_write_report_empty_and_replaces_existing(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text("old", encoding="utf-8")
    write_report(path, [])
    assert json.loads(path.read_text(encoding="utf-8")) == []
    assert list(tmp_path.iterdir()) == [path]
