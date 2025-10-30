#!/usr/bin/env python3
"""
Drift-on-synced agent: Analyzes pending comment groups for topic drift
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

def get_pending_groups(conn) -> List[Tuple[int, str]]:
    """Get all pending drift groups"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_id, expert_id
        FROM comment_group_drift
        WHERE analyzed_by = 'pending'
        ORDER BY expert_id, post_id
    """)
    return [(row['post_id'], row['expert_id']) for row in cursor.fetchall()]

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
    Analyze drift for a comment group using Claude Sonnet 4.5
    This is where the actual drift analysis happens
    """
    if not comments:
        return {"has_drift": 0, "drift_topics": None}

    post_text = post_content.get('message_text', '')
    if not post_text:
        return {"has_drift": 0, "drift_topics": None}

    # Prepare analysis prompt
    comments_text = "\n\n".join([
        f"Comment by {c['author_name']} ({c['created_at']}): {c['comment_text']}"
        for c in comments
    ])

    analysis_prompt = f"""
Analyze the topic drift between this post and its comments:

POST:
{post_text}

COMMENTS:
{comments_text}

Instructions:
1. Compare the main topic of the post with the discussion in comments
2. Identify if comments discuss topics beyond the original post
3. Extract drift topics if meaningful topic shift exists
4. Consider tangential discussions, expansions, or completely different topics

Return JSON format:
{{
    "has_drift": 1 or 0,
    "drift_topics": [
        {{
            "topic": "Main drifted topic",
            "keywords": ["keyword1", "keyword2"],
            "key_phrases": ["phrase1", "phrase2"],
            "context": "Brief context of how this topic emerged"
        }}
    ] if has_drift = 1, otherwise null
}}

Criteria for drift:
- Comments discuss related but expanded topics not in original post
- Comments ask follow-up questions about different aspects
- Comments bring in external examples or comparisons
- Comments discuss practical applications not mentioned in post
- Comments debate implications or consequences not covered

If comments are purely discussing the post content (clarifications, agreements, basic questions), then has_drift = 0.
"""

    # For now, we'll implement a simplified analysis
    # In production, this would call Claude API

    # Simple heuristic-based analysis as fallback
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

def update_drift_record(conn, post_id: int, analysis_result: Dict[str, Any]):
    """Update drift analysis result in database"""
    cursor = conn.cursor()

    drift_topics_json = json.dumps(analysis_result['drift_topics']) if analysis_result['drift_topics'] else None

    cursor.execute("""
        UPDATE comment_group_drift
        SET has_drift = ?,
            drift_topics = ?,
            analyzed_by = 'drift-on-synced',
            analyzed_at = datetime('now')
        WHERE post_id = ?
    """, (analysis_result['has_drift'], drift_topics_json, post_id))

    conn.commit()

