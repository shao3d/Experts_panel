#!/usr/bin/env python3
"""
Custom drift analysis script for specific post_id 680
Forces re-analysis regardless of current status
"""

import json
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Any
import time

def get_database_connection():
    """Get database connection"""
    # Use absolute path for database reliability
    db_path = '/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_post_content(conn, post_id: int) -> Dict[str, Any]:
    """Get post content for analysis"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_text, created_at, channel_id
        FROM posts
        WHERE post_id = ?
    """, (post_id,))
    row = cursor.fetchone()
    return dict(row) if row else {}

def get_comments_for_post(conn, post_id: int) -> List[Dict[str, Any]]:
    """Get all comments for a post"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT comment_id, comment_text, author_name, created_at
        FROM comments
        WHERE post_id = ?
        ORDER BY created_at
    """, (post_id,))
    return [dict(row) for row in cursor.fetchall()]

def analyze_drift_for_group(post_content: Dict, comments: List[Dict]) -> Dict[str, Any]:
    """
    Analyze drift for a comment group using enhanced heuristic analysis
    """
    if not comments:
        return {"has_drift": 0, "drift_topics": None}

    post_text = post_content.get('message_text', '')
    if not post_text:
        return {"has_drift": 0, "drift_topics": None}

    # Use the enhanced drift analysis from the original script
    return simple_drift_analysis(post_text, comments)

def simple_drift_analysis(post_text: str, comments: List[Dict]) -> Dict[str, Any]:
    """
    Enhanced heuristic-based drift analysis
    Analyzes topic drift between post and comments
    """
    if not comments:
        return {"has_drift": 0, "drift_topics": None}

    # Normalize post text
    post_text_lower = post_text.lower()
    post_words = set(post_text_lower.split())

    # Define topic categories and their keywords
    topic_categories = {
        "OCR Performance & Capabilities": {
            "keywords": ["ocr", "bounding", "boxes", "сканированные", "приказы", "сканер", "результаты", "шум", "экран"],
            "related_terms": ["распознает", "сканирует", "читает", "обрабатывает", "анализирует"]
        },
        "Model Testing & Benchmarks": {
            "keywords": ["годнота", "огнище", "бенчи", "картинки", "тест", "проверка", "сравнение", "производительность"],
            "related_terms": ["проверял", "тестировал", "бенчмарк", "результаты", "скорость"]
        },
        "Hardware Requirements & Compatibility": {
            "keywords": ["4090", "3060", "машинах", "компьюта", "железо", "видеокарта", "память"],
            "related_terms": ["запустить", "работает", "требует", "нужна", "подходит"]
        },
        "Alternative Solutions & Models": {
            "keywords": ["nanonets", "qwen", "huggingface", "gguf", "альтернатива", "другие", "модели"],
            "related_terms": ["использовать", "попробовать", "сравнить", "варианты"]
        },
        "Practical Applications & Use Cases": {
            "keywords": ["crm", "координатам", "предразметки", "аннотацию", "задача", "применение", "реальный"],
            "related_terms": ["использую", "применять", "практика", "работа", "проект"]
        },
        "Technical Limitations & Issues": {
            "keywords": ["не могут", "тинкеринг", "автоматизированном", "проблемы", "ограничения", "баги", "точность"],
            "related_terms": ["проблема", "сложность", "ограничение", "не работает", "ошибка"]
        },
        "Presentation & Discussion Quality": {
            "keywords": ["презентации", "достаточно", "высокий", "уровень", "абстракции", "понятно", "интересно", "применимо"],
            "related_terms": ["благодарю", "понравилось", "ясно", "полезно", "качественно"]
        },
        "Recording & Documentation": {
            "keywords": ["запись", "будет", "записать", "видео", "документация", "материалы"],
            "related_terms": ["запись", "сохранить", "опубликовать", "доступно"]
        }
    }

    # Analyze comments for topic drift
    drift_topics = []
    comment_texts = [comment["comment_text"].lower() for comment in comments]

    for category_name, category_data in topic_categories.items():
        matching_comments = []

        # Find comments that match this category
        for i, text in enumerate(comment_texts):
            keyword_matches = sum(1 for keyword in category_data["keywords"] if keyword in text)
            related_matches = sum(1 for term in category_data["related_terms"] if term in text)

            if keyword_matches > 0 or related_matches > 0:
                matching_comments.append(comments[i])

        # Only consider as drift if:
        # 1. We have matching comments
        # 2. The topic is not the main focus of the original post
        # 3. We have substantial discussion (multiple comments or detailed comments)

        if matching_comments:
            # Check if this topic is already covered in the original post
            post_topic_coverage = sum(1 for keyword in category_data["keywords"] if keyword in post_text_lower)

            # Consider it drift if:
            # - Post doesn't cover this topic well (<= 1 keyword match)
            # - OR we have extensive discussion beyond what's in the post
            if post_topic_coverage <= 1 or len(matching_comments) >= 2:

                # Extract key phrases and context
                key_phrases = []
                context_parts = []

                for comment in matching_comments[:3]:
                    comment_text = comment["comment_text"]
                    # Extract meaningful phrases (avoid very short ones)
                    if len(comment_text.strip()) > 10:
                        phrase = comment_text[:80] + "..." if len(comment_text) > 80 else comment_text
                        key_phrases.append(phrase)
                        context_parts.append(f"{comment['author_name']}: {comment_text[:50]}...")

                # Create drift topic entry
                drift_topic = {
                    "topic": category_name,
                    "keywords": category_data["keywords"][:5],  # Limit keywords
                    "key_phrases": key_phrases,
                    "context": f"Discussion from {len(matching_comments)} comments: {'; '.join(context_parts[:2])}"
                }
                drift_topics.append(drift_topic)

    # Determine if meaningful drift exists
    has_drift = 1 if len(drift_topics) > 0 else 0

    if has_drift:
        return {"has_drift": 1, "drift_topics": drift_topics}
    else:
        return {"has_drift": 0, "drift_topics": None}

