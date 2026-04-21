"""
E2E Benchmark: Hybrid (Embs&Keys) vs Standard retrieval.

Connects to the running backend as an SSE client, sends identical queries
with use_super_passport=true and false, records per-phase timestamps
from SSE events, and prints a comparative timing table.

Works against both local (http://localhost:8000) and production (https://experts-panel.fly.dev).

Usage:
    # Against local backend (start it first with: cd backend && python -m src.api.main)
    python backend/scripts/benchmark_hybrid_e2e.py

    # Against production
    python backend/scripts/benchmark_hybrid_e2e.py --url https://experts-panel.fly.dev

    # Custom query and experts
    python backend/scripts/benchmark_hybrid_e2e.py --query "Как настроить RAG?" --experts doronin silicbag akimov
"""

import argparse
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.benchmark_hybrid_e2e",
)

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Install: pip install httpx")
    sys.exit(1)


@dataclass
class PhaseEvent:
    timestamp: float
    event_type: str
    phase: str
    status: str
    message: str
    expert_id: Optional[str] = None
    data: dict = field(default_factory=dict)


@dataclass
class RunResult:
    mode: str  # "hybrid" or "standard"
    query: str
    experts: list
    wall_time_ms: float
    events: list  # List[PhaseEvent]
    expert_timings: dict = field(default_factory=dict)  # expert_id -> {phase: ms}
    error: Optional[str] = None


def parse_sse_stream(response) -> list:
    """Parse SSE stream from httpx response, return list of PhaseEvents."""
    events = []
    buffer = ""

    for line in response.iter_lines():
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                events.append(PhaseEvent(
                    timestamp=time.perf_counter(),
                    event_type=payload.get("event_type", ""),
                    phase=payload.get("phase", ""),
                    status=payload.get("status", ""),
                    message=payload.get("message", ""),
                    expert_id=payload.get("data", {}).get("expert_id"),
                    data=payload.get("data", {}),
                ))
            except json.JSONDecodeError:
                pass  # keep-alive or malformed
        elif line.startswith(":"):
            # Comment/keep-alive, ignore
            pass

    return events


def run_query(base_url: str, query: str, experts: list, use_super_passport: bool,
              include_reddit: bool = False, timeout: float = 180.0) -> RunResult:
    """Send a query and collect SSE events with timing."""
    mode = "hybrid" if use_super_passport else "standard"

    payload = {
        "query": query,
        "expert_filter": experts,
        "stream_progress": True,
        "include_comments": True,
        "include_comment_groups": True,
        "use_recent_only": False,
        "include_reddit": include_reddit,
        "use_super_passport": use_super_passport,
    }

    url = f"{base_url.rstrip('/')}/api/v1/query"

    print(f"\n{'='*60}")
    print(f"  Mode: {mode.upper()} | Experts: {', '.join(experts)}")
    print(f"  Query: {query[:80]}")
    print(f"  URL: {url}")
    print(f"{'='*60}")

    t_start = time.perf_counter()

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
            with client.stream("POST", url, json=payload,
                               headers={"Accept": "text/event-stream"}) as response:
                if response.status_code != 200:
                    return RunResult(
                        mode=mode, query=query, experts=experts,
                        wall_time_ms=0, events=[],
                        error=f"HTTP {response.status_code}"
                    )

                events = parse_sse_stream(response)
                wall_time = (time.perf_counter() - t_start) * 1000

    except Exception as e:
        return RunResult(
            mode=mode, query=query, experts=experts,
            wall_time_ms=(time.perf_counter() - t_start) * 1000,
            events=[], error=str(e)
        )

    # Compute per-expert phase timings from SSE events
    expert_timings = compute_expert_timings(events, t_start)

    result = RunResult(
        mode=mode, query=query, experts=experts,
        wall_time_ms=round(wall_time, 1),
        events=events,
        expert_timings=expert_timings,
    )

    print_run_summary(result)
    return result


