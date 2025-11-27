"""
Live end-to-end tests with actual Ollama calls
Run with: pytest tests/test_live_ollama_e2e.py -v -s
"""
import os
import pytest
import requests
from tests.testing_modes import require_live_mode, is_live_mode


@pytest.fixture
def ollama_config():
    """Get Ollama configuration"""
    return {
        'base_url': os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'),
        'model': os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:7b')
    }


@pytest.mark.live
def test_ollama_health_check(ollama_config):
    """Test Ollama server is accessible"""
    response = requests.get(f"{ollama_config['base_url']}/api/version", timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert 'version' in data
    print(f"\n[OK] Ollama version: {data['version']}")


@pytest.mark.live
def test_ollama_list_local_models(ollama_config):
    """Test listing available models"""
    response = requests.get(f"{ollama_config['base_url']}/api/tags", timeout=10)
    assert response.status_code == 200
    data = response.json()

    models = data.get('models', [])
    assert len(models) > 0, "No models found"

    # Find non-premium models
    local_models = [m for m in models if m.get('size', 0) > 0]
    print(f"\n[OK] Found {len(local_models)} local models")

    for model in local_models[:5]:
        print(f"  - {model['name']} ({model.get('parameter_size', 'unknown')})")

    # Return only non-premium models
    local_models = [m for m in local_models if 'gemini-3-pro-preview' not in m['name']]

    return local_models


@pytest.mark.live
def test_ollama_generate_simple_response(ollama_config):
    """Test generating a simple response with Ollama"""
    model = ollama_config['model']

    # Check if model exists
    response = requests.get(f"{ollama_config['base_url']}/api/tags", timeout=10)
    models = response.json().get('models', [])
    model_names = [m['name'] for m in models]

    if model not in model_names:
        # Use first available local model (excluding premium)
        local_models = [m for m in models if m.get('size', 0) > 0 and 'gemini-3-pro-preview' not in m['name']]
        assert len(local_models) > 0, "No local models available"
        model = local_models[0]['name']
        print(f"\n Using model: {model}")

    # Double check it's not a premium model
    if 'gemini-3-pro-preview' in model:
        local_models = [m for m in models if m.get('size', 0) > 0 and 'gemini-3-pro-preview' not in m['name']]
        model = local_models[0]['name']

    # Generate response
    payload = {
        "model": model,
        "prompt": "What is SEO? Answer in one sentence.",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 100
        }
    }

    print(f"\n Generating response with {model}...")
    response = requests.post(
        f"{ollama_config['base_url']}/api/generate",
        json=payload,
        timeout=60
    )

    assert response.status_code == 200, f"Request failed: {response.text}"
    data = response.json()

    assert 'response' in data or 'message' in data, f"Unexpected response format: {data}"

    generated_text = data.get('response', data.get('message', ''))
    print(f"\n[OK] Generated response ({len(generated_text)} chars):")
    print(f"  {generated_text[:200]}...")

    assert len(generated_text) > 0
    return generated_text


@pytest.mark.live
def test_ollama_embeddings_generation(ollama_config):
    """Test generating embeddings with Ollama"""
    try:
        from insights_core.embeddings import EmbeddingGenerator

        print("\n Testing embedding generation...")
        generator = EmbeddingGenerator()

        text = "How to optimize website performance for better SEO rankings"
        embedding = generator.generate_embedding(text)

        assert embedding is not None
        assert len(embedding) > 0
        print(f"[OK] Generated embedding with {len(embedding)} dimensions")

        # Test similarity using numpy
        import numpy as np
        text2 = "Website speed optimization improves search engine rankings"
        embedding2 = generator.generate_embedding(text2)

        # Compute cosine similarity
        similarity = np.dot(embedding, embedding2) / (np.linalg.norm(embedding) * np.linalg.norm(embedding2))
        print(f"[OK] Similarity between related texts: {similarity:.3f}")
        assert similarity > 0.5, "Related texts should have high similarity"

    except ImportError as e:
        pytest.skip(f"Embeddings module not available: {e}")


@pytest.mark.live
def test_ollama_chat_multi_turn(ollama_config):
    """Test multi-turn conversation with Ollama"""
    model = ollama_config['model']

    # Get available model (excluding premium)
    response = requests.get(f"{ollama_config['base_url']}/api/tags", timeout=10)
    models = response.json().get('models', [])
    local_models = [m for m in models if m.get('size', 0) > 0 and 'gemini-3-pro-preview' not in m['name']]

    if local_models:
        model = local_models[0]['name']

    print(f"\n Testing multi-turn chat with {model}...")

    # Turn 1
    payload1 = {
        "model": model,
        "prompt": "List 3 important SEO factors.",
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 150}
    }

    response1 = requests.post(
        f"{ollama_config['base_url']}/api/generate",
        json=payload1,
        timeout=60
    )
    assert response1.status_code == 200

    answer1 = response1.json().get('response', '')
    print(f"\n Turn 1 Response: {answer1[:150]}...")

    # Turn 2 - Follow up
    payload2 = {
        "model": model,
        "prompt": f"Previous answer: {answer1}\n\nNow explain the first factor in detail.",
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 200}
    }

    response2 = requests.post(
        f"{ollama_config['base_url']}/api/generate",
        json=payload2,
        timeout=60
    )
    assert response2.status_code == 200

    answer2 = response2.json().get('response', '')
    print(f"\n Turn 2 Response: {answer2[:150]}...")

    assert len(answer1) > 0 and len(answer2) > 0
    print(f"\n[OK] Multi-turn conversation successful")


@pytest.mark.live
def test_ollama_with_system_prompt(ollama_config):
    """Test using system prompts for structured output"""
    model = ollama_config['model']

    # Get available model (excluding premium)
    response = requests.get(f"{ollama_config['base_url']}/api/tags", timeout=10)
    models = response.json().get('models', [])
    local_models = [m for m in models if m.get('size', 0) > 0 and 'gemini-3-pro-preview' not in m['name']]

    if local_models:
        model = local_models[0]['name']

    print(f"\n Testing system prompt with {model}...")

    # Use system prompt to guide response format
    system_prompt = "You are an SEO expert. Provide concise, actionable advice."
    user_prompt = "How can I improve my website's Core Web Vitals?"

    combined_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {user_prompt}\n\nASSISTANT:"

    payload = {
        "model": model,
        "prompt": combined_prompt,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": 250
        }
    }

    response = requests.post(
        f"{ollama_config['base_url']}/api/generate",
        json=payload,
        timeout=60
    )

    assert response.status_code == 200
    data = response.json()

    answer = data.get('response', '')
    print(f"\n[OK] Response with system prompt ({len(answer)} chars):")
    print(f"  {answer[:200]}...")

    assert len(answer) > 0
    assert any(keyword in answer.lower() for keyword in ['lcp', 'fid', 'cls', 'performance', 'speed', 'load'])


if __name__ == '__main__':
    # Run tests with live mode
    os.environ['TEST_MODE'] = 'live'
    os.environ['OLLAMA_BASE_URL'] = 'http://localhost:11434'
    os.environ['OLLAMA_MODEL'] = 'qwen2.5-coder:7b'

    pytest.main([__file__, '-v', '-s', '-m', 'live'])
