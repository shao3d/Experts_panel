#!/usr/bin/env python3
"""
A/B Testing Script for Super-Passport Search (FTS5 + AI Scout)

Compares old pipeline (MapReduce) vs new pipeline (FTS5 + AI Scout):
- Recall: % matching main_sources between both methods
- Latency: Execution time comparison
- Answer similarity: Structural comparison of responses

Usage:
    cd backend && python scripts/ab_test_super_passport.py

Requirements:
    - Backend running on localhost:8000 (or set BACKEND_URL env var)
    - Or use --start-backend flag to auto-start
"""

import asyncio
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import argparse

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp")
    sys.exit(1)

# ANSI colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


# Test queries for comparison
DEFAULT_TEST_QUERIES = [
    {
        "id": "cpp_special_chars",
        "query": "как работать с C++",
        "description": "Special characters test (C++)",
        "expected_keywords": ["cpp", "cplusplus", "си плюс плюс"]
    },
    {
        "id": "kubernetes_bilingual",
        "query": "настройка кубера в продакшен",
        "description": "Bilingual slang (кубер = kubernetes)",
        "expected_keywords": ["kubernetes", "k8s", "кубер"]
    },
    {
        "id": "deploy_pipeline",
        "query": "как сделать раскатку через пайплайн",
        "description": "Russian slang (раскатка = deploy, пайплайн = pipeline)",
        "expected_keywords": ["deploy", "pipeline", "ci", "cd"]
    },
    {
        "id": "csharp_dotnet",
        "query": "C# и .NET разработка",
        "description": "Multiple special chars (C# + .NET)",
        "expected_keywords": ["csharp", "dotnet", "си шарп"]
    },
    {
        "id": "general_query",
        "query": "как использовать Docker контейнеры",
        "description": "General query without special chars",
        "expected_keywords": ["docker", "контейнер"]
    }
]