def compute_expert_timings(events: list, t_start: float) -> dict:
    """Compute per-expert and global phase timings from SSE events."""
    # Track first/last event per expert
    expert_first = {}  # expert_id -> timestamp
    expert_last = {}   # expert_id -> timestamp
    expert_phases = {}  # expert_id -> [(phase, timestamp)]

    # Global phases
    global_phases = []

    for e in events:
        eid = e.expert_id
        if eid:
            if eid not in expert_first:
                expert_first[eid] = e.timestamp
            expert_last[eid] = e.timestamp

            if eid not in expert_phases:
                expert_phases[eid] = []
            expert_phases[eid].append((e.phase, e.status, e.timestamp, e.message))

        global_phases.append((e.event_type, e.phase, e.status, e.timestamp, e.message))

    timings = {}

    for eid in expert_first:
        total = (expert_last[eid] - expert_first[eid]) * 1000
        timings[eid] = {"total_ms": round(total, 1)}

        # Extract phase transitions
        phases = expert_phases.get(eid, [])
        for i, (phase, status, ts, msg) in enumerate(phases):
            if phase not in timings[eid]:
                timings[eid][phase] = {"start": ts}
            timings[eid][phase]["end"] = ts

        # Convert to durations
        for phase_name, phase_data in list(timings[eid].items()):
            if isinstance(phase_data, dict) and "start" in phase_data and "end" in phase_data:
                timings[eid][phase_name] = round(
                    (phase_data["end"] - phase_data["start"]) * 1000, 1
                )

    # Add global scout phase timing (appears before expert processing)
    scout_start = None
    scout_end = None
    for et, phase, status, ts, msg in global_phases:
        if phase == "scout":
            if scout_start is None:
                scout_start = ts
            scout_end = ts

    if scout_start and scout_end:
        timings["__scout__"] = round((scout_end - scout_start) * 1000, 1)

    return timings


def print_run_summary(result: RunResult):
    """Print a human-readable summary of one run."""
    if result.error:
        print(f"\n  ERROR: {result.error}")
        return

    print(f"\n  Wall time: {result.wall_time_ms:.0f}ms")
    print(f"  SSE events: {len(result.events)}")

    # Global phases
    if "__scout__" in result.expert_timings:
        print(f"  AI Scout: {result.expert_timings['__scout__']:.0f}ms")

    # Per-expert
    for eid in result.experts:
        if eid in result.expert_timings:
            t = result.expert_timings[eid]
            total = t.get("total_ms", "?")
            phases_str = " | ".join(
                f"{k}={v}ms" for k, v in t.items()
                if k != "total_ms" and isinstance(v, (int, float))
            )
            print(f"  [{eid}] total={total}ms | {phases_str}")
        else:
            print(f"  [{eid}] no timing data")

    # Event log (condensed)
    print(f"\n  Event log:")
    base_ts = result.events[0].timestamp if result.events else 0
    for e in result.events:
        rel = (e.timestamp - base_ts) * 1000
        eid_tag = f"[{e.expert_id}]" if e.expert_id else ""
        # Truncate long messages
        msg = e.message[:80] if e.message else ""
        print(f"    +{rel:7.0f}ms  {e.event_type:20s} {e.phase:15s} {eid_tag} {msg}")


def print_comparison(hybrid_result: RunResult, standard_result: RunResult):
    """Print side-by-side comparison."""
    print("\n")
    print("=" * 70)
    print("  COMPARISON: HYBRID vs STANDARD")
    print("=" * 70)

    h_wall = hybrid_result.wall_time_ms
    s_wall = standard_result.wall_time_ms
    diff = s_wall - h_wall
    pct = (diff / s_wall * 100) if s_wall > 0 else 0

    print(f"\n  {'Metric':<30s} {'Hybrid':>12s} {'Standard':>12s} {'Diff':>12s}")
    print(f"  {'-'*66}")
    print(f"  {'Wall time':<30s} {h_wall:>10.0f}ms {s_wall:>10.0f}ms {diff:>+10.0f}ms ({pct:+.1f}%)")
    print(f"  {'SSE events':<30s} {len(hybrid_result.events):>12d} {len(standard_result.events):>12d}")

    # Per-expert comparison
    all_experts = set(hybrid_result.experts) | set(standard_result.experts)
    for eid in sorted(all_experts):
        h_t = hybrid_result.expert_timings.get(eid, {}).get("total_ms", "N/A")
        s_t = standard_result.expert_timings.get(eid, {}).get("total_ms", "N/A")
        if isinstance(h_t, (int, float)) and isinstance(s_t, (int, float)):
            d = s_t - h_t
            print(f"  {eid:<30s} {h_t:>10.0f}ms {s_t:>10.0f}ms {d:>+10.0f}ms")
        else:
            print(f"  {eid:<30s} {str(h_t):>12s} {str(s_t):>12s}")

    # Scout overhead
    scout_ms = hybrid_result.expert_timings.get("__scout__", 0)
    if scout_ms:
        print(f"  {'AI Scout overhead':<30s} {scout_ms:>10.0f}ms {'---':>12s}")

    if diff > 0:
        print(f"\n  >>> HYBRID is {diff:.0f}ms FASTER ({pct:.1f}%)")
    elif diff < 0:
        print(f"\n  >>> STANDARD is {-diff:.0f}ms FASTER ({-pct:.1f}%)")
    else:
        print(f"\n  >>> No difference")

    print()


