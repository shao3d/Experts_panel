#!/usr/bin/env python3
"""Export a full-context semantic passport packet for one expert.

The script is deliberately read-only. It prepares the corpus, prompt, schema,
and manifest needed for a high-fidelity Gemini/Vertex semantic passport run,
but it does not call Vertex AI by itself.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "experts.db"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "expert_admission" / "semantic_passports"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
SCHEMA_VERSION = "expert_value_passport.v1.1"
PROMPT_VERSION = "semantic-passport-prompt.v1"
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Expert:
    expert_id: str
    display_name: str
    channel_username: str


@dataclass(frozen=True)
class Post:
    source_ref: str
    post_id: int
    telegram_message_id: int
    created_at: str | None
    view_count: int | None
    forward_count: int | None
    reply_count: int | None
    text: str


@dataclass(frozen=True)
class Comment:
    source_ref: str
    comment_id: int
    telegram_comment_id: int | None
    post_id: int
    author_name: str
    created_at: str | None
    text: str


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def estimate_tokens_from_chars(char_count: int) -> dict[str, int]:
    return {
        "chars_div_4": round(char_count / 4),
        "chars_div_3_5": round(char_count / 3.5),
        "chars_div_3": round(char_count / 3),
    }


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_expert(conn: sqlite3.Connection, expert_id: str) -> Expert:
    row = conn.execute(
        """
        SELECT expert_id, display_name, channel_username
        FROM expert_metadata
        WHERE expert_id = ?
        """,
        (expert_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"Expert not found: {expert_id}")
    return Expert(
        expert_id=row["expert_id"],
        display_name=row["display_name"],
        channel_username=row["channel_username"],
    )


def fetch_posts(
    conn: sqlite3.Connection,
    expert_id: str,
    max_posts: int | None,
) -> list[Post]:
    limit_clause = "" if max_posts is None else " LIMIT ?"
    params: list[Any] = [expert_id]
    if max_posts is not None:
        params.append(max_posts)

    rows = conn.execute(
        f"""
        SELECT
            post_id,
            telegram_message_id,
            created_at,
            view_count,
            forward_count,
            reply_count,
            message_text
        FROM posts
        WHERE expert_id = ?
          AND LENGTH(COALESCE(message_text, '')) > 0
        ORDER BY datetime(created_at), telegram_message_id, post_id
        {limit_clause}
        """,
        params,
    ).fetchall()

    posts: list[Post] = []
    for idx, row in enumerate(rows, start=1):
        posts.append(
            Post(
                source_ref=f"P{idx:04d}",
                post_id=int(row["post_id"]),
                telegram_message_id=int(row["telegram_message_id"]),
                created_at=row["created_at"],
                view_count=row["view_count"],
                forward_count=row["forward_count"],
                reply_count=row["reply_count"],
                text=normalize_text(row["message_text"]),
            )
        )
    return posts


def fetch_comments(
    conn: sqlite3.Connection,
    expert_id: str,
    post_refs_by_id: dict[int, str],
    max_comments_per_post: int | None,
) -> dict[int, list[Comment]]:
    rows = conn.execute(
        """
        SELECT
            c.comment_id,
            c.telegram_comment_id,
            c.post_id,
            c.author_name,
            c.created_at,
            c.comment_text
        FROM comments c
        JOIN posts p ON p.post_id = c.post_id
        WHERE p.expert_id = ?
        ORDER BY c.post_id, datetime(c.created_at), c.telegram_comment_id, c.comment_id
        """,
        (expert_id,),
    ).fetchall()

    grouped: dict[int, list[Comment]] = {post_id: [] for post_id in post_refs_by_id}
    per_post_counts: dict[int, int] = {post_id: 0 for post_id in post_refs_by_id}

    for row in rows:
        post_id = int(row["post_id"])
        if post_id not in post_refs_by_id:
            continue
        if max_comments_per_post is not None and per_post_counts[post_id] >= max_comments_per_post:
            continue
        per_post_counts[post_id] += 1
        source_ref = f"{post_refs_by_id[post_id]}.C{per_post_counts[post_id]:04d}"
        grouped.setdefault(post_id, []).append(
            Comment(
                source_ref=source_ref,
                comment_id=int(row["comment_id"]),
                telegram_comment_id=row["telegram_comment_id"],
                post_id=post_id,
                author_name=normalize_text(row["author_name"]),
                created_at=row["created_at"],
                text=normalize_text(row["comment_text"]),
            )
        )

    return grouped


def build_schema() -> dict[str, Any]:
    """Return the machine-comparable passport schema expected from the model."""

    return {
        "schema_version": SCHEMA_VERSION,
        "type": "object",
        "required": [
            "passport_meta",
            "corpus_audit",
            "source_ref_index_used",
            "executive_summary",
            "expert_positioning",
            "knowledge_domains",
            "value_dimensions",
            "matrix_cells",
            "query_intent_fit",
            "content_quality_distribution",
            "matrix_export",
            "signature_insights",
            "practical_patterns",
            "claims_and_positions",
            "source_utility",
            "community_signal",
            "admission_implications",
            "audit",
        ],
        "properties": {
            "passport_meta": {
                "type": "object",
                "required": [
                    "schema_version",
                    "expert_id",
                    "display_name",
                    "channel_username",
                    "model_assumed",
                    "prompt_version",
                    "generated_at",
                ],
                "properties": {
                    "schema_version": {"const": SCHEMA_VERSION},
                    "expert_id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "channel_username": {"type": "string"},
                    "model_assumed": {"type": "string"},
                    "prompt_version": {"const": PROMPT_VERSION},
                    "generated_at": {"type": "string"},
                },
            },
            "corpus_audit": {
                "type": "object",
                "properties": {
                    "post_count_seen": {"type": "integer"},
                    "comment_count_seen": {"type": "integer"},
                    "date_range": {"type": "object"},
                    "language_mix": {"type": "array"},
                    "material_limitations": {"type": "array"},
                    "author_vs_community_boundary": {"type": "string"},
                },
            },
            "source_ref_index_used": {
                "type": "array",
                "description": "Only source refs actually cited in the passport. The full source_ref_index is exported by the packet builder.",
                "items": {
                    "type": "object",
                    "required": ["source_ref", "source_kind", "post_id", "created_at", "why_used"],
                    "properties": {
                        "source_ref": {"type": "string"},
                        "source_kind": {"enum": ["expert_post", "community_comment"]},
                        "post_id": {"type": "integer"},
                        "telegram_message_id": {"type": ["integer", "null"]},
                        "comment_id": {"type": ["integer", "null"]},
                        "telegram_comment_id": {"type": ["integer", "null"]},
                        "created_at": {"type": ["string", "null"]},
                        "why_used": {"type": "string"},
                    },
                },
            },
            "executive_summary": {
                "type": "object",
                "properties": {
                    "one_sentence_positioning": {"type": "string"},
                    "strongest_system_value": {"type": "string"},
                    "weakest_system_value": {"type": "string"},
                    "best_fit_queries": {"type": "array"},
                    "poor_fit_queries": {"type": "array"},
                    "confidence": {"type": "number"},
                },
            },
            "expert_positioning": {
                "type": "object",
                "properties": {
                    "primary_role": {"type": "string"},
                    "audience": {"type": "array"},
                    "voice": {"type": "array"},
                    "worldview": {"type": "array"},
                    "distinctive_angle": {"type": "string"},
                    "recurring_formats": {"type": "array"},
                    "evidence_refs": {"type": "array"},
                },
            },
            "knowledge_domains": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "domain_id",
                        "domain_name",
                        "coverage_level",
                        "depth_level",
                        "system_value",
                        "evidence_refs",
                    ],
                    "properties": {
                        "domain_id": {"type": "string"},
                        "domain_name": {"type": "string"},
                        "subdomain_ids": {"type": "array"},
                        "query_intent_ids": {"type": "array"},
                        "coverage_level": {"enum": ["none", "thin", "moderate", "strong"]},
                        "depth_level": {
                            "enum": ["none", "news", "commentary", "practical", "deep_practitioner"]
                        },
                        "system_value": {"enum": ["none", "low", "medium", "high", "unique"]},
                        "what_the_expert_knows": {"type": "array"},
                        "how_they_reason": {"type": "array"},
                        "missing_or_weak_subtopics": {"type": "array"},
                        "evidence_refs": {"type": "array"},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "value_dimensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["dimension_id", "score_0_5", "rationale", "evidence_refs"],
                    "properties": {
                        "dimension_id": {"type": "string"},
                        "score_0_5": {"type": "number"},
                        "rationale": {"type": "string"},
                        "evidence_refs": {"type": "array"},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "matrix_cells": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "domain_id",
                        "subdomain_id",
                        "query_intent_ids",
                        "depth_score_0_5",
                        "practicality_score_0_5",
                        "intrinsic_distinctiveness_score_0_5",
                        "evidence_quality_score_0_5",
                        "source_utility_score_0_5",
                        "evidence_refs",
                    ],
                    "properties": {
                        "domain_id": {"type": "string"},
                        "subdomain_id": {"type": "string"},
                        "subdomain_name": {"type": "string"},
                        "query_intent_ids": {"type": "array"},
                        "depth_score_0_5": {"type": "number"},
                        "practicality_score_0_5": {"type": "number"},
                        "intrinsic_distinctiveness_score_0_5": {"type": "number"},
                        "matrix_relative_novelty": {"const": "not_scored_without_matrix"},
                        "evidence_quality_score_0_5": {"type": "number"},
                        "source_utility_score_0_5": {"type": "number"},
                        "comment_signal_score_0_5": {"type": "number"},
                        "recommended_matrix_weight": {
                            "enum": ["ignore", "weak", "normal", "strong", "signature"]
                        },
                        "evidence_refs": {"type": "array"},
                        "notes": {"type": "string"},
                    },
                },
            },
            "query_intent_fit": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "query_intent_id",
                        "fit_role",
                        "source_utility_score_0_5",
                        "evidence_refs",
                    ],
                    "properties": {
                        "query_intent_id": {"type": "string"},
                        "query_intent_name": {"type": "string"},
                        "fit_role": {
                            "enum": ["primary", "supporting", "niche", "weak", "bad_fit", "unknown"]
                        },
                        "best_domain_ids": {"type": "array"},
                        "source_utility_score_0_5": {"type": "number"},
                        "why": {"type": "string"},
                        "limitations": {"type": "array"},
                        "evidence_refs": {"type": "array"},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "content_quality_distribution": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["category_id", "share_estimate_0_1", "system_value", "evidence_refs"],
                    "properties": {
                        "category_id": {
                            "enum": [
                                "deep_practitioner",
                                "case_study",
                                "architecture_analysis",
                                "howto_or_checklist",
                                "benchmark_or_eval",
                                "tool_release_with_analysis",
                                "commentary",
                                "announcement_or_news",
                                "low_signal",
                            ]
                        },
                        "share_estimate_0_1": {"type": "number"},
                        "system_value": {"enum": ["none", "low", "medium", "high"]},
                        "notes": {"type": "string"},
                        "evidence_refs": {"type": "array"},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "matrix_export": {
                "type": "object",
                "required": ["schema_version", "expert_id", "cells", "compare_hints"],
                "properties": {
                    "schema_version": {"const": "knowledge_matrix_export.v1"},
                    "expert_id": {"type": "string"},
                    "cells": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "cell_id",
                                "domain_id",
                                "subdomain_id",
                                "query_intent_ids",
                                "coverage_level",
                                "depth_level",
                                "source_role",
                                "scores",
                                "evidence_refs",
                            ],
                            "properties": {
                                "cell_id": {"type": "string"},
                                "domain_id": {"type": "string"},
                                "subdomain_id": {"type": "string"},
                                "subdomain_name": {"type": "string"},
                                "query_intent_ids": {"type": "array"},
                                "coverage_level": {
                                    "enum": ["none", "thin", "moderate", "strong"]
                                },
                                "depth_level": {
                                    "enum": [
                                        "none",
                                        "news",
                                        "commentary",
                                        "practical",
                                        "deep_practitioner",
                                    ]
                                },
                                "source_role": {
                                    "enum": ["primary", "supporting", "niche", "weak", "avoid"]
                                },
                                "scores": {
                                    "type": "object",
                                    "properties": {
                                        "depth": {"type": "number"},
                                        "practicality": {"type": "number"},
                                        "evidence_quality": {"type": "number"},
                                        "source_utility": {"type": "number"},
                                        "intrinsic_distinctiveness": {"type": "number"},
                                        "anti_hype": {"type": "number"},
                                        "community_signal": {"type": "number"},
                                    },
                                },
                                "matrix_update_role": {
                                    "enum": [
                                        "fills_gap",
                                        "deepens_existing_cell",
                                        "adds_viewpoint",
                                        "likely_duplicate",
                                        "noise_risk",
                                        "needs_matrix_compare",
                                    ]
                                },
                                "limitations": {"type": "array"},
                                "evidence_refs": {"type": "array"},
                                "confidence": {"type": "number"},
                            },
                        },
                    },
                    "compare_hints": {
                        "type": "object",
                        "properties": {
                            "likely_unique_cells": {"type": "array"},
                            "likely_duplicate_cells": {"type": "array"},
                            "cells_requiring_probe": {"type": "array"},
                            "matrix_only_decision_confidence": {
                                "enum": ["low", "medium", "high"]
                            },
                        },
                    },
                },
            },
            "signature_insights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "insight": {"type": "string"},
                        "why_it_matters_for_experts_panel": {"type": "string"},
                        "applicable_query_types": {"type": "array"},
                        "novelty_level": {"enum": ["common", "useful_packaging", "distinctive", "rare"]},
                        "evidence_refs": {"type": "array"},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "practical_patterns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "when_to_use": {"type": "string"},
                        "failure_modes": {"type": "array"},
                        "evidence_refs": {"type": "array"},
                    },
                },
            },
            "claims_and_positions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "stance": {"enum": ["supports", "warns_against", "mixed", "unclear"]},
                        "decision_relevance": {"type": "string"},
                        "dispute_risk": {"enum": ["low", "medium", "high"]},
                        "evidence_refs": {"type": "array"},
                    },
                },
            },
            "source_utility": {
                "type": "object",
                "properties": {
                    "best_use_cases": {"type": "array"},
                    "bad_use_cases": {"type": "array"},
                    "retrieval_keywords": {"type": "array"},
                    "source_selection_hints": {"type": "array"},
                    "expected_overlap_hypotheses": {"type": "array"},
                    "recommended_panex_role": {
                        "enum": [
                            "primary_expert",
                            "supporting_expert",
                            "niche_expert",
                            "watchlist_only",
                            "not_recommended",
                        ]
                    },
                },
            },
            "community_signal": {
                "type": "object",
                "properties": {
                    "comment_themes": {"type": "array"},
                    "questions_from_audience": {"type": "array"},
                    "disagreements_or_corrections": {"type": "array"},
                    "practical_feedback": {"type": "array"},
                    "noise_or_low_value_patterns": {"type": "array"},
                    "evidence_refs": {"type": "array"},
                },
            },
            "admission_implications": {
                "type": "object",
                "properties": {
                    "if_candidate_verdict": {
                        "enum": ["accept", "limited_scope", "watchlist", "reject", "needs_matrix_compare"]
                    },
                    "verdict_rationale": {"type": "string"},
                    "unique_value_claims_to_verify_against_matrix": {"type": "array"},
                    "likely_duplicate_areas_to_check": {"type": "array"},
                    "minimum_followup_probe_queries": {"type": "array"},
                    "risk_notes": {"type": "array"},
                },
            },
            "audit": {
                "type": "object",
                "properties": {
                    "unsupported_or_weak_claims": {"type": "array"},
                    "abstentions": {"type": "array"},
                    "possible_model_errors": {"type": "array"},
                    "source_refs_used": {"type": "array"},
                    "source_refs_most_important": {"type": "array"},
                },
            },
        },
    }


def build_prompt(expert: Expert, manifest: dict[str, Any]) -> str:
    schema_json = json.dumps(build_schema(), ensure_ascii=False, indent=2)
    return f"""# Task

