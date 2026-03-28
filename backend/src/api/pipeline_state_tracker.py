"""Pipeline State Tracker for SSE progress events.

Tracks aggregate pipeline state across all experts and sidecars.
Per-expert state is tracked internally. The public get_state() method
returns the aggregate (single dict) for SSE events.

Thread safety: Not needed — runs in single asyncio event loop.
"""

from typing import Dict, List, Optional


# Status normalization map: service status values → tracker statuses
STATUS_MAP = {
    "starting": "active",
    "processing": "active",
    "synthesizing": "active",
    "scoring": "active",
    "retrying": "active",
    "completed": "completed",
    "complete": "completed",
    "fallback": "completed",  # Scout sends "fallback" on partial failure
    "skipped": "skipped",
    "error": "error",
}

# Video Hub sends generic phase names; remap to distinct video_* names
VIDEO_PHASE_MAP = {
    "map": "video_map",
    "resolve": "video_resolve",
    "reduce": "video_synthesis",
    "language_validation": "video_validation",
}


def _normalize_status(raw_status: str) -> str:
    """Convert service status values to tracker statuses."""
    return STATUS_MAP.get(raw_status, "active")


class PipelineStateTracker:
    """Tracks aggregate pipeline state across all experts and sidecars.

    Usage:
        tracker = PipelineStateTracker(
            expert_ids=["expert_a", "expert_b", "video_hub"],
            include_reddit=True,
            include_comment_groups=True,
            use_super_passport=True,
        )
        tracker.update("expert_a", "map", "active")
        tracker.update(None, "scout", "completed")
        state = tracker.get_state()
        # => {"scout": "completed", "map": "active", "medium_scoring": "pending", ...}
    """

    def __init__(
        self,
        expert_ids: List[str],
        include_reddit: bool = False,
        include_comment_groups: bool = False,
        use_super_passport: bool = False,
    ):
        regular_experts = [e for e in expert_ids if e != "video_hub"]
        has_video_hub = "video_hub" in expert_ids
        has_regular = len(regular_experts) > 0
        total_experts = len(expert_ids)

        # Per-expert state: {expert_id: {phase: status}}
        self._per_expert: Dict[str, Dict[str, str]] = {}

        # Cross-cutting phases (not per-expert)
        self._cross_cutting: Dict[str, str] = {}

        # Initialize per-expert phases for regular experts
        for eid in regular_experts:
            phases: Dict[str, str] = {
                "map": "pending",
                "medium_scoring": "pending",
                "resolve": "pending",
                "reduce": "pending",
                "language_validation": "pending",
            }
            if include_comment_groups:
                phases["comment_groups"] = "pending"
                phases["comment_synthesis"] = "pending"
            self._per_expert[eid] = phases

        # Initialize per-expert phases for video_hub (distinct names)
        if has_video_hub:
            self._per_expert["video_hub"] = {
                "video_map": "pending",
                "video_resolve": "pending",
                "video_synthesis": "pending",
                "video_validation": "pending",
            }

        # Cross-cutting: scout (only useful for regular experts)
        if use_super_passport and has_regular:
            self._cross_cutting["scout"] = "pending"

        # Cross-cutting: meta_synthesis (requires ≥2 experts)
        if total_experts >= 2:
            self._cross_cutting["meta_synthesis"] = "pending"

        # Cross-cutting: reddit
        if include_reddit:
            self._cross_cutting["reddit_search"] = "pending"
            self._cross_cutting["reddit_synthesis"] = "pending"

    # State priority: higher number = more "final". Only forward transitions allowed.
    # pending(0) → active(1) → error/skipped(2) → completed(3)
    _PRIORITY = {"pending": 0, "active": 1, "error": 2, "skipped": 2, "completed": 3}

    def update(self, expert_id: Optional[str], phase: str, status: str) -> None:
        """Update state for a specific phase.

        Args:
            expert_id: Expert ID, or None for cross-cutting phases.
            phase: Phase name (must match initialized phases).
            status: Raw status from service — will be normalized.

        Monotonic progression: states can only move forward in priority.
        pending(0) → active(1) → error/skipped(2) → completed(3).
        This prevents late callbacks or finally-blocks from rolling back state.
        """
        normalized = _normalize_status(status)

        if expert_id and expert_id in self._per_expert:
            if phase in self._per_expert[expert_id]:
                current = self._per_expert[expert_id][phase]
                if self._PRIORITY.get(normalized, 0) < self._PRIORITY.get(current, 0):
                    return  # Only forward transitions
                self._per_expert[expert_id][phase] = normalized
        elif phase in self._cross_cutting:
            current = self._cross_cutting[phase]
            if self._PRIORITY.get(normalized, 0) < self._PRIORITY.get(current, 0):
                return  # Only forward transitions
            self._cross_cutting[phase] = normalized

    def mark_expert_error(self, expert_id: str) -> None:
        """Mark all pending/active phases of an expert as error.

        Called when an expert's pipeline fails entirely.
        Does NOT overwrite "completed" or "skipped" phases.
        """
        if expert_id not in self._per_expert:
            return
        for phase, current in self._per_expert[expert_id].items():
            if current in ("pending", "active"):
                self._per_expert[expert_id][phase] = "error"

    def skip_phase(self, expert_id: Optional[str], phase: str) -> None:
        """Convenience method to mark a phase as skipped."""
        self.update(expert_id, phase, "skipped")

    def mark_expert_skipped(self, expert_id: str) -> None:
        """Mark all pending phases of an expert as skipped.

        Called when an expert has no data to process (e.g., 0 posts found).
        Does NOT overwrite phases that already progressed beyond pending.
        """
        if expert_id not in self._per_expert:
            return
        for phase, current in self._per_expert[expert_id].items():
            if current == "pending":
                self._per_expert[expert_id][phase] = "skipped"

    def get_state(self) -> Dict[str, str]:
        """Compute and return aggregate pipeline state.

        Aggregation rules for per-expert phases:
        - "active" if ANY expert has that phase as "active"
        - "completed" if ALL experts have that phase as "completed" or "skipped"
        - "error" if ANY expert has "error" and none has "active"
        - "pending" otherwise

        Cross-cutting phases are returned as-is.
        """
        aggregate: Dict[str, str] = {}

        # Collect all unique phase names across all experts
        all_phases: set = set()
        for expert_phases in self._per_expert.values():
            all_phases.update(expert_phases.keys())

        for phase in all_phases:
            statuses = []
            for expert_phases in self._per_expert.values():
                if phase in expert_phases:
                    statuses.append(expert_phases[phase])

            if not statuses:
                continue

            if any(s == "active" for s in statuses):
                aggregate[phase] = "active"
            elif all(s in ("completed", "skipped") for s in statuses):
                # All done: "skipped" if ALL skipped, "completed" if any completed
                if all(s == "skipped" for s in statuses):
                    aggregate[phase] = "skipped"
                else:
                    aggregate[phase] = "completed"
            elif any(s == "error" for s in statuses):
                aggregate[phase] = "error"
            else:
                aggregate[phase] = "pending"

        # Add cross-cutting phases
        aggregate.update(self._cross_cutting)

        return aggregate

    def remap_video_phase(self, phase: str) -> str:
        """Remap generic video_hub phase name to distinct video_* name."""
        return VIDEO_PHASE_MAP.get(phase, phase)