def main():
    parser = argparse.ArgumentParser(description="E2E Benchmark: Hybrid vs Standard retrieval")
    parser.add_argument("--url", default="http://localhost:8000",
                        help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--query", default="Какими инструментами сейчас удобно делать дашборды в своих системах?",
                        help="Test query")
    parser.add_argument("--experts", nargs="+", default=["doronin", "silicbag"],
                        help="Expert IDs to test (default: doronin silicbag)")
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="Request timeout in seconds (default: 180)")
    parser.add_argument("--only", choices=["hybrid", "standard"],
                        help="Run only one mode (skip comparison)")
    parser.add_argument("--reddit", action="store_true",
                        help="Include Reddit pipeline (disabled by default for cleaner timing)")
    args = parser.parse_args()

    print(f"\nE2E Hybrid Retrieval Benchmark")
    print(f"Backend: {args.url}")
    print(f"Experts: {', '.join(args.experts)}")
    print(f"Query: {args.query[:80]}")
    print(f"Reddit: {'ON' if args.reddit else 'OFF'}")

    # Check backend is reachable
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{args.url.rstrip('/')}/health")
            if r.status_code != 200:
                print(f"\nERROR: Backend returned {r.status_code} on /health")
                sys.exit(1)
            print(f"Backend health: OK")
    except Exception as e:
        print(f"\nERROR: Cannot reach backend at {args.url}: {e}")
        sys.exit(1)

    results = {}

    if args.only != "standard":
        # Run HYBRID first
        print("\n\n>>> RUNNING HYBRID MODE (use_super_passport=True)")
        results["hybrid"] = run_query(
            args.url, args.query, args.experts,
            use_super_passport=True,
            include_reddit=args.reddit,
            timeout=args.timeout,
        )

        # Small pause between runs to avoid rate limits
        if not args.only:
            print("\n... Waiting 3 seconds between runs to avoid rate limits ...")
            time.sleep(3)

    if args.only != "hybrid":
        # Run STANDARD
        print("\n\n>>> RUNNING STANDARD MODE (use_super_passport=False)")
        results["standard"] = run_query(
            args.url, args.query, args.experts,
            use_super_passport=False,
            include_reddit=args.reddit,
            timeout=args.timeout,
        )

    # Print comparison if both modes ran
    if "hybrid" in results and "standard" in results:
        print_comparison(results["hybrid"], results["standard"])

    # Save raw results to JSON
    output_file = "backend/scripts/benchmark_results.json"
    raw = {}
    for mode, r in results.items():
        raw[mode] = {
            "wall_time_ms": r.wall_time_ms,
            "expert_timings": r.expert_timings,
            "event_count": len(r.events),
            "error": r.error,
            "events": [
                {
                    "rel_ms": round((e.timestamp - r.events[0].timestamp) * 1000, 1) if r.events else 0,
                    "event_type": e.event_type,
                    "phase": e.phase,
                    "status": e.status,
                    "expert_id": e.expert_id,
                    "message": e.message[:120],
                }
                for e in r.events
            ],
        }

    with open(output_file, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    print(f"Raw results saved to: {output_file}")


if __name__ == "__main__":
    main()
