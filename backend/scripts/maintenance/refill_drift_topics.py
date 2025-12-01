"""
Refill drift_topics for all comment groups using Claude Sonnet 4.5.

Usage:
    python backend/refill_drift_topics.py --test  # Test on 10 groups
    python backend/refill_drift_topics.py --all   # Process all 63 groups
"""

import os
import json
import time
import argparse
from pathlib import Path
from string import Template
from typing import Dict, List, Any, Optional

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuration
DATABASE_PATH = Path(__file__).parent / "data" / "experts.db"
PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_drift_topics.txt"
MODEL = "anthropic/claude-sonnet-4.5"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def load_prompt_template() -> Template:
    """Load prompt template from file."""
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        return Template(f.read())

def get_db_session():
    """Create database session."""
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Session = sessionmaker(bind=engine)
    return Session()

def fetch_comment_groups(session, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch all comment groups with anchor posts."""
    query = text("""
        SELECT
            cgd.post_id,
            p.message_text as anchor_post_text,
            p.telegram_message_id,
            COUNT(c.comment_id) as comment_count
        FROM comment_group_drift cgd
        JOIN posts p ON cgd.post_id = p.post_id
        JOIN comments c ON c.post_id = cgd.post_id
        GROUP BY cgd.post_id
        ORDER BY cgd.post_id
    """)

    if limit:
        query = text(str(query) + f" LIMIT {limit}")

    result = session.execute(query)
    return [dict(row._mapping) for row in result]

def fetch_comments(session, post_id: int) -> List[Dict[str, Any]]:
    """Fetch all comments for a post."""
    query = text("""
        SELECT comment_text, author_name, created_at
        FROM comments
        WHERE post_id = :post_id
        ORDER BY created_at
    """)

    result = session.execute(query, {"post_id": post_id})
    return [dict(row._mapping) for row in result]

def format_comments(comments: List[Dict[str, Any]]) -> str:
    """Format comments for prompt."""
    formatted = []
    for i, comment in enumerate(comments, 1):
        formatted.append(f"{comment['comment_text']}|{comment['author_name']}")
    return "\n".join(formatted)

def parse_json_response(content: str) -> Dict[str, Any]:
    """Parse JSON from LLM response with fallback for markdown blocks."""
    import re

    # 1. Try clean JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. Try markdown JSON block
    match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Try any JSON object
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in response: {content[:200]}...")

def call_openrouter(
    prompt: str,
    api_key: str,
    temperature: float = 0.3
) -> Dict[str, Any]:
    """Call OpenRouter API with Sonnet 4.5."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/yourusername/experts-panel",
        "X-Title": "Experts Panel - Drift Topics Extraction"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature
    }

    response = requests.post(
        OPENROUTER_API_URL,
        headers=headers,
        json=payload,
        timeout=120
    )

    response.raise_for_status()
    return response.json()

def extract_drift_topics(
    anchor_post: str,
    comments: List[Dict[str, Any]],
    prompt_template: Template,
    api_key: str
) -> Dict[str, Any]:
    """Extract drift topics using Claude Sonnet 4.5."""

    comments_text = format_comments(comments)

    prompt = prompt_template.substitute(
        anchor_post=anchor_post,
        comments=comments_text
    )

    response = call_openrouter(prompt, api_key)
    content = response['choices'][0]['message']['content']

    return parse_json_response(content)

def update_drift_topics(
    session,
    post_id: int,
    drift_data: Dict[str, Any]
) -> None:
    """Update comment_group_drift table with new drift_topics."""

    query = text("""
        UPDATE comment_group_drift
        SET
            has_drift = :has_drift,
            drift_topics = :drift_topics,
            analyzed_at = CURRENT_TIMESTAMP,
            analyzed_by = :analyzed_by
        WHERE post_id = :post_id
    """)

    session.execute(query, {
        "post_id": post_id,
        "has_drift": drift_data["has_drift"],
        "drift_topics": json.dumps(drift_data["drift_topics"], ensure_ascii=False),
        "analyzed_by": f"{MODEL} (refill_script)"
    })

    session.commit()

def main():
    parser = argparse.ArgumentParser(description="Refill drift_topics for comment groups")
    parser.add_argument("--test", action="store_true", help="Test on first 3 groups")
    parser.add_argument("--all", action="store_true", help="Process all 63 groups")
    parser.add_argument("--api-key", help="OpenRouter API key (or set OPENROUTER_API_KEY env var)")

    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Must specify either --test or --all")

    # Get API key
    api_key = args.api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OpenRouter API key required. Set OPENROUTER_API_KEY env var or use --api-key")

    # Load resources
    prompt_template = load_prompt_template()
    session = get_db_session()

    # Fetch groups
    limit = 3 if args.test else None
    groups = fetch_comment_groups(session, limit)

    print(f"📊 Processing {len(groups)} comment groups...")
    print(f"🤖 Model: {MODEL}")
    print(f"💰 Estimated cost: ${len(groups) * 0.005:.2f}")
    print()

    # Process each group
    success_count = 0
    error_count = 0

    for i, group in enumerate(groups, 1):
        post_id = group["post_id"]
        telegram_id = group["telegram_message_id"]

        print(f"[{i}/{len(groups)}] Post #{post_id} (TG: {telegram_id})...")

        try:
            # Fetch comments
            comments = fetch_comments(session, post_id)

            # Extract drift topics
            drift_data = extract_drift_topics(
                group["anchor_post_text"],
                comments,
                prompt_template,
                api_key
            )

            # Update database
            update_drift_topics(session, post_id, drift_data)

            # Print results
            topic_count = len(drift_data.get("drift_topics", []))
            has_drift = drift_data.get("has_drift", False)

            if has_drift:
                print(f"  ✅ {topic_count} drift topic(s) extracted")
                for topic in drift_data["drift_topics"]:
                    print(f"     - {topic['topic']}")
            else:
                print(f"  ⚪ No drift detected")

            success_count += 1

            # Rate limiting
            time.sleep(1)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            error_count += 1
            continue

    # Summary
    print()
    print("=" * 60)
    print(f"✅ Success: {success_count}/{len(groups)}")
    print(f"❌ Errors: {error_count}/{len(groups)}")
    print("=" * 60)

    session.close()

if __name__ == "__main__":
    main()