def update_drift_record(conn, post_id: int, analysis_result: Dict[str, Any], force_update: bool = False):
    """Update or create drift analysis result in database"""
    cursor = conn.cursor()

    # Check if record exists
    cursor.execute("SELECT post_id FROM comment_group_drift WHERE post_id = ?", (post_id,))
    existing = cursor.fetchone()

    drift_topics_json = json.dumps(analysis_result['drift_topics'], ensure_ascii=False) if analysis_result['drift_topics'] else None

    if existing and force_update:
        # Update existing record
        cursor.execute("""
            UPDATE comment_group_drift
            SET has_drift = ?,
                drift_topics = ?,
                analyzed_by = 'drift-on-synced-custom',
                analyzed_at = datetime('now')
            WHERE post_id = ?
        """, (analysis_result['has_drift'], drift_topics_json, post_id))
        print(f"  📝 Updated existing record for post {post_id}")
    elif existing:
        # Update existing record with regular analysis
        cursor.execute("""
            UPDATE comment_group_drift
            SET has_drift = ?,
                drift_topics = ?,
                analyzed_by = 'drift-on-synced',
                analyzed_at = datetime('now')
            WHERE post_id = ?
        """, (analysis_result['has_drift'], drift_topics_json, post_id))
        print(f"  📝 Updated existing record for post {post_id}")
    else:
        # Create new record - need to determine expert_id
        cursor.execute("SELECT expert_id FROM posts WHERE post_id = ?", (post_id,))
        post_expert = cursor.fetchone()
        expert_id = post_expert['expert_id'] if post_expert else 'unknown'

        cursor.execute("""
            INSERT INTO comment_group_drift
            (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, (post_id, analysis_result['has_drift'], drift_topics_json, 'drift-on-synced-custom', expert_id))
        print(f"  ➕ Created new record for post {post_id} (expert: {expert_id})")

    conn.commit()

def main():
    """Main drift analysis workflow for specific post_id 680"""
    target_post_id = 680
    print(f"🎯 Custom Drift Analysis Agent: Analyzing post_id {target_post_id}")
    print("=" * 50)

    conn = get_database_connection()

    try:
        # Get current status
        cursor = conn.cursor()
        cursor.execute("""
            SELECT post_id, expert_id, has_drift, analyzed_by, analyzed_at
            FROM comment_group_drift
            WHERE post_id = ?
        """, (target_post_id,))
        current_status = cursor.fetchone()

        if current_status:
            print(f"📊 Current status:")
            print(f"  - Post ID: {current_status['post_id']}")
            print(f"  - Expert ID: {current_status['expert_id']}")
            print(f"  - Has drift: {current_status['has_drift']}")
            print(f"  - Analyzed by: {current_status['analyzed_by']}")
            print(f"  - Analyzed at: {current_status['analyzed_at']}")
            print(f"🔄 Re-analyzing regardless of current status...")
        else:
            print(f"📊 No existing analysis found for post {target_post_id}")
            print(f"🔄 Creating new analysis...")

        # Get post content and comments
        post_content = get_post_content(conn, target_post_id)
        comments = get_comments_for_post(conn, target_post_id)

        print(f"\n📝 Content Analysis:")
        print(f"  - Post content: {post_content.get('message_text', 'N/A')[:150]}...")
        print(f"  - Found {len(comments)} comments")

        if comments:
            print(f"  - Comment preview:")
            for i, comment in enumerate(comments[:3]):
                print(f"    {i+1}. {comment['author_name']}: {comment['comment_text'][:50]}...")
            if len(comments) > 3:
                print(f"    ... and {len(comments) - 3} more comments")

        # Analyze drift
        print(f"\n🧠 Running drift analysis...")
        analysis_result = analyze_drift_for_group(post_content, comments)

        # Update database
        update_drift_record(conn, target_post_id, analysis_result, force_update=True)

        # Display results
        print(f"\n📈 DRIFT ANALYSIS RESULTS")
        print("=" * 30)

        if analysis_result["has_drift"] == 1:
            print(f"✅ Drift detected: {len(analysis_result['drift_topics'] or [])} topics")
            for i, topic in enumerate(analysis_result['drift_topics'] or [], 1):
                print(f"\n  Topic {i}: {topic['topic']}")
                print(f"    Keywords: {', '.join(topic['keywords'])}")
                print(f"    Context: {topic['context']}")
                if topic['key_phrases']:
                    print(f"    Key phrases:")
                    for phrase in topic['key_phrases'][:2]:
                        print(f"      - {phrase}")
        else:
            print(f"➖ No drift detected")

        print(f"\n✅ Custom drift analysis complete!")
        print(f"📝 Record updated in database with analyzed_by = 'drift-on-synced-custom'")

    except Exception as e:
        print(f"❌ Error analyzing post {target_post_id}: {str(e)}")
        sys.exit(1)

    finally:
        conn.close()

if __name__ == "__main__":
    main()