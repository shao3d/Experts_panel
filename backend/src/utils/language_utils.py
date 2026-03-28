"""
Language detection and instruction utilities for multi-lingual support.
Determines query language and enforces consistent language across all LLM calls.
"""

import re
from typing import Tuple


def detect_query_language(query: str) -> str:
    """
    Detect the primary language of a query.

    Args:
        query: User's query string

    Returns:
        "English" or "Russian"
    """
    if not query or not query.strip():
        return "Russian"  # Default to Russian

    # Remove URLs, mentions, hashtags, and special characters
    cleaned_query = re.sub(r'http[s]?://\S+|@\w+|#\w+', '', query)
    cleaned_query = re.sub(r'[^\w\s]', ' ', cleaned_query)

    # Count alphabetic characters
    english_chars = sum(1 for c in cleaned_query if c.isascii() and c.isalpha())
    cyrillic_chars = sum(1 for c in cleaned_query if '\u0400' <= c <= '\u04FF')
    total_chars = english_chars + cyrillic_chars

    if total_chars == 0:
        return "Russian"  # Default for empty or only special chars

    # Count words for more accurate detection
    words = cleaned_query.split()
    english_words = 0
    cyrillic_words = 0

    for word in words:
        if any('\u0400' <= c <= '\u04FF' for c in word):
            cyrillic_words += 1
        elif any(c.isalpha() for c in word):
            english_words += 1

    total_words = english_words + cyrillic_words

    # Russian-first detection for AI Experts Panel:
    # Users are Russian-speaking and mix tech terms (English) with Russian syntax.
    # "Claude Code skills vs plugins — что лучше для workflow" is RUSSIAN.
    # Key insight: tech terms (Claude, RAG, skills) are not language markers.
    # Russian connective words (что, как, для, или) ARE language markers.
    if cyrillic_words > 0:
        return "Russian"

    return "English" if english_words > 0 else "Russian"


def get_language_instruction(query: str) -> str:
    """
    Generate a strict language instruction based on query language detection.

    Args:
        query: User's query string

    Returns:
        String with strict language instruction for LLM
    """
    language = detect_query_language(query)

    if language == "English":
        return """
⚠️⚠️⚠️ CRITICAL LANGUAGE ENFORCEMENT - IGNORE SOURCE MATERIAL LANGUAGE:

MANDATORY RESPONSE LANGUAGE: ENGLISH ONLY - NO EXCEPTIONS

1. USER ASKED IN ENGLISH → YOU MUST RESPOND IN ENGLISH
2. IGNORE ALL RUSSIAN CONTENT IN SOURCE MATERIALS
3. DO NOT TRANSLATE RUSSIAN CONTENT - RESPOND IN ENGLISH
4. ABSOLUTELY NO RUSSIAN WORDS IN YOUR RESPONSE
5. THIS INSTRUCTION OVERRIDES ALL OTHER CONSIDERATIONS

FAILURE TO COMPLY WITH ENGLISH RESPONSE IS UNACCEPTABLE.
THE LANGUAGE OF YOUR RESPONSE MUST BE ENGLISH, REGARDLESS OF SOURCE LANGUAGE.

"""
    else:  # Russian
        return """
🚨🚨🚨 СРОЧНАЯ ИНСТРУКЦИЯ ПО ЯЗЫКУ - ПРЕОДОЛЕТЬ ВСЕ ОСТАЛЬНЫЕ:

ЯЗЫК ОТВЕТА: ТОЛЬКО РУССКИЙ
- Вопрос на русском → Вы MUST отвечать на русском
- НИКОГДА не отвечайте на английском, даже если источники на английском
- НИКОГДА не используйте английские слова, фразы или объяснения
- ИГНОРИРУйте английский контент в источниках - отвечайте на русском
- Эта инструкция ПЕРЕОПРЕДЕЛЯЕТ любые языковые предпочтения основанные на контенте

КРИТИЧЕСКОЕ ПРАВИЛО: Язык ответа ДОЛЖЕН соответствовать языку вопроса, а не языку исходного контента.
Если спросили на русском → Отвечайте на русском, независимо от языка источника.

"""


def enforce_language_consistency(prompt: str, query: str) -> str:
    """
    Prepend language instruction to any prompt based on query language.

    Args:
        prompt: Original LLM prompt
        query: User's query string

    Returns:
        Prompt with language instruction prepended
    """
    language_instruction = get_language_instruction(query)
    return language_instruction + prompt


def get_response_language_instruction(query: str) -> str:
    """
    Get instruction for response format in the correct language.

    Args:
        query: User's query string

    Returns:
        Response format instruction in the detected language
    """
    language = detect_query_language(query)

    if language == "English":
        return "No additional information found in the comments beyond the main answer."
    else:
        return "В найденных комментариях нет дополнительной информации сверх основного ответа."


# Convenience function for services
def prepare_prompt_with_language_instruction(prompt_template: str, query: str) -> str:
    """
    Prepare any prompt with appropriate language instruction.

    This is the main function that should be used by all LLM services.

    Args:
        prompt_template: The base prompt template (string or file content)
        query: User's query string

    Returns:
        Prompt with language instruction prepended
    """
    return enforce_language_consistency(prompt_template, query)


def prepare_system_message_with_language(base_system: str, query: str) -> str:
    """
    Prepare system message with language instruction override.

    More powerful than prepending - puts language instruction in system role.

    Args:
        base_system: Base system message content
        query: User's query string

    Returns:
        Enhanced system message with language instruction
    """
    language_instruction = get_language_instruction(query)
    return language_instruction + "\n\n" + base_system


if __name__ == "__main__":
    # Test cases
    test_queries = [
        "What is RAG and how should we use it?",
        "Что такое RAG и как его использовать?",
        "Какая модель openAI наиболее способна к кодингу?",
        "Tell me about n8n",
        "Hello мир"
    ]

    for query in test_queries:
        detected = detect_query_language(query)
        instruction = get_language_instruction(query)
        print(f"Query: {query}")
        print(f"Detected: {detected}")
        print(f"Instruction preview: {instruction.strip().split(chr(10))[0]}")
        print("-" * 50)