"""Shadow Testing Service for Super-Passport Search.

Compares FTS5 pre-filtering vs standard pipeline to measure:
- Recall: % of posts found by both methods
- Latency: Time difference between methods
- Token cost: Estimated token savings

Results are logged for analysis and A/B testing decisions.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.post import Post
from ..config import MAX_FTS_RESULTS

logger = logging.getLogger(__name__)


class ShadowTestingService:
    """Service for comparing FTS5 vs standard pipeline results.

    Runs both methods in parallel (shadow mode) and logs comparison metrics.
    Does NOT affect user-facing results - only for internal analysis.
    """

    def __init__(self, db: Session):
        self.db = db
        self.results: List[Dict[str, Any]] = []

    def compare_retrieval(
        self,
        expert_id: str,
        fts5_post_ids: List[int],
        standard_post_ids: List[int],
        query: str,
        latency_fts5_ms: float,
        latency_standard_ms: float
    ) -> Dict[str, Any]:
        """Compare FTS5 vs standard retrieval results.

        Args:
            expert_id: Expert identifier
            fts5_post_ids: Post IDs from FTS5 retrieval
            standard_post_ids: Post IDs from standard retrieval
            query: Original user query
            latency_fts5_ms: FTS5 retrieval time in ms
            latency_standard_ms: Standard retrieval time in ms

        Returns:
            Comparison metrics dictionary
        """
        fts5_set = set(fts5_post_ids)
        standard_set = set(standard_post_ids)

        # Calculate metrics
        intersection = fts5_set & standard_set
        fts5_only = fts5_set - standard_set
        standard_only = standard_set - fts5_set

        # Recall: % of standard posts found by FTS5
        recall = len(intersection) / len(standard_set) if standard_set else 0.0

        # Precision: % of FTS5 posts that are in standard
        precision = len(intersection) / len(fts5_set) if fts5_set else 0.0

        # Token savings estimate (assuming ~1300 chars per post, ~0.33 tokens/char)
        posts_saved = len(standard_set) - len(fts5_set)
        tokens_saved_estimate = max(0, posts_saved * 1300 * 0.33)

        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "expert_id": expert_id,
            "query_preview": query[:50] + "..." if len(query) > 50 else query,
            "fts5_count": len(fts5_set),
            "standard_count": len(standard_set),
            "intersection_count": len(intersection),
            "fts5_only_count": len(fts5_only),
            "standard_only_count": len(standard_only),
            "recall": round(recall, 3),
            "precision": round(precision, 3),
            "latency_fts5_ms": round(latency_fts5_ms, 2),
            "latency_standard_ms": round(latency_standard_ms, 2),
            "latency_improvement_pct": round(
                (latency_standard_ms - latency_fts5_ms) / latency_standard_ms * 100, 2
            ) if latency_standard_ms > 0 else 0,
            "tokens_saved_estimate": round(tokens_saved_estimate),
            "fts5_post_ids": list(fts5_post_ids)[:10],  # First 10 for debugging
            "standard_post_ids": list(standard_post_ids)[:10]
        }

        # Log results
        logger.info(
            f"[Shadow Test] {expert_id}: "
            f"recall={recall:.1%}, "
            f"latency={latency_fts5_ms:.0f}ms vs {latency_standard_ms:.0f}ms, "
            f"tokens_saved≈{tokens_saved_estimate:.0f}"
        )

        # Store for later analysis
        self.results.append(result)

        return result

    def get_standard_post_ids(
        self,
        expert_id: str,
        cutoff_date: Optional[datetime] = None,
        max_posts: Optional[int] = None
    ) -> List[int]:
        """Get post IDs using standard retrieval (for comparison).

        Args:
            expert_id: Expert identifier
            cutoff_date: Optional date filter
            max_posts: Optional limit

        Returns:
            List of post IDs from standard retrieval
        """
        query = self.db.query(Post.post_id).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30
        )

        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)

        query = query.order_by(Post.created_at.desc())

        limit = min(max_posts, MAX_FTS_RESULTS) if max_posts else MAX_FTS_RESULTS
        query = query.limit(limit)

        return [row[0] for row in query.all()]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics across all shadow tests.

        Returns:
            Aggregate statistics dictionary
        """
        if not self.results:
            return {"message": "No shadow tests run yet"}

        recalls = [r["recall"] for r in self.results]
        latency_improvements = [r["latency_improvement_pct"] for r in self.results]
        tokens_saved = [r["tokens_saved_estimate"] for r in self.results]

        return {
            "total_tests": len(self.results),
            "avg_recall": round(sum(recalls) / len(recalls), 3),
            "min_recall": round(min(recalls), 3),
            "max_recall": round(max(recalls), 3),
            "avg_latency_improvement_pct": round(
                sum(latency_improvements) / len(latency_improvements), 2
            ),
            "total_tokens_saved_estimate": round(sum(tokens_saved)),
            "tests_with_perfect_recall": sum(1 for r in recalls if r >= 0.99),
            "tests_with_poor_recall": sum(1 for r in recalls if r < 0.8),
        }

    def export_results(self, filepath: str) -> None:
        """Export shadow test results to JSON file.

        Args:
            filepath: Path to save results
        """
        output = {
            "summary": self.get_summary_stats(),
            "results": self.results
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"[Shadow Test] Exported {len(self.results)} results to {filepath}")