Create a source-grounded semantic value passport for one Telegram expert channel
in the Experts Panel system.

The system goal: Experts Panel is a source-backed practitioner panel for
AI-assisted development. The passport must help compare this expert against an
existing knowledge matrix and decide whether a future expert adds new value,
duplicates existing value, or adds noise.

Expert:
- expert_id: {expert.expert_id}
- display_name: {expert.display_name}
- channel_username: @{expert.channel_username}

Model assumed by operator: {manifest["model"]}
Prompt version: {PROMPT_VERSION}
Schema version: {SCHEMA_VERSION}
Packet created_at: {manifest["created_at"]}

# Non-negotiable rules

1. Return strict JSON only. Do not wrap it in Markdown.
2. Use the JSON schema below as the output contract.
3. Every important claim must include source references from the corpus, such as
   `P0007` or `P0007.C0003`.
4. Treat `EXPERT_POST_TEXT` as the expert channel voice.
5. Treat `COMMENT_TEXT` as community signal only. Do not attribute comments to
   the expert unless the corpus metadata clearly supports it.
6. Prefer `insufficient_evidence`, `unknown`, or an audit abstention over
   inventing a confident claim.
7. Do not summarize by keyword frequency. Infer semantic value: what knowledge,
   judgment, practical patterns, evidence quality, and reusable decision value
   the channel contributes.