class ABTestRunner:
    """Runs A/B tests comparing old vs new pipeline."""

    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.results: List[Dict[str, Any]] = []
        self.session: Optional[aiohttp.ClientSession] = None

    async def setup(self):
        """Setup HTTP session."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )

    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()

    async def run_query(
        self,
        query: str,
        use_super_passport: bool,
        expert_filter: List[str] = None
    ) -> Dict[str, Any]:
        """Run a single query against the API.

        Args:
            query: User query
            use_super_passport: Enable FTS5 + AI Scout
            expert_filter: Optional list of expert IDs

        Returns:
            Response dict with data, latency, success status
        """
        url = f"{self.base_url}/api/v1/query"

        payload = {
            "query": query,
            "use_super_passport": use_super_passport,
            "stream_progress": True,   # API always returns SSE
            "include_reddit": False    # Focus on expert responses
        }

        if expert_filter:
            payload["expert_filter"] = expert_filter

        start_time = time.time()

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    latency_ms = (time.time() - start_time) * 1000
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {text[:200]}",
                        "latency_ms": latency_ms,
                        "status_code": response.status
                    }

                # Parse SSE stream to extract expert responses
                expert_responses = []

                async for line in response.content:
                    line = line.decode('utf-8').strip()

                    # Skip empty lines
                    if not line:
                        continue

                    # Handle SSE format: "data: data: {...}" (double data: prefix)
                    if line.startswith("data:"):
                        json_str = line[5:].strip()
                        # Handle double "data:" prefix
                        if json_str.startswith("data:"):
                            json_str = json_str[5:].strip()
                        if not json_str:
                            continue

                        try:
                            event = json.loads(json_str)

                            # Look for expert_complete events to collect sources
                            if event.get("event_type") == "expert_complete":
                                expert_data = event.get("data", {})
                                expert_responses.append({
                                    "expert_id": expert_data.get("expert_id"),
                                    "main_sources": expert_data.get("main_sources", []),
                                    "posts_analyzed": expert_data.get("posts_analyzed", 0)
                                })

                        except json.JSONDecodeError:
                            continue

                latency_ms = (time.time() - start_time) * 1000

                # Build response from collected data
                if expert_responses:
                    return {
                        "success": True,
                        "data": {
                            "expert_responses": expert_responses,
                            "query": query
                        },
                        "latency_ms": latency_ms,
                        "status_code": 200
                    }
                else:
                    return {
                        "success": False,
                        "error": "No expert responses from SSE stream",
                        "latency_ms": latency_ms,
                        "status_code": 200
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {self.timeout}s",
                "latency_ms": self.timeout * 1000,
                "status_code": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
                "status_code": 0
            }

    def calculate_recall(
        self,
        old_sources: List[int],
        new_sources: List[int]
    ) -> Tuple[float, int, int, int]:
        """Calculate recall between old and new sources.

        Returns:
            (recall, intersection_count, old_only_count, new_only_count)
        """
        old_set = set(old_sources)
        new_set = set(new_sources)

        intersection = old_set & new_set
        old_only = old_set - new_set
        new_only = new_set - old_set

        recall = len(intersection) / len(old_set) if old_set else 0.0

        return recall, len(intersection), len(old_only), len(new_only)

    def extract_sources(self, response: Dict) -> Dict[str, List[int]]:
        """Extract main_sources from all expert responses.

        Returns:
            Dict mapping expert_id to list of main_sources
        """
        sources = {}
        expert_responses = response.get("expert_responses", [])

        for expert in expert_responses:
            expert_id = expert.get("expert_id", "unknown")
            main_sources = expert.get("main_sources", [])
            sources[expert_id] = main_sources

        return sources

    async def run_ab_test(
        self,
        test_case: Dict[str, Any],
        expert_filter: List[str] = None
    ) -> Dict[str, Any]:
        """Run A/B test for a single test case.

        Args:
            test_case: Test case dict with id, query, description
            expert_filter: Optional list of expert IDs to filter

        Returns:
            Comparison results dict
        """
        query = test_case["query"]
        test_id = test_case["id"]

        print(f"\n{CYAN}▶ Test: {test_id}{RESET}")
        print(f"  Query: {query}")

        # Run OLD pipeline (use_super_passport=False)
        print(f"  {YELLOW}Running OLD pipeline...{RESET}")
        old_result = await self.run_query(
            query=query,
            use_super_passport=False,
            expert_filter=expert_filter
        )

        # Run NEW pipeline (use_super_passport=True)
        print(f"  {YELLOW}Running NEW pipeline (FTS5 + Scout)...{RESET}")
        new_result = await self.run_query(
            query=query,
            use_super_passport=True,
            expert_filter=expert_filter
        )

        # Calculate comparison metrics
        comparison = {
            "test_id": test_id,
            "query": query,
            "description": test_case.get("description", ""),
            "timestamp": datetime.utcnow().isoformat(),
            "old": {
                "success": old_result["success"],
                "latency_ms": old_result["latency_ms"],
                "error": old_result.get("error")
            },
            "new": {
                "success": new_result["success"],
                "latency_ms": new_result["latency_ms"],
                "error": new_result.get("error")
            }
        }

        # Extract and compare sources if both succeeded
        if old_result["success"] and new_result["success"]:
            old_sources = self.extract_sources(old_result["data"])
            new_sources = self.extract_sources(new_result["data"])

            expert_comparisons = {}
            all_old_sources = []
            all_new_sources = []

            for expert_id in set(old_sources.keys()) | set(new_sources.keys()):
                old_expert = old_sources.get(expert_id, [])
                new_expert = new_sources.get(expert_id, [])

                recall, intersection, old_only, new_only = self.calculate_recall(
                    old_expert, new_expert
                )

                expert_comparisons[expert_id] = {
                    "recall": round(recall, 3),
                    "intersection": intersection,
                    "old_only": old_only,
                    "new_only": new_only,
                    "old_sources": old_expert[:5],  # First 5 for debugging
                    "new_sources": new_expert[:5]
                }

                all_old_sources.extend(old_expert)
                all_new_sources.extend(new_expert)

            # Overall metrics
            overall_recall, _, _, _ = self.calculate_recall(
                all_old_sources, all_new_sources
            )

            comparison["metrics"] = {
                "overall_recall": round(overall_recall, 3),
                "total_old_sources": len(set(all_old_sources)),
                "total_new_sources": len(set(all_new_sources)),
                "latency_improvement_ms": round(
                    old_result["latency_ms"] - new_result["latency_ms"], 2
                ),
                "latency_improvement_pct": round(
                    (old_result["latency_ms"] - new_result["latency_ms"]) /
                    old_result["latency_ms"] * 100, 2
                ) if old_result["latency_ms"] > 0 else 0
            }

            comparison["expert_comparisons"] = expert_comparisons

            # Print summary
            self._print_test_summary(comparison)

        else:
            comparison["metrics"] = None
            comparison["expert_comparisons"] = None
            print(f"  {RED}✗ Test failed: old={old_result['success']}, new={new_result['success']}{RESET}")

        self.results.append(comparison)
        return comparison

    def _print_test_summary(self, comparison: Dict):
        """Print test summary with colors."""
        metrics = comparison["metrics"]
        recall = metrics["overall_recall"]
        latency_imp = metrics["latency_improvement_pct"]

        # Recall color
        if recall >= 0.9:
            recall_color = GREEN
            recall_icon = "✓"
        elif recall >= 0.7:
            recall_color = YELLOW
            recall_icon = "△"
        else:
            recall_color = RED
            recall_icon = "✗"

        # Latency color
        if latency_imp > 0:
            latency_color = GREEN
            latency_icon = "↓"
        else:
            latency_color = RED
            latency_icon = "↑"

        print(f"  {recall_color}{recall_icon} Recall: {recall:.1%}{RESET}")
        print(f"  {latency_color}{latency_icon} Latency: {metrics['latency_improvement_pct']:+.1f}% "
              f"({metrics['latency_improvement_ms']:.0f}ms){RESET}")
        print(f"  Sources: {metrics['total_old_sources']} (old) → {metrics['total_new_sources']} (new)")

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all tests."""
        if not self.results:
            return {"message": "No tests run yet"}

        successful = [r for r in self.results if r["metrics"] is not None]
        if not successful:
            return {"message": "No successful tests"}

        recalls = [r["metrics"]["overall_recall"] for r in successful]
        latency_improvements = [r["metrics"]["latency_improvement_pct"] for r in successful]

        return {
            "total_tests": len(self.results),
            "successful_tests": len(successful),
            "avg_recall": round(sum(recalls) / len(recalls), 3),
            "min_recall": round(min(recalls), 3),
            "max_recall": round(max(recalls), 3),
            "avg_latency_improvement_pct": round(
                sum(latency_improvements) / len(latency_improvements), 2
            ),
            "tests_with_good_recall": sum(1 for r in recalls if r >= 0.8),
            "tests_with_poor_recall": sum(1 for r in recalls if r < 0.7)
        }

    def export_results(self, filepath: str):
        """Export results to JSON file."""
        output = {
            "summary": self.get_summary_stats(),
            "results": self.results,
            "config": {
                "base_url": self.base_url,
                "timeout": self.timeout,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{GREEN}Results exported to: {filepath}{RESET}")


async def check_backend_health(base_url: str) -> bool:
    """Check if backend is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except:
        return False


async def main():
    parser = argparse.ArgumentParser(description="A/B Test Super-Passport Search")
    parser.add_argument(
        "--url",
        default=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="Backend URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: 120)"
    )
    parser.add_argument(
        "--experts",
        nargs="+",
        help="Filter by specific expert IDs (e.g., --experts refat nobilix)"
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        help="Custom queries to test (overrides default test cases)"
    )
    parser.add_argument(
        "--output",
        default="ab_test_results.json",
        help="Output file for results (default: ab_test_results.json)"
    )
    parser.add_argument(
        "--list-experts",
        action="store_true",
        help="List available experts and exit"
    )

    args = parser.parse_args()

    # Check backend health
    print(f"{BLUE}Checking backend at {args.url}...{RESET}")
    if not await check_backend_health(args.url):
        print(f"{RED}Error: Backend not responding at {args.url}{RESET}")
        print(f"Start backend with: cd backend && uvicorn src.main:app --reload")
        sys.exit(1)

    print(f"{GREEN}✓ Backend is healthy{RESET}")

    # List experts mode
    if args.list_experts:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{args.url}/api/v1/experts") as resp:
                experts = await resp.json()
                print(f"\n{BOLD}Available Experts:{RESET}")
                for exp in experts:
                    print(f"  - {exp.get('expert_id')}: {exp.get('display_name')}")
        return

    # Prepare test cases
    if args.queries:
        test_cases = [
            {"id": f"custom_{i}", "query": q, "description": f"Custom query {i}"}
            for i, q in enumerate(args.queries, 1)
        ]
    else:
        test_cases = DEFAULT_TEST_QUERIES

    # Run A/B tests
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}A/B Testing: Super-Passport Search{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"Tests: {len(test_cases)}")
    print(f"Expert filter: {args.experts or 'All experts'}")

    runner = ABTestRunner(base_url=args.url, timeout=args.timeout)
    await runner.setup()

    try:
        for test_case in test_cases:
            await runner.run_ab_test(
                test_case=test_case,
                expert_filter=args.experts
            )

        # Print summary
        print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
        print(f"{BOLD}{BLUE}Summary{RESET}")
        print(f"{BOLD}{BLUE}{'=' * 60}{RESET}")

        stats = runner.get_summary_stats()
        if "message" not in stats:
            print(f"Total tests: {stats['total_tests']}")
            print(f"Successful: {stats['successful_tests']}")
            print(f"Average Recall: {stats['avg_recall']:.1%}")
            print(f"Recall range: {stats['min_recall']:.1%} - {stats['max_recall']:.1%}")
            print(f"Avg Latency Improvement: {stats['avg_latency_improvement_pct']:+.1f}%")
            print(f"Good recall (≥80%): {stats['tests_with_good_recall']}")
            print(f"Poor recall (<70%): {stats['tests_with_poor_recall']}")

        # Export results
        output_path = Path(__file__).parent / args.output
        runner.export_results(str(output_path))

    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
