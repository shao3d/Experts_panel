import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.services.reddit_synthesis_service import RedditSynthesisService


def _system_prompt(language: str) -> str:
    service = object.__new__(RedditSynthesisService)
    messages = service._create_synthesis_prompt(
        "test query",
        "1. **Source** (r/test)\n   - Content: evidence\n   - URL: https://reddit.com/r/test/1",
        language,
    )
    return messages[0]["content"]


def test_russian_prompt_is_bounded_and_decision_first():
    prompt = _system_prompt("Russian")

    assert "+30%" not in prompt
    assert 'max_words="120"' in prompt
    assert 'max_words="600"' in prompt
    assert prompt.index("КУДА ИДТИ") < prompt.index("Deep Dive")
    assert 'required="only_if_enough_numeric_evidence"' in prompt
    assert "минимум две содержательные строки" in prompt
    assert "минимум два разных релевантных источника" in prompt
    assert "Не добавляйте его для привлечения внимания" in prompt
    assert "верните ровно одно предложение и больше ничего" in prompt


def test_english_prompt_is_bounded_and_decision_first():
    prompt = _system_prompt("English")

    assert "+30%" not in prompt
    assert 'max_words="120"' in prompt
    assert 'max_words="600"' in prompt
    assert prompt.index("WHERE TO GO") < prompt.index("Deep Dive")
    assert 'required="only_if_enough_numeric_evidence"' in prompt
    assert "at least two meaningful comparison rows" in prompt
    assert "at least two distinct relevant sources" in prompt
    assert "Never add it merely for emphasis" in prompt
    assert "return exactly one sentence and nothing else" in prompt


def test_opencode_accepts_only_standalone_canonical_abstention():
    assert RedditSynthesisService._reject_opencode_output(
        "No relevant Reddit discussions found for this specific topic.",
        "English",
    ) is None
    assert RedditSynthesisService._reject_opencode_output(
        "No relevant benchmarks were found, but this answer is truncated.",
        "English",
    ).startswith("suspiciously short")