8. Distinguish broad AI news from useful practitioner evidence.
9. Do not make a final roster decision against existing experts because you only
   see this one expert's corpus in this run. Use `needs_matrix_compare` when
   matrix comparison is required.
10. Keep quotes short. Prefer source refs and paraphrase over long excerpts.
11. Do not score matrix-relative novelty inside this single-expert run. Use
   `intrinsic_distinctiveness_score_0_5` and set `matrix_relative_novelty` to
   `not_scored_without_matrix`.
12. Populate `matrix_export` as the machine-comparable payload that can be
   merged into the Experts Panel knowledge matrix without reading narrative
   sections.
13. Set `passport_meta.generated_at` exactly to the packet `created_at` value
   shown above.
14. `source_ref_index_used` must include every source ref cited anywhere in the
   passport output, not only the most important refs.

# Scoring rubric

Scores are 0-5:
- 0: absent or unsupported
- 1: rare/thin/mostly noisy
- 2: present but shallow or mostly commentary
- 3: useful moderate coverage
- 4: strong recurring practical value
- 5: signature-level value with reusable insight and strong evidence

Recommended core dimensions for `value_dimensions`:
- insight_density
- practical_specificity
- evidence_quality
- decision_value
- source_utility_for_panex
- originality_or_distinctive_angle
- anti_hype_signal
- technical_depth
- product_pm_depth
- business_adoption_depth
- governance_security_depth
- community_resonance

