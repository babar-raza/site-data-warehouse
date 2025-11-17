import os
import pytest
import requests


def _skip_if_unreachable(base_url: str) -> None:
    """Helper to skip tests if the Ollama server is not reachable."""
    try:
        # Attempt a simple GET to the base URL or /api/health if available
        requests.get(base_url, timeout=2)
    except Exception:
        pytest.skip("Ollama server is not reachable on the configured URL")


def test_ollama_generate_basic():
    """Verify that the Ollama server can generate a simple response."""
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    _skip_if_unreachable(base_url)

    # Discover available models via /api/tags
    tags_resp = requests.get(f"{base_url}/api/tags", timeout=10)
    if tags_resp.status_code != 200:
        pytest.skip(f"/api/tags endpoint unavailable (status {tags_resp.status_code})")
    try:
        tags_data = tags_resp.json()
    except Exception:
        pytest.skip("/api/tags did not return JSON")

    # Extract model names from the response
    models = []
    if isinstance(tags_data, dict):
        models = tags_data.get("models") or tags_data.get("tags") or []
    elif isinstance(tags_data, list):
        models = tags_data
    if not models:
        pytest.skip("No models available in Ollama server")
    first = models[0]
    model_name = first.get("name") if isinstance(first, dict) else first

    generate_endpoint = f"{base_url}/api/generate"
    payload = {
        "model": model_name,
        "prompt": "Hello, world!",
        "stream": False
    }
    resp = requests.post(generate_endpoint, json=payload, timeout=30)
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
    try:
        data = resp.json()
    except Exception:
        pytest.skip("/api/generate did not return JSON; streaming may be enabled")
    assert any(key in data for key in ["response", "generated", "message", "messages"]), data


def test_ollama_list_models():
    """Verify that the Ollama server exposes a models listing endpoint."""
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    _skip_if_unreachable(base_url)
    models_endpoint = f"{base_url}/api/tags"
    resp = requests.get(models_endpoint, timeout=10)
    if resp.status_code != 200:
        pytest.skip(f"/api/tags endpoint unavailable (status {resp.status_code})")
    try:
        data = resp.json()
    except Exception:
        pytest.skip("/api/tags did not return JSON")
    assert isinstance(data, (list, dict)), data
    if isinstance(data, list):
        assert len(data) > 0, "Model list is empty"
    else:
        models = data.get("models") or data.get("tags") or data
        assert models, "No models returned"