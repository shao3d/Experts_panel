"""Unit tests for AI Scout Service - Level 1 Upgrade.

Tests special character handling, fallback protection, and validation.

Run: cd backend && python -m pytest ../tests/test_ai_scout.py -v
"""

import pytest
import sys
import os

# Setup path for backend imports
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

from src.services.ai_scout_service import AIScoutService
from src.services.fts5_retrieval_service import sanitize_fts5_query


class TestAIScoutSpecialChars:
    """Test suite for special character handling in AI Scout."""

    def test_known_slang_contains_special_chars(self):
        """Verify KNOWN_SLANG includes C++, C#, F#, .NET, Node.js."""
        service = AIScoutService()

        assert "c++" in service.KNOWN_SLANG
        assert "c#" in service.KNOWN_SLANG
        assert "f#" in service.KNOWN_SLANG
        assert ".net" in service.KNOWN_SLANG
        assert "node.js" in service.KNOWN_SLANG

    def test_slang_mappings_are_safe(self):
        """Verify special char mappings don't contain raw special chars."""
        service = AIScoutService()

        for key, value in service.KNOWN_SLANG.items():
            if any(c in key for c in '+#.'):
                # Value should NOT contain raw special chars with wildcards
                assert '++*' not in value, f"Unsafe mapping: {key} -> {value}"
                assert '#*' not in value, f"Unsafe mapping: {key} -> {value}"
                # Value should contain safe alternatives
                assert 'cpp' in value or 'csharp' in value or 'fsharp' in value or 'dotnet' in value or 'nodejs' in value, \
                    f"Missing safe alternative for: {key}"


class TestFallbackProtection:
    """Test suite for fallback generator protection against special chars."""

    def test_fallback_cplusplus_no_wildcard(self):
        """C++ in fallback should NOT produce C++* wildcard."""
        service = AIScoutService()

        fallback = service._generate_fallback("как работать с C++")

        # Should NOT contain C++* (invalid FTS5 syntax)
        assert "c++*" not in fallback.lower()
        # Should contain safe alternatives
        assert "cpp" in fallback or "cplusplus" in fallback

    def test_fallback_csharp_no_wildcard(self):
        """C# in fallback should NOT produce C#* wildcard."""
        service = AIScoutService()

        fallback = service._generate_fallback("C# разработка")

        assert "c#*" not in fallback.lower()
        assert "csharp" in fallback

    def test_fallback_regular_word_has_wildcard(self):
        """Regular words should still get wildcards."""
        service = AIScoutService()

        fallback = service._generate_fallback("kubernetes настройка")

        # Regular words should have wildcards
        assert "*" in fallback


class TestValidator:
    """Test suite for FTS5 query validation."""

    def test_validator_rejects_cplusplus_wildcard(self):
        """Validator should reject C++* pattern."""
        service = AIScoutService()

        assert service.validate_match_query("(C++*) AND test") is False
        assert service.validate_match_query("C++*") is False

    def test_validator_rejects_csharp_wildcard(self):
        """Validator should reject C#* pattern."""
        service = AIScoutService()

        assert service.validate_match_query("(C#*)") is False
        assert service.validate_match_query("C#* AND deploy") is False

    def test_validator_accepts_safe_alternatives(self):
        """Validator should accept safe alternatives like cpp, csharp."""
        service = AIScoutService()

        assert service.validate_match_query("(cpp OR cplusplus) AND test") is True
        assert service.validate_match_query('(csharp OR "си шарп")') is True

    def test_validator_balanced_quotes(self):
        """Validator should check quote balance."""
        service = AIScoutService()

        assert service.validate_match_query('"си плюс плюс"') is True
        assert service.validate_match_query('"unbalanced') is False
        assert service.validate_match_query('a"b') is False

    def test_validator_balanced_parens(self):
        """Validator should check parenthesis balance."""
        service = AIScoutService()

        assert service.validate_match_query('((a OR b) AND c)') is True
        assert service.validate_match_query('((a OR b') is False


class TestSanitizerIntegration:
    """Test that sanitizer and scout work together."""

    def test_phrase_search_preserved(self):
        """Phrase search with quotes should be preserved through sanitization."""
        # This phrase should pass through with balanced quotes
        result = sanitize_fts5_query('"си плюс плюс"')

        # Quotes should be preserved
        assert '"' in result
        assert 'си плюс плюс' in result

    def test_unbalanced_quotes_removed(self):
        """Unbalanced quotes should be stripped."""
        result = sanitize_fts5_query('"unbalanced phrase')

        # All quotes should be removed if unbalanced
        assert '"' not in result

    def test_sql_injection_blocked(self):
        """SQL injection attempts should be blocked."""
        # Semicolon should be removed
        result = sanitize_fts5_query("test; DROP TABLE posts;")
        assert ';' not in result


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