Recommended domain IDs for `knowledge_domains` and `matrix_cells`:
- coding_agents
- agent_ops
- evals_quality
- rag_retrieval_knowledge
- prompt_engineering
- ai_product_pm
- business_adoption
- ai_ux_workflow
- security_privacy_governance
- ai_engineering_infra
- model_landscape
- creative_multimodal
- general_ai_news
- other_distinctive_domain

Recommended subdomain IDs. Use these where they fit; create a concise
`other_*` subdomain only when the corpus clearly needs it:
- ai_coding_ides
- claude_code_workflows
- codex_workflows
- cursor_windsurf_copilot
- agentic_dev_process
- code_review_testing
- mcp_tooling
- local_agent_setup
- multi_agent_orchestration
- tool_calling_hooks_skills
- llm_evals
- regression_harness
- benchmark_interpretation
- quality_gates
- rag_architecture
- hybrid_retrieval
- embeddings_vector_search
- knowledge_base_design
- model_specific_formatting
- context_compression
- reasoning_control
- ai_product_strategy
- pm_workflow
- adoption_roadmaps
- roi_business_cases
- financial_modeling
- human_ai_workflow
- ai_ux_patterns
- security_privacy_controls
- governance_risk
- inference_cost_latency
- deployment_observability
- model_comparison
- model_release_analysis
- multimodal_generation
- broad_ai_news

