import pytest

from bleeper import settings

VARS = ("BLEEPER_MODEL", "BLEEPER_UI_HOST", "BLEEPER_UI_PORT", "BLEEPER_UI_MAX_UPLOAD_MB")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    assert settings.default_model() == "small"
    assert settings.ui_host() == "127.0.0.1"
    assert settings.ui_port() == 7860
    assert settings.max_upload_mb() == 100


def test_values_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLEEPER_MODEL", "base")
    monkeypatch.setenv("BLEEPER_UI_HOST", "0.0.0.0")
    monkeypatch.setenv("BLEEPER_UI_PORT", "8080")
    monkeypatch.setenv("BLEEPER_UI_MAX_UPLOAD_MB", "5")
    assert settings.default_model() == "base"
    assert settings.ui_host() == "0.0.0.0"
    assert settings.ui_port() == 8080
    assert settings.max_upload_mb() == 5


def test_empty_strings_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLEEPER_MODEL", "")
    monkeypatch.setenv("BLEEPER_UI_HOST", "")
    assert settings.default_model() == "small"
    assert settings.ui_host() == "127.0.0.1"


@pytest.mark.parametrize("value", ["abc", "0", "65536"])
def test_bad_port(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("BLEEPER_UI_PORT", value)
    with pytest.raises(settings.SettingsError, match="BLEEPER_UI_PORT.*1–65535"):
        settings.ui_port()


@pytest.mark.parametrize("value", ["0", "-1", "x"])
def test_bad_upload_limit(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("BLEEPER_UI_MAX_UPLOAD_MB", value)
    with pytest.raises(settings.SettingsError, match="BLEEPER_UI_MAX_UPLOAD_MB.*an integer ≥ 1"):
        settings.max_upload_mb()
