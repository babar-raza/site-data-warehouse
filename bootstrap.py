#!/usr/bin/env python3
"""
Phase 0 Bootstrap for API‑Only mode.

This script performs a minimal bootstrap of the GSC Data Warehouse in API‑only
deployments.  It validates that Google service account credentials are
available and usable, then connects to the Google Search Console API to
discover the list of accessible properties.  The results are written to a
report directory for human inspection.  On failure, a clear error is printed
and the process exits with a non‑zero status; no report is written.

Environment variables recognised:

  GSC_SA_PATH            Full path to the service account JSON file.  If not
                         provided, defaults to ``secrets/gsc_sa.json`` relative
                         to the project root.

  BOOTSTRAP_REPORT_ROOT  Base directory for report output.  If not provided,
                         reports are written under ``report/phase‑0`` relative
                         to the working directory.  Tests may override this
                         variable to isolate report output.

Usage:
  python bootstrap.py

On success the script prints the location of the report directory and exits
with code 0.  On failure it prints an error message to stderr and exits
non‑zero.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

try:
    # google-auth and google-api-python-client are declared in requirements.txt
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    # Lazy import errors will be surfaced in validate_credentials()
    service_account = None  # type: ignore
    build = None  # type: ignore


def _resolve_secret_path() -> Path:
    """Resolve the path to the service account JSON file.

    The path is taken from the ``GSC_SA_PATH`` environment variable if set;
    otherwise defaults to ``secrets/gsc_sa.json`` relative to the current
    working directory.
    """
    env_path = os.environ.get("GSC_SA_PATH")
    if env_path:
        return Path(env_path)
    return Path("secrets") / "gsc_sa.json"


def _resolve_report_dir() -> Path:
    """Resolve the base directory for report output.

    The base directory can be customised via the ``BOOTSTRAP_REPORT_ROOT``
    environment variable.  Reports are written into a ``phase‑0`` subdirectory
    of this root.
    """
    root = os.environ.get("BOOTSTRAP_REPORT_ROOT", "report")
    return Path(root) / "phase-0"


def validate_credentials(secret_path: Path) -> Any:
    """Load and validate service account credentials.

    Reads the JSON file at ``secret_path`` and attempts to construct a
    ``Credentials`` object with the minimal scope needed to list Search Console
    properties.  On success returns a credentials instance.  On failure raises
    an exception describing the issue.
    """
    # Ensure required libraries are available
    if service_account is None or build is None:
        raise RuntimeError(
            "Required Google libraries are missing. Ensure google-auth and google-api-python-client are installed."
        )

    if not secret_path.exists():
        raise FileNotFoundError(
            f"Service account file not found at '{secret_path}'. "
            "Place your JSON key in this location or set GSC_SA_PATH."
        )
    try:
        with secret_path.open("r", encoding="utf-8") as f:
            info = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in service account file '{secret_path}': {exc.msg}"
        )

    try:
        # Minimal scope for read‑only access to Search Console API
        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    except Exception as exc:
        raise ValueError(
            f"Failed to parse service account credentials from '{secret_path}': {exc}"
        )
    return creds


def discover_properties(creds: Any) -> List[Dict[str, Any]]:
    """Use the Search Console API to list accessible properties.

    This function uses the authorised ``creds`` object to build the
    ``webmasters`` client and invoke its ``sites().list()`` method.  It
    returns the raw list of site entries returned by Google.  Any exceptions
    raised by the client library will propagate to the caller.
    """
    try:
        service = build("webmasters", "v3", credentials=creds)
        request = service.sites().list()
        response = request.execute()
    except Exception as exc:
        raise RuntimeError(f"Error calling Search Console API: {exc}")

    # The API returns a dict with key 'siteEntry' containing a list of site objects.
    sites = response.get("siteEntry", [])
    # Optionally normalise field names for downstream use
    return sites


def write_report(report_dir: Path, properties: List[Dict[str, Any]]) -> None:
    """Write a bootstrap report.

    The report consists of two files:
      - ``status.json`` summarises the run timestamp and the number of discovered properties.
      - ``properties.json`` contains the raw list of property entries.

    The ``report_dir`` directory will be created if it does not already exist.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    # Use timezone-aware UTC timestamp and normalize to trailing 'Z'
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    status = {
        "timestamp": timestamp,
        "num_properties": len(properties),
    }
    status_path = report_dir / "status.json"
    properties_path = report_dir / "properties.json"
    with status_path.open("w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    with properties_path.open("w", encoding="utf-8") as f:
        json.dump(properties, f, indent=2)

    print(f"Phase 0 complete. Report written to {report_dir}")


def main() -> None:
    """Entry point for the bootstrap script.

    Performs credential validation and property discovery, writes a report,
    and exits.  On any exception the function prints an error message and
    exits with a non‑zero code without writing a report.
    """
    secret_path = _resolve_secret_path()
    report_dir = _resolve_report_dir()
    try:
        creds = validate_credentials(secret_path)
        properties = discover_properties(creds)
    except Exception as exc:
        # Print error and abort without writing a report
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Write report on success
    write_report(report_dir, properties)
    # Exit with success code
    sys.exit(0)


if __name__ == "__main__":
    main()
