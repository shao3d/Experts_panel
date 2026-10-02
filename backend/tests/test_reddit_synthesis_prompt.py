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


def test_prompt_requires_scope_before_content_in_both_languages():
    for language in ("Russian", "English"):
        prompt = _system_prompt(language)
        assert f"user-facing text in {language}" in prompt
        assert prompt.index("COVERAGE") < prompt.index("EVIDENCE RULES")
        assert "actions MUST be empty" in prompt
        assert "generated guide is not a tested practitioner report" in prompt
        assert 'required="always"' not in prompt


def test_only_standalone_canonical_abstention_is_an_abstention():
    assert RedditSynthesisService.is_explicit_abstention(
        "No relevant Reddit discussions found for this specific topic.")
    assert not RedditSynthesisService.is_explicit_abstention(
        "No relevant benchmarks were found, but use model X anyway.")
