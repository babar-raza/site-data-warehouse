import json
import os

import pytest

import bootstrap


def test_bootstrap_happy_path(monkeypatch, tmp_path):
    """Happy path: credentials validate, properties discovered, report written."""
    # Set up a temporary secrets file with minimal JSON content
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    secret_file = secrets_dir / "gsc_sa.json"
    secret_file.write_text("{" + '\n' + "  \"type\": \"service_account\"," + '\n' + "  \"client_email\": \"test@example.com\"" + '\n' + "}")

    # Environment variables to override defaults
    report_root = tmp_path / "out"
    monkeypatch.setenv("GSC_SA_PATH", str(secret_file))
    monkeypatch.setenv("BOOTSTRAP_REPORT_ROOT", str(report_root))

    # Patch credential validation to return a dummy credentials object
    monkeypatch.setattr(
        bootstrap,
        "validate_credentials",
        lambda path: object(),
    )

    # Prepare a fixed list of discovered properties
    discovered = [
        {
            "siteUrl": "https://example.com/",
            "permissionLevel": "siteOwner",
        },
        {
            "siteUrl": "sc-domain:example.net",
            "permissionLevel": "siteOwner",
        },
    ]
    monkeypatch.setattr(
        bootstrap,
        "discover_properties",
        lambda creds: discovered,
    )

    # Execute the script; expect SystemExit with code 0
    with pytest.raises(SystemExit) as excinfo:
        bootstrap.main()
    assert excinfo.value.code == 0

    # Verify report files exist and contents match
    phase_dir = report_root / "phase-0"
    assert phase_dir.is_dir()
    status_path = phase_dir / "status.json"
    properties_path = phase_dir / "properties.json"
    assert status_path.exists()
    assert properties_path.exists()
    status = json.loads(status_path.read_text())
    assert status["num_properties"] == len(discovered)
    props = json.loads(properties_path.read_text())
    assert props == discovered


def test_bootstrap_missing_secret(monkeypatch, tmp_path):
    """Failing path: missing secret file leads to non‑zero exit and no report."""
    # Point to a non‑existent secrets file
    missing_secret = tmp_path / "nope.json"
    monkeypatch.setenv("GSC_SA_PATH", str(missing_secret))
    report_root = tmp_path / "out"
    monkeypatch.setenv("BOOTSTRAP_REPORT_ROOT", str(report_root))

    # Patch google libraries to dummy objects so validate_credentials() checks file existence
    class DummyCreds:
        # minimal stub to satisfy attribute lookup
        class Credentials:
            @staticmethod
            def from_service_account_info(info, scopes=None):
                return object()

    def dummy_build(api, version, credentials=None):
        class Sites:
            def list(self):
                return self
            def execute(self):
                return {}
        class DummyService:
            def sites(self):
                return Sites()
        return DummyService()

    monkeypatch.setattr(bootstrap, "service_account", DummyCreds, raising=False)
    monkeypatch.setattr(bootstrap, "build", dummy_build, raising=False)

    # Execute the script; expect SystemExit with non‑zero code
    with pytest.raises(SystemExit) as excinfo:
        bootstrap.main()
    assert excinfo.value.code != 0

    # Report directory must not exist
    assert not (report_root / "phase-0").exists()


def test_bootstrap_discovery_error(monkeypatch, tmp_path):
    """Failing path: property discovery error aborts without writing report."""
    # Create a minimal valid secret file
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    secret_file = secrets_dir / "gsc_sa.json"
    secret_file.write_text("{" + '\n' + "  \"type\": \"service_account\"," + '\n' + "  \"client_email\": \"test@example.com\"" + '\n' + "}")
    monkeypatch.setenv("GSC_SA_PATH", str(secret_file))
    report_root = tmp_path / "out"
    monkeypatch.setenv("BOOTSTRAP_REPORT_ROOT", str(report_root))

    # Patch credential validation to succeed
    monkeypatch.setattr(
        bootstrap,
        "validate_credentials",
        lambda path: object(),
    )

    # Patch discover_properties to raise an exception
    def _raise(_):
        raise RuntimeError("API Error")

    monkeypatch.setattr(bootstrap, "discover_properties", _raise)

    # Execute script; expect non‑zero exit
    with pytest.raises(SystemExit) as excinfo:
        bootstrap.main()
    assert excinfo.value.code != 0
    # Ensure no report written
    assert not (report_root / "phase-0").exists()
