import asyncio
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import MODEL_DRIFT_ANALYSIS
from .vertex_llm_client import get_vertex_llm_client, VertexLLMError
from .embedding_service import get_embedding_service
from .comment_group_map_service import build_drift_text, _normalize_embedding_to_blob

logger = logging.getLogger(__name__)

class DriftSchedulerService:
    """
    Service for processing 'pending' comment groups using Gemini on Vertex AI.
    Designed for Cron Job execution with strict rate limiting.

    Uses the unified Vertex LLM client for consistent API access with
    automatic retry logic and OpenAI-compatible response format.
    """

    def __init__(self, db: Session):
        import os as _os
        self.db = db
        self.client = get_vertex_llm_client()
        self.model_name = MODEL_DRIFT_ANALYSIS
        self.backend = _os.getenv("DRIFT_BACKEND", "openrouter").lower()
        self.concurrency = max(1, int(_os.getenv("DRIFT_CONCURRENCY", "3")))
        if self.backend == "opencode":
            from .opencode_drift_client import analyze as _oc_analyze, check_serve_health
            if not check_serve_health():
                logger.warning(
                    "DRIFT_BACKEND=opencode, но opencode serve недоступен — "
                    "fallback на openrouter для этого цикла"
                )
                self.backend = "openrouter"
            else:
                self._oc_analyze = _oc_analyze
                from .opencode_drift_client import analyze_batch as _oc_batch
                self._oc_batch = _oc_batch
                self.oc_batch_size = max(1, int(_os.getenv("OPENCODE_DRIFT_BATCH_SIZE", "12")))
                logger.info(
                    f"Drift backend: opencode ({_os.getenv('OPENCODE_DRIFT_MODEL', 'x-preview-f-free')}) "
                    f"concurrency={self.concurrency}"
                )
        else:
            logger.info(f"Drift backend: openrouter ({self.model_name})")
        # Rate limiting is handled by the shared Vertex client
        # which uses Tenacity with exponential backoff + jitter
        logger.info(f"DriftSchedulerService initialized with model: {self.model_name}")

    def get_pending_count(self) -> int:
        """Count pending drift analysis groups."""
        result = self.db.execute(text(
            "SELECT COUNT(*) FROM comment_group_drift WHERE analyzed_by = 'pending'"
        ))
        return result.scalar() or 0

    def get_pending_groups(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch pending groups with their posts and comments."""
        query = text("""
            SELECT
                cgd.post_id,
                cgd.expert_id,
                p.message_text as post_text,
                p.telegram_message_id
            FROM comment_group_drift cgd
            JOIN posts p ON cgd.post_id = p.post_id
            WHERE cgd.analyzed_by = 'pending'
            ORDER BY cgd.post_id ASC
            LIMIT :limit
        """)

        results = self.db.execute(query, {"limit": limit}).fetchall()
        groups = []

        for row in results:
            # Fetch comments for this post
            comments_query = text("""
                SELECT author_name, comment_text
                FROM comments
                WHERE post_id = :post_id
                ORDER BY created_at ASC
            """)
            comments = self.db.execute(comments_query, {"post_id": row.post_id}).fetchall()

            groups.append({
                "post_id": row.post_id,
                "expert_id": row.expert_id,
                "post_text": row.post_text,
                "telegram_message_id": row.telegram_message_id,
                "comments": [{"author": c.author_name, "text": c.comment_text} for c in comments]
            })

        return groups

    def _oc_safe_single(self, group):
        """Single-group opencode retry for batch failures. Returns (group, dict|Exception)."""
        try:
            return group, self._oc_analyze(group['post_text'], group['comments'])
        except Exception as exc:
            return group, exc

    async def analyze_drift_async(self, post_text: str, comments: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze drift using Gemini through the unified Vertex client.
        Returns parsed JSON result.

        This is an async method that uses the unified Vertex LLM client
        which handles retry logic and OpenAI-compatible response format.
        """
        comments_text = "\n".join([f"- {c['author']}: {c['text']}" for c in comments])

        prompt = f"""Analyze this Telegram post and its comments to determine if the discussion DRIFTED to other topics.

POST (anchor):
{post_text[:1000]}...

COMMENTS:
{comments_text[:3000]}

TASK:
1. Determine if comments discuss topics NOT mentioned in the post
2. If yes (drift detected), extract drift topics with:
   - topic: General theme (1-2 sentences)
   - keywords: Specific terms, technologies, names (array)
   - key_phrases: Direct quotes from comments (array, 1-3 phrases)
   - context: Brief explanation (1 sentence)

CRITERIA FOR DRIFT:
✅ DRIFT:
- Comments ask about/discuss technologies/concepts not in post
- Discussion moves to different subject area
- New specific questions with detailed answers

❌ NOT DRIFT:
- Comments just expand on post topic
- Questions clarifying post content
- Generic reactions/thanks

CONFIDENCE:
- high: Clear drift, obvious new topics
- medium: Partial drift, some new elements
- low: Unclear if drift or just expansion

Return ONLY valid JSON:
{{
  "has_drift": true/false,
  "confidence": "high|medium|low",
  "drift_topics": [
    {{
      "topic": "...",
      "keywords": ["..."],
      "key_phrases": ["..."],
      "context": "..."
    }}
  ] or null
}}"""

        try:
            response = await self.client.chat_completions_create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            # Parse OpenAI-compatible response format
            text_response = response.choices[0].message.content.strip()

            # Robust JSON extraction (same as original)
            try:
                parsed = json.loads(text_response)
            except json.JSONDecodeError:
                # Heuristic extraction
                idx_brace = text_response.find('{')
                idx_bracket = text_response.find('[')

                start_idx = -1
                end_idx = -1

                if idx_brace != -1 and idx_bracket != -1:
                    if idx_brace < idx_bracket:
                        start_idx = idx_brace
                        end_idx = text_response.rfind('}')
                    else:
                        start_idx = idx_bracket
                        end_idx = text_response.rfind(']')
                elif idx_brace != -1:
                    start_idx = idx_brace
                    end_idx = text_response.rfind('}')
                elif idx_bracket != -1:
                    start_idx = idx_bracket
                    end_idx = text_response.rfind(']')

                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = text_response[start_idx : end_idx + 1]
                    try:
                        parsed = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse extracted JSON: {json_str[:100]}... Error: {e}")
                        raise ValueError(f"Gemini returned invalid JSON structure even after extraction.")
                else:
                    raise ValueError(f"Could not find valid JSON object in response: {text_response[:100]}")

            # Validate structure
            if isinstance(parsed, list):
                if len(parsed) > 0 and isinstance(parsed[0], dict):
                    return parsed[0]
                raise ValueError(f"Gemini returned invalid list structure: {str(parsed)[:100]}")

            if not isinstance(parsed, dict):
                raise ValueError(f"Gemini returned non-dict JSON: {type(parsed)}")

            return parsed

        except VertexLLMError as e:
            # The unified client handles rate limit retries automatically
            # If we still get an error here, log and re-raise
            if e.is_rate_limit:
                logger.error(f"Rate limit error after retries: {str(e)}")
            else:
                logger.error(f"Vertex LLM error: {str(e)}")
            raise



    def update_group_status(
        self,
        post_id: int,
        analysis_result: Dict[str, Any],
        drift_embedding: Optional[bytes] = None,
        analyzed_by_label: str = 'drift_checked_gemini',
    ):
        """Update database with analysis results.

        ``drift_embedding`` is the pre-computed numpy.float32 vector
        serialized via ``.tobytes()``. Stored as BLOB alongside ``drift_topics``
        for fast cosine similarity at query time.
        """

        has_drift = analysis_result.get("has_drift", False)
        drift_topics = analysis_result.get("drift_topics")

        # Ensure drift_topics is valid JSON string or NULL
        drift_topics_json = None
        if has_drift and drift_topics:
            drift_data = {
                "has_drift": has_drift,
                "drift_topics": drift_topics
            }
            drift_topics_json = json.dumps(drift_data, ensure_ascii=False)

        update_query = text("""
            UPDATE comment_group_drift
            SET
                has_drift = :has_drift,
                drift_topics = :drift_topics,
                drift_embedding = :drift_embedding,
                analyzed_by = :analyzed_by,
                analyzed_at = datetime('now')
            WHERE post_id = :post_id
        """)

        self.db.execute(update_query, {
            "post_id": post_id,
            "has_drift": 1 if has_drift else 0,
            "drift_topics": drift_topics_json,
            "drift_embedding": drift_embedding,
            "analyzed_by": analyzed_by_label,
        })
        self.db.commit()

    async def process_batch(self, batch_size: int = 10):
        """Process a batch of pending groups."""
        groups = self.get_pending_groups(limit=batch_size)

        if not groups:
            logger.info("No pending groups found.")
            return 0

        logger.info(f"Starting processing batch of {len(groups)} groups "
                    f"(backend={self.backend}, concurrency={self.concurrency if self.backend == 'opencode' else 1})")

        success_count = 0

        # Empty-comment groups: mark serially, they need no LLM.
        todo = []
        for group in groups:
            if not group['comments']:
                logger.info(f"Post {group['post_id']} has no comments, marking no-comments")
                self.db.execute(text("""
                    UPDATE comment_group_drift
                    SET analyzed_by = 'no-comments', analyzed_at = datetime('now')
                    WHERE post_id = :pid
                """), {"pid": group['post_id']})
                self.db.commit()
                success_count += 1
            else:
                todo.append(group)

        # ── LLM phase: parallel for opencode, sequential for openrouter ──
        llm_results: list = []  # (group, dict_result | Exception)
        if self.backend == "opencode":
            import asyncio as _asyncio
            from concurrent.futures import ThreadPoolExecutor as _Pool

            batches = [todo[i:i + self.oc_batch_size]
                       for i in range(0, len(todo), self.oc_batch_size)]
            logger.info(f"Packing {len(todo)} groups into {len(batches)} "
                        f"batch call(s) of <= {self.oc_batch_size}")

            def _batch_worker(batch):
                try:
                    return self._oc_batch(batch)
                except Exception as exc:
                    logger.warning(f"Batch of {len(batch)} failed wholesale: {str(exc)[:120]}")
                    return {}

            loop = _asyncio.get_running_loop()
            with _Pool(max_workers=self.concurrency) as pool:
                batch_results = list(await asyncio.gather(*[
                    loop.run_in_executor(pool, _batch_worker, b) for b in batches
                ]))

            merged: dict = {}
            for br in batch_results:
                merged.update(br or {})

            # Groups the model skipped/mangled get an individual retry.
            fallback = [g for g in todo if g['post_id'] not in merged]
            if fallback:
                logger.warning(f"{len(fallback)} group(s) missing from batch "
                               f"responses — individual retry")
                with _Pool(max_workers=self.concurrency) as pool:
                    fb_results = list(await asyncio.gather(*[
                        loop.run_in_executor(pool, self._oc_safe_single, g) for g in fallback
                    ]))

            for g in todo:
                r = merged.get(g['post_id'])
                if r is not None:
                    llm_results.append((g, r))
            for g, r in (fb_results if fallback else []):
                llm_results.append((g, r))
        else:
            for group in todo:
                logger.info(f"Analyzing post {group['post_id']} ({len(group['comments'])} comments)...")
                try:
                    result = await self.analyze_drift_async(group['post_text'], group['comments'])
                    llm_results.append((group, result))
                except Exception as e:
                    llm_results.append((group, e))

        # ── DB phase: strictly serial (SQLite single-writer discipline) ──
        backend_label = f'drift_checked_{self.backend}'
        for group, res_or_exc in llm_results:
            try:
                if isinstance(res_or_exc, Exception):
                    raise res_or_exc
                result = res_or_exc

                # Embed drift_topics for fast query-time scoring (cosine similarity).
                # Failures are non-fatal: row stays with drift_topics but no embedding,
                # and the query path will fall back to the LLM chunked scoring.
                drift_embedding_bytes: Optional[bytes] = None
                if result.get("has_drift") and result.get("drift_topics"):
                    text_repr = build_drift_text(json.dumps(
                        {"has_drift": True, "drift_topics": result["drift_topics"]},
                        ensure_ascii=False,
                    ))
                    if text_repr:
                        try:
                            embedding_service = get_embedding_service()
                            embedding = await embedding_service.embed_text(
                                text_repr, task_type="RETRIEVAL_DOCUMENT"
                            )
                            # Storage contract: stored vectors must be unit-length
                            # so _score_by_embedding can skip matrix normalize.
                            try:
                                drift_embedding_bytes = _normalize_embedding_to_blob(
                                    embedding
                                )
                            except ValueError as norm_exc:
                                logger.warning(
                                    f"Skipping embedding for post "
                                    f"{group['post_id']}: {norm_exc}"
                                )
                                drift_embedding_bytes = None
                        except Exception as embed_exc:
                            logger.warning(
                                f"Failed to embed drift for post {group['post_id']}: {embed_exc}"
                            )

                # Update DB
                self.update_group_status(
                    group['post_id'], result, drift_embedding=drift_embedding_bytes,
                    analyzed_by_label=backend_label,
                )

                if result.get('has_drift'):
                    logger.info(f"✅ DRIFT DETECTED for post {group['post_id']}")

            except Exception as e:
                logger.error(f"❌ Error analyzing post {group['post_id']}: {str(e)}")
                # Mark as error so we don't loop forever
                self.db.execute(text("""
                    UPDATE comment_group_drift
                    SET analyzed_by = 'error', analyzed_at = datetime('now')
                    WHERE post_id = :pid
                """), {"pid": group['post_id']})
                self.db.commit()
                continue

            success_count += 1

        logger.info(f"Batch complete. Processed {success_count}/{len(groups)} successfully.")
        return len(groups)

    async def run_full_cycle(self):
        """Run until no pending groups remain."""
        total_pending = self.get_pending_count()
        logger.info(f"🚀 Starting Drift Scheduler Cycle ({total_pending} groups pending)")

        if total_pending == 0:
            logger.info("✅ No pending groups. Nothing to do.")
            return

        total_processed = 0

        while True:
            count = await self.process_batch(batch_size=10)
            total_processed += count
            if count == 0:
                break

            remaining = self.get_pending_count()
            logger.info(f"📊 Progress: {total_processed}/{total_pending} processed, {remaining} remaining")

            # Extra cooldown between batches
            logger.info("Batch cooldown (10s)...")
            await asyncio.sleep(10)

        logger.info(f"🏁 Cycle complete. Total processed: {total_processed}/{total_pending}")
