"""Regression tests for the interactive five-expert credit guard."""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.api.models import QueryRequest
from src.api.simplified_query_endpoint import process_simplified_query


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expert_filter, expected_detail",
    [
        (None, "Select from 1 to 5 experts"),
        ([], "Select from 1 to 5 experts"),
        (["a", "b", "c", "d", "e", "f"], "no more than 5 experts"),
        (["a", "a"], "must be unique"),
    ],
)
async def test_query_rejects_unbounded_or_invalid_expert_selection(expert_filter, expected_detail):
    request = QueryRequest(query="How should a team adopt AI?", expert_filter=expert_filter)

    with pytest.raises(HTTPException) as exc_info:
        await process_simplified_query(request, db=object())

    assert exc_info.value.status_code == 422
    assert expected_detail in str(exc_info.value.detail)
