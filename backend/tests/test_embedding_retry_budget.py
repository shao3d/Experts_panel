"""Scout can shorten retries without changing ingestion's embedding policy."""
import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services import embedding_service as embeddings


@pytest.mark.parametrize('options, attempts, timeout', [
    ({}, 4, 60),
    ({'request_timeout': 15, 'max_retry_attempts': 2}, 2, 15),
])
def test_retry_policy_is_scoped_to_service(monkeypatch, options, attempts, timeout):
    monkeypatch.setattr(embeddings.config, 'OPENROUTER_API_KEY', 'test-only')
    service = embeddings.EmbeddingService(**options)
    calls = []

    def fail(*args, **kwargs):
        calls.append(kwargs['timeout'])
        raise requests.Timeout('simulated timeout')

    sleep = AsyncMock()
    monkeypatch.setattr(embeddings.requests, 'post', fail)
    monkeypatch.setattr(embeddings.asyncio, 'sleep', sleep)
    with pytest.raises(embeddings.RetryableEmbeddingError):
        asyncio.run(service.embed_query('camera'))
    assert calls == [timeout] * attempts
    assert sleep.await_count == attempts - 1


@pytest.mark.parametrize('status, expected_calls', [(429, 2), (503, 2), (401, 1)])
def test_retryable_http_errors_and_terminal_auth_error(monkeypatch, status, expected_calls):
    monkeypatch.setattr(embeddings.config, 'OPENROUTER_API_KEY', 'test-only')
    service = embeddings.EmbeddingService(request_timeout=15, max_retry_attempts=2)
    response = requests.Response()
    response.status_code = status
    response._content = b'{"error":{"message":"test failure"}}'
    response.headers['Retry-After'] = '300'
    calls = []
    monkeypatch.setattr(embeddings.requests, 'post', lambda *a, **kw: calls.append(kw) or response)
    sleep = AsyncMock()
    monkeypatch.setattr(embeddings.asyncio, 'sleep', sleep)
    with pytest.raises(RuntimeError):
        asyncio.run(service.embed_query('camera'))
    assert len(calls) == expected_calls
    for call in sleep.await_args_list:
        assert call.args[0] <= 12


def test_transient_error_can_recover(monkeypatch):
    monkeypatch.setattr(embeddings.config, 'OPENROUTER_API_KEY', 'test-only')
    service = embeddings.EmbeddingService(request_timeout=15, max_retry_attempts=2)
    calls = []

    def embed(*args):
        calls.append(args)
        if len(calls) == 1:
            raise embeddings.RetryableEmbeddingError('temporary')
        return [0.1, 0.2]

    monkeypatch.setattr(service, '_embed', embed)
    monkeypatch.setattr(embeddings.asyncio, 'sleep', AsyncMock())
    assert asyncio.run(service.embed_query('camera')) == [0.1, 0.2]
    assert len(calls) == 2
