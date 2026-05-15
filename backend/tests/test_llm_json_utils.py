import pytest

from src.utils.llm_json import parse_llm_json


def test_parse_llm_json_accepts_strict_json():
    assert parse_llm_json('{"position": "ok"}') == {"position": "ok"}


def test_parse_llm_json_extracts_fenced_json():
    assert parse_llm_json('```json\n{"position": "ok"}\n```') == {"position": "ok"}


def test_parse_llm_json_repairs_common_llm_json_breakage():
    assert parse_llm_json('{"key_signals": [{"claim": "unterminated"}') == {
        "key_signals": [{"claim": "unterminated"}]
    }
    assert parse_llm_json('{"claim": "bad\x01control"}') == {
        "claim": "bad\x01control"
    }


def test_parse_llm_json_rejects_plain_safety_or_empty_text():
    with pytest.raises(ValueError, match="no JSON object or array found"):
        parse_llm_json("Запрос был заблокирован фильтрами безопасности")

    with pytest.raises(ValueError, match="empty LLM response"):
        parse_llm_json("   ")