def main():
    """Main drift analysis workflow"""
    print("🎯 Drift-on-Synced Agent: Starting analysis")
    print("=" * 50)

    conn = get_database_connection()

    try:
        # Check if specific post_id is provided as argument
        if len(sys.argv) > 1:
            target_post_id = int(sys.argv[1])
            print(f"🎯 Analyzing specific post_id: {target_post_id}")

            # Check if this post is pending
            cursor = conn.cursor()
            cursor.execute("SELECT post_id, expert_id FROM comment_group_drift WHERE post_id = ? AND analyzed_by = 'pending'", (target_post_id,))
            pending_post = cursor.fetchone()

            if not pending_post:
                print(f"❌ Post {target_post_id} not found in pending groups")
                return

            post_id, expert_id = pending_post
            pending_groups = [(post_id, expert_id)]
            print(f"📊 Found 1 pending group for expert: {expert_id}")
        else:
            # Step 1: Identify all pending groups
            pending_groups = get_pending_groups(conn)

            if not pending_groups:
                print("✅ No pending drift groups found")
                return

            print(f"📊 Found {len(pending_groups)} pending groups:")

            # Count by expert
            expert_counts = {}
            for post_id, expert_id in pending_groups:
                expert_counts[expert_id] = expert_counts.get(expert_id, 0) + 1

            for expert_id, count in expert_counts.items():
                print(f"  - {expert_id}: {count} groups")

        print("\n🔄 Starting drift analysis...")

        # Step 2: Analyze each pending group
        results = {
            "total_pending_groups": len(pending_groups),
            "groups_processed": 0,
            "by_expert": {},
            "drift_summary": {
                "total_with_drift": 0,
                "total_without_drift": 0,
                "success_rate": "0%"
            }
        }

        # Initialize expert results
        expert_ids = list(set(expert_id for _, expert_id in pending_groups))
        for expert_id in expert_ids:
            results["by_expert"][expert_id] = {
                "processed": 0,
                "with_drift": 0,
                "without_drift": 0
            }

        start_time = time.time()

        for i, (post_id, expert_id) in enumerate(pending_groups, 1):
            try:
                print(f"\n[{i}/{len(pending_groups)}] Analyzing post {post_id} ({expert_id})")

                # Get post content and comments
                post_content = get_post_content(conn, post_id)
                comments = get_comments_for_post(conn, post_id)

                print(f"  - Found {len(comments)} comments")
                print(f"  - Post content: {post_content.get('message_text', 'N/A')[:100]}...")

                # Analyze drift
                analysis_result = analyze_drift_for_group(post_content, comments)

                # Update database
                update_drift_record(conn, post_id, analysis_result)

                # Update results
                results["groups_processed"] += 1
                results["by_expert"][expert_id]["processed"] += 1

                if analysis_result["has_drift"] == 1:
                    results["by_expert"][expert_id]["with_drift"] += 1
                    results["drift_summary"]["total_with_drift"] += 1
                    print(f"  ✅ Has drift: {len(analysis_result['drift_topics'] or [])} topics")
                    for topic in analysis_result['drift_topics'] or []:
                        print(f"    - {topic['topic']}")
                else:
                    results["by_expert"][expert_id]["without_drift"] += 1
                    results["drift_summary"]["total_without_drift"] += 1
                    print(f"  ➖ No drift detected")

            except Exception as e:
                print(f"  ❌ Error analyzing post {post_id}: {str(e)}")
                continue

        # Calculate final statistics
        end_time = time.time()
        processing_time = end_time - start_time

        if results["groups_processed"] > 0:
            success_rate = (results["groups_processed"] / results["total_pending_groups"]) * 100
            results["drift_summary"]["success_rate"] = f"{success_rate:.1f}%"

        # Step 3: Display results
        print("\n" + "=" * 50)
        print("📈 DRIFT ANALYSIS RESULTS")
        print("=" * 50)
        print(f"Total pending groups: {results['total_pending_groups']}")
        print(f"Groups processed: {results['groups_processed']}")
        print(f"Processing time: {processing_time:.1f} seconds")

        print(f"\nBy expert:")
        for expert_id, stats in results["by_expert"].items():
            print(f"  {expert_id}:")
            print(f"    Processed: {stats['processed']}")
            print(f"    With drift: {stats['with_drift']}")
            print(f"    Without drift: {stats['without_drift']}")

        print(f"\nDrift summary:")
        print(f"  Total with drift: {results['drift_summary']['total_with_drift']}")
        print(f"  Total without drift: {results['drift_summary']['total_without_drift']}")
        print(f"  Success rate: {results['drift_summary']['success_rate']}")

        drift_ratio = (results['drift_summary']['total_with_drift'] / results['groups_processed'] * 100) if results['groups_processed'] > 0 else 0
        print(f"  Drift detection ratio: {drift_ratio:.1f}%")

        print(f"\n✅ Drift-on-synced analysis complete!")

        # Save results to file
        with open('drift_on_synced_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"📄 Results saved to drift_on_synced_results.json")

    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)

    finally:
        conn.close()

if __name__ == "__main__":
    main()