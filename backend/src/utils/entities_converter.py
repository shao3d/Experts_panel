"""
Utilities for converting Telegram entities to Markdown format.

Supports both:
1. JSON entities (from Telegram Desktop JSON export)
2. Telethon entities (from Live Telegram API)
"""

from typing import List, Dict, Any, Union, Optional


def entities_to_markdown_from_json(text: Union[str, List], text_entities: Optional[List[Dict]] = None) -> str:
    """
    Convert Telegram JSON export text with entities to Markdown.

    Args:
        text: Either a string or a list of text parts (with entities)
        text_entities: List of entity dicts from JSON (optional, for compatibility)

    Returns:
        Markdown-formatted string

    Examples:
        >>> entities_to_markdown_from_json("plain text")
        'plain text'

        >>> entities_to_markdown_from_json([
        ...     {"type": "plain", "text": "Check this "},
        ...     {"type": "text_link", "text": "link", "href": "https://example.com"},
        ...     {"type": "plain", "text": " out!"}
        ... ])
        'Check this [link](https://example.com) out!'
    """
    # If text is already a string, return as-is
    if isinstance(text, str):
        return text

    # If text is not a list, convert to string
    if not isinstance(text, list):
        return str(text)

    # Process list of entities
    markdown_parts = []

    for part in text:
        if isinstance(part, str):
            # Plain string part
            markdown_parts.append(part)
        elif isinstance(part, dict):
            entity_type = part.get('type', 'plain')
            entity_text = part.get('text', '')

            # Convert entity to markdown
            markdown_text = _convert_entity_to_markdown(entity_type, entity_text, part)
            markdown_parts.append(markdown_text)

    return ''.join(markdown_parts)


def entities_to_markdown_from_telethon(message_text: str, entities: Optional[List] = None) -> str:
    """
    Convert Telethon message text with entities to Markdown.

    Args:
        message_text: Plain text message
        entities: List of Telethon entity objects

    Returns:
        Markdown-formatted string

    Note:
        Telethon entities have offset/length structure, need to be processed in reverse order
        to avoid offset shifts when inserting markdown syntax.
    """
    if not entities or len(entities) == 0:
        return message_text

    # Sort entities by offset in reverse order (process from end to start)
    # This prevents offset shifts when we insert markdown syntax
    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)

    # Work with mutable list of characters
    chars = list(message_text)

    for entity in sorted_entities:
        offset = entity.offset
        length = entity.length
        entity_text = message_text[offset:offset + length]

        # Get entity type name
        entity_type = type(entity).__name__

        # Convert to markdown
        markdown_text = _convert_telethon_entity_to_markdown(entity_type, entity_text, entity)

        # Replace in chars list
        chars[offset:offset + length] = list(markdown_text)

    return ''.join(chars)


def _convert_entity_to_markdown(entity_type: str, text: str, entity: Dict[str, Any]) -> str:
    """
    Convert a single JSON entity to markdown.

    Args:
        entity_type: Type of entity (text_link, bold, italic, etc.)
        text: Text content of the entity
        entity: Full entity dict (may contain additional fields like href)

    Returns:
        Markdown-formatted text
    """
    if entity_type == 'plain':
        return text

    elif entity_type == 'text_link':
        # [text](href)
        href = entity.get('href', '')
        return f'[{text}]({href})'

    elif entity_type == 'link':
        # Plain URL - return as-is (ReactMarkdown will autolink)
        return text

    elif entity_type == 'bold':
        # **text**
        return f'**{text}**'

    elif entity_type == 'italic':
        # *text*
        return f'*{text}*'

    elif entity_type == 'code':
        # `text`
        return f'`{text}`'

    elif entity_type == 'pre':
        # ```text```
        return f'```\n{text}\n```'

    elif entity_type == 'strikethrough':
        # ~~text~~
        return f'~~{text}~~'

    elif entity_type == 'underline':
        # Markdown doesn't have standard underline, use HTML or just text
        return f'<u>{text}</u>'

    elif entity_type == 'blockquote':
        # > text
        # Handle multiline blockquotes
        lines = text.split('\n')
        return '\n'.join(f'> {line}' for line in lines)

    elif entity_type == 'mention':
        # @username - keep as-is
        return text

    elif entity_type == 'hashtag':
        # #tag - keep as-is
        return text

    elif entity_type == 'email':
        # email@example.com - ReactMarkdown will autolink
        return text

    elif entity_type == 'spoiler':
        # Spoiler - markdown doesn't have standard spoiler, use text
        # (could use ||text|| for Discord-style, but not standard markdown)
        return text

    elif entity_type == 'custom_emoji':
        # Custom emoji - just return text representation
        return text

    else:
        # Unknown entity type - return text as-is
        return text


def _convert_telethon_entity_to_markdown(entity_type: str, text: str, entity: Any) -> str:
    """
    Convert a single Telethon entity to markdown.

    Args:
        entity_type: Type name of Telethon entity (e.g., 'MessageEntityBold')
        text: Text content
        entity: Telethon entity object

    Returns:
        Markdown-formatted text
    """
    # Map Telethon entity types to markdown
    if entity_type == 'MessageEntityTextUrl':
        # [text](url)
        url = getattr(entity, 'url', '')
        return f'[{text}]({url})'

    elif entity_type == 'MessageEntityUrl':
        # Plain URL - return as-is
        return text

    elif entity_type == 'MessageEntityBold':
        # **text**
        return f'**{text}**'

    elif entity_type == 'MessageEntityItalic':
        # *text*
        return f'*{text}*'

    elif entity_type == 'MessageEntityCode':
        # `text`
        return f'`{text}`'

    elif entity_type == 'MessageEntityPre':
        # ```text```
        language = getattr(entity, 'language', '')
        if language:
            return f'```{language}\n{text}\n```'
        else:
            return f'```\n{text}\n```'

    elif entity_type == 'MessageEntityStrike':
        # ~~text~~
        return f'~~{text}~~'

    elif entity_type == 'MessageEntityUnderline':
        # HTML underline
        return f'<u>{text}</u>'

    elif entity_type == 'MessageEntityBlockquote':
        # > text
        lines = text.split('\n')
        return '\n'.join(f'> {line}' for line in lines)

    elif entity_type == 'MessageEntityMention':
        # @username
        return text

    elif entity_type == 'MessageEntityMentionName':
        # User mention - keep as text
        return text

    elif entity_type == 'MessageEntityHashtag':
        # #tag
        return text

    elif entity_type == 'MessageEntityEmail':
        # email@example.com
        return text

    elif entity_type == 'MessageEntitySpoiler':
        # Spoiler - no standard markdown
        return text

    elif entity_type == 'MessageEntityCustomEmoji':
        # Custom emoji - return text
        return text

    else:
        # Unknown entity - return as-is
        return text