Recommended query intent IDs:
- choose_ai_coding_tool
- design_agentic_dev_workflow
- debug_agent_failure
- build_ai_dev_eval
- design_rag_knowledge_base
- improve_retrieval_quality
- plan_ai_product_feature
- assess_ai_tool_business_adoption
- manage_security_privacy_governance
- compare_models_for_task
- optimize_inference_cost_latency
- build_human_ai_workflow
- learn_ai_assisted_development

# Matrix export guidance

The `matrix_export.cells` array is the most important part for future expert
admission. Each cell should be atomic enough to compare against the existing
knowledge matrix. Prefer several precise cells over one broad cell.

For each matrix cell:
- use a stable `cell_id` like
  `<domain_id>/<subdomain_id>/<primary_query_intent_id>`;
- include only source refs that support that exact cell;
- mark `matrix_update_role` as `needs_matrix_compare` when uniqueness cannot be
  decided without the current matrix;
- mark likely duplicate or likely unique only as a hypothesis, not proof.

The `query_intent_fit` section should answer: "For which real Panex / Agent
Context questions would this expert be selected as a primary or supporting
source?"

# Output schema

{schema_json}

# Corpus audit from packet builder

{json.dumps(manifest["corpus_stats"], ensure_ascii=False, indent=2)}

# Now analyze the corpus that follows this prompt.
"""


def build_corpus_markdown(
    expert: Expert,
    posts: list[Post],
    comments_by_post_id: dict[int, list[Comment]],
) -> str:
    lines: list[str] = [
        "# Expert Semantic Passport Corpus",
        "",
        f"expert_id: {expert.expert_id}",
        f"display_name: {expert.display_name}",
        f"channel_username: @{expert.channel_username}",
        "",
        "Corpus rules:",
        "- Source refs starting with P are expert channel posts.",
        "- Source refs with .C are comments under that post.",
        "- Comments are community signal, not expert voice, unless metadata proves otherwise.",
        "",
    ]

    for post in posts:
        comments = comments_by_post_id.get(post.post_id, [])
        lines.extend(
            [
                f"## SOURCE {post.source_ref}",
                "",
                "metadata:",
                f"- post_id: {post.post_id}",
                f"- telegram_message_id: {post.telegram_message_id}",
                f"- created_at: {post.created_at or ''}",
                f"- view_count: {post.view_count if post.view_count is not None else ''}",
                f"- forward_count: {post.forward_count if post.forward_count is not None else ''}",
                f"- reply_count: {post.reply_count if post.reply_count is not None else ''}",
                f"- comment_count_in_packet: {len(comments)}",
                "",
                "### EXPERT_POST_TEXT",
                post.text,
                "",
            ]
        )

        if comments:
            lines.append("### COMMENTS")
            for comment in comments:
                lines.extend(
                    [
                        f"#### COMMENT {comment.source_ref}",
                        "metadata:",
                        f"- comment_id: {comment.comment_id}",
                        f"- telegram_comment_id: {comment.telegram_comment_id if comment.telegram_comment_id is not None else ''}",
                        f"- author_name: {comment.author_name}",
                        f"- created_at: {comment.created_at or ''}",
                        "",
                        "COMMENT_TEXT:",
                        comment.text,
                        "",
                    ]
                )
        else:
            lines.extend(["### COMMENTS", "No comments in packet.", ""])

    return "\n".join(lines).rstrip() + "\n"


def corpus_stats(
    expert: Expert,
    posts: list[Post],
    comments_by_post_id: dict[int, list[Comment]],
    max_comments_per_post: int | None,
) -> dict[str, Any]:
    comments = [comment for post_comments in comments_by_post_id.values() for comment in post_comments]
    post_chars = sum(len(post.text) for post in posts)
    comment_chars = sum(len(comment.text) for comment in comments)
    all_dates = [post.created_at for post in posts if post.created_at]
    return {
        "expert_id": expert.expert_id,
        "display_name": expert.display_name,
        "channel_username": expert.channel_username,
        "post_count": len(posts),
        "comment_count": len(comments),
        "post_chars": post_chars,
        "comment_chars": comment_chars,
        "total_chars": post_chars + comment_chars,
        "estimated_input_tokens_from_corpus_chars": estimate_tokens_from_chars(post_chars + comment_chars),
        "date_range": {
            "first_post": min(all_dates) if all_dates else None,
            "last_post": max(all_dates) if all_dates else None,
        },
        "max_comments_per_post": max_comments_per_post,
    }


def build_source_ref_index(
    posts: list[Post],
    comments_by_post_id: dict[int, list[Comment]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for post in posts:
        entries.append(
            {
                "source_ref": post.source_ref,
                "source_kind": "expert_post",
                "post_id": post.post_id,
                "telegram_message_id": post.telegram_message_id,
                "comment_id": None,
                "telegram_comment_id": None,
                "created_at": post.created_at,
                "char_count": len(post.text),
            }
        )
        for comment in comments_by_post_id.get(post.post_id, []):
            entries.append(
                {
                    "source_ref": comment.source_ref,
                    "source_kind": "community_comment",
                    "post_id": comment.post_id,
                    "telegram_message_id": post.telegram_message_id,
                    "comment_id": comment.comment_id,
                    "telegram_comment_id": comment.telegram_comment_id,
                    "created_at": comment.created_at,
                    "char_count": len(comment.text),
                }
            )
    return entries


def write_packet(
    expert: Expert,
    posts: list[Post],
    comments_by_post_id: dict[int, list[Comment]],
    output_dir: Path,
    model: str,
    max_comments_per_post: int | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = corpus_stats(expert, posts, comments_by_post_id, max_comments_per_post)
    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": "backend/scripts/export_semantic_passport_packet.py",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "corpus_stats": stats,
        "files": {
            "prompt": "semantic_passport_prompt.md",
            "schema": "expert_value_passport_schema_v1_1.json",
            "source_ref_index": f"{expert.expert_id}_source_ref_index.json",
            "corpus": f"{expert.expert_id}_corpus.md",
            "combined_prompt": f"{expert.expert_id}_vertex_prompt.md",
            "expected_output": f"{expert.expert_id}_semantic_passport.json",
        },
        "operator_notes": [
            "This packet is read-only export evidence, not a Vertex run receipt.",
            "Use response MIME type application/json.",
            "Suggested maxOutputTokens: 65536 for the first full passport run.",
            "Do not treat the resulting passport as a final admission verdict until matrix comparison is done.",
        ],
    }

    schema = build_schema()
    source_ref_index = build_source_ref_index(posts, comments_by_post_id)
    prompt = build_prompt(expert, manifest)
    corpus_md = build_corpus_markdown(expert, posts, comments_by_post_id)
    combined = (
        prompt
        + "\n\n"
        + "# Corpus\n\n"
        + corpus_md
        + "\n\n"
        + "# End of corpus\n"
        + "Return the strict JSON passport now.\n"
    )
    manifest["artifact_stats"] = {
        "prompt_chars": len(prompt),
        "schema_chars": len(json.dumps(schema, ensure_ascii=False, indent=2)),
        "source_ref_count": len(source_ref_index),
        "corpus_markdown_chars": len(corpus_md),
        "combined_prompt_chars": len(combined),
        "combined_prompt_utf8_bytes": len(combined.encode("utf-8")),
        "estimated_input_tokens_from_combined_prompt_chars": estimate_tokens_from_chars(len(combined)),
        "estimated_input_tokens_from_combined_prompt_utf8_bytes": estimate_tokens_from_chars(
            len(combined.encode("utf-8"))
        ),
    }

    (output_dir / manifest["files"]["schema"]).write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / manifest["files"]["source_ref_index"]).write_text(
        json.dumps(source_ref_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / manifest["files"]["prompt"]).write_text(prompt, encoding="utf-8")
    (output_dir / manifest["files"]["corpus"]).write_text(corpus_md, encoding="utf-8")
    (output_dir / manifest["files"]["combined_prompt"]).write_text(combined, encoding="utf-8")
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a full-context semantic passport packet for one expert."
    )
    parser.add_argument("--expert-id", required=True, help="Expert ID from expert_metadata.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite DB path.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to output/expert_admission/semantic_passports/<expert-id>/input.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Target model ID for manifest notes.")
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="Optional smoke-test cap. Omit for full expert corpus.",
    )
    parser.add_argument(
        "--max-comments-per-post",
        type=int,
        default=None,
        help="Optional per-post comment cap. Omit for all comments.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir or (DEFAULT_OUTPUT_ROOT / args.expert_id / "input")
    with connect(args.db) as conn:
        expert = fetch_expert(conn, args.expert_id)
        posts = fetch_posts(conn, args.expert_id, args.max_posts)
        post_refs_by_id = {post.post_id: post.source_ref for post in posts}
        comments = fetch_comments(
            conn,
            args.expert_id,
            post_refs_by_id,
            args.max_comments_per_post,
        )

    manifest = write_packet(
        expert=expert,
        posts=posts,
        comments_by_post_id=comments,
        output_dir=out_dir,
        model=args.model,
        max_comments_per_post=args.max_comments_per_post,
    )
    stats = manifest["corpus_stats"]
    print(f"Wrote semantic passport packet: {out_dir}")
    print(
        "Corpus: "
        f"{stats['post_count']} posts, "
        f"{stats['comment_count']} comments, "
        f"{stats['total_chars']} chars, "
        f"~{stats['estimated_input_tokens_from_corpus_chars']['chars_div_4']} tokens chars/4"
    )
    artifact_stats = manifest["artifact_stats"]
    print(
        "Combined prompt estimate: "
        f"{artifact_stats['combined_prompt_chars']} chars, "
        f"{artifact_stats['combined_prompt_utf8_bytes']} utf8 bytes, "
        f"~{artifact_stats['estimated_input_tokens_from_combined_prompt_chars']['chars_div_4']} tokens chars/4, "
        f"~{artifact_stats['estimated_input_tokens_from_combined_prompt_utf8_bytes']['chars_div_3']} tokens bytes/3"
    )
    print(f"Combined prompt: {out_dir / manifest['files']['combined_prompt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
