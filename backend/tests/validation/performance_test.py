#!/usr/bin/env python3
"""
Performance Validation Test Runner
Tests system performance against <3 minute response time requirement
"""

import asyncio
import json
import time
import psutil
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import aiohttp
import yaml
import sys
import argparse
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single test run"""
    query_id: str
    query_text: str
    response_time: float
    status_code: int
    memory_before: float
    memory_after: float
    memory_delta: float
    cpu_percent: float
    tokens_used: Optional[int] = None
    posts_processed: Optional[int] = None
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class TestSummary:
    """Summary of all performance tests"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    avg_memory_usage: float
    peak_memory_usage: float
    tests_under_3min: int
    performance_goal_met: bool


class PerformanceValidator:
    """Validates system performance with various test scenarios"""

    def __init__(self, config_file: str = "performance_config.yaml"):
        self.config_file = Path(__file__).parent / config_file
        self.results: List[PerformanceMetrics] = []
        self.load_config()
        self.session = None
        self.process = psutil.Process()

    def load_config(self):
        """Load performance test configuration"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
        else:
            # Default configuration
            config = self.get_default_config()

        self.api_base_url = config['api']['base_url']
        self.timeout = config['api']['timeout_seconds']
        self.performance_targets = config['performance_targets']
        self.test_scenarios = config['test_scenarios']
        self.concurrent_tests = config.get('concurrent_tests', 1)

    def get_default_config(self) -> Dict:
        """Default configuration if config file doesn't exist"""
        return {
            'api': {
                'base_url': 'http://localhost:8000',
                'timeout_seconds': 300  # 5 minutes max
            },
            'performance_targets': {
                'max_response_time_seconds': 180,  # 3 minutes
                'max_memory_mb': 500,
                'success_rate_percent': 95
            },
            'test_scenarios': [
                {
                    'name': 'simple_query',
                    'query': 'What are the main topics discussed?',
                    'expected_posts': 5
                },
                {
                    'name': 'complex_query',
                    'query': 'Analyze all discussions about research and their responses',
                    'expected_posts': 10
                }
            ],
            'concurrent_tests': 1
        }

    async def setup(self):
        """Setup aiohttp session"""
        self.session = aiohttp.ClientSession()

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()

    def measure_system_resources(self) -> Dict[str, float]:
        """Measure current system resource usage"""
        return {
            'memory_mb': self.process.memory_info().rss / 1024 / 1024,
            'cpu_percent': self.process.cpu_percent(interval=0.1)
        }

    async def run_single_query(self, query: str, query_id: str) -> PerformanceMetrics:
        """Run a single query and measure performance"""
        url = f"{self.api_base_url}/api/v1/query"

        # Measure resources before
        resources_before = self.measure_system_resources()

        start_time = time.time()
        metrics = PerformanceMetrics(
            query_id=query_id,
            query_text=query[:100],  # Truncate for logging
            response_time=0,
            status_code=0,
            memory_before=resources_before['memory_mb'],
            memory_after=0,
            memory_delta=0,
            cpu_percent=resources_before['cpu_percent'],
            timestamp=datetime.now().isoformat()
        )

        try:
            async with self.session.post(
                url,
                json={"query": query, "stream_progress": False},
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                metrics.status_code = response.status

                if response.status == 200:
                    result = await response.json()
                    metrics.response_time = time.time() - start_time

                    # Extract metrics from response
                    if 'sources' in result:
                        metrics.posts_processed = len(result.get('sources', []))
                    if 'token_usage' in result:
                        metrics.tokens_used = result['token_usage'].get('total_tokens')
                else:
                    error_text = await response.text()
                    metrics.error = f"HTTP {response.status}: {error_text[:200]}"
                    metrics.response_time = time.time() - start_time

        except asyncio.TimeoutError:
            metrics.error = f"Timeout after {self.timeout} seconds"
            metrics.response_time = self.timeout
            metrics.status_code = 408  # Request Timeout

        except Exception as e:
            metrics.error = str(e)
            metrics.response_time = time.time() - start_time
            metrics.status_code = 500

        # Measure resources after
        resources_after = self.measure_system_resources()
        metrics.memory_after = resources_after['memory_mb']
        metrics.memory_delta = metrics.memory_after - metrics.memory_before

        return metrics

    async def run_concurrent_queries(self, queries: List[Dict]) -> List[PerformanceMetrics]:
        """Run multiple queries concurrently"""
        tasks = []
        for i, scenario in enumerate(queries):
            task = self.run_single_query(
                scenario['query'],
                f"{scenario['name']}_{i}"
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

    async def run_load_test(self, concurrent_users: int = 5) -> List[PerformanceMetrics]:
        """Simulate multiple concurrent users"""
        print(f"\n🔥 Running load test with {concurrent_users} concurrent users...")

        # Create multiple copies of test scenarios
        queries = []
        for user in range(concurrent_users):
            for scenario in self.test_scenarios:
                queries.append({
                    'name': f"user{user}_{scenario['name']}",
                    'query': scenario['query']
                })

        # Run in batches to avoid overwhelming the system
        batch_size = 5
        all_results = []

        for i in range(0, len(queries), batch_size):
            batch = queries[i:i+batch_size]
            print(f"  Running batch {i//batch_size + 1}/{(len(queries)-1)//batch_size + 1}...")
            batch_results = await self.run_concurrent_queries(batch)
            all_results.extend(batch_results)
            await asyncio.sleep(1)  # Brief pause between batches

        return all_results

    async def run_all_tests(self) -> TestSummary:
        """Run all performance test scenarios"""
        print("=" * 70)
        print("🚀 PERFORMANCE VALIDATION TEST SUITE")
        print("=" * 70)
        print(f"Target: <{self.performance_targets['max_response_time_seconds']} seconds response time")
        print(f"API: {self.api_base_url}\n")

        # 1. Individual query tests
        print("📊 Running individual query tests...")
        for scenario in self.test_scenarios:
            print(f"\n  Testing: {scenario['name']}")
            print(f"  Query: {scenario['query'][:60]}...")

            metrics = await self.run_single_query(
                scenario['query'],
                scenario['name']
            )
            self.results.append(metrics)

            # Print immediate feedback
            if metrics.error:
                print(f"  ❌ Failed: {metrics.error}")
            else:
                status = "✅" if metrics.response_time < self.performance_targets['max_response_time_seconds'] else "⚠️"
                print(f"  {status} Response time: {metrics.response_time:.2f}s")
                print(f"  📦 Posts processed: {metrics.posts_processed or 'N/A'}")
                print(f"  💾 Memory delta: {metrics.memory_delta:.1f} MB")

        # 2. Concurrent request test
        if self.concurrent_tests > 1:
            print(f"\n📊 Running concurrent test ({self.concurrent_tests} parallel requests)...")
            concurrent_results = await self.run_concurrent_queries(
                self.test_scenarios[:self.concurrent_tests]
            )
            self.results.extend(concurrent_results)

            avg_concurrent_time = statistics.mean([m.response_time for m in concurrent_results])
            print(f"  Average concurrent response: {avg_concurrent_time:.2f}s")

        # 3. Load test
        print("\n📊 Running load test...")
        load_results = await self.run_load_test(concurrent_users=3)
        self.results.extend(load_results)

        # Generate summary
        summary = self.generate_summary()
        return summary

    def generate_summary(self) -> TestSummary:
        """Generate performance test summary"""
        successful_results = [r for r in self.results if not r.error]
        response_times = [r.response_time for r in successful_results]

        if not response_times:
            response_times = [0]  # Avoid division by zero

        summary = TestSummary(
            total_tests=len(self.results),
            passed_tests=len(successful_results),
            failed_tests=len(self.results) - len(successful_results),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            p95_response_time=self.calculate_percentile(response_times, 95),
            p99_response_time=self.calculate_percentile(response_times, 99),
            avg_memory_usage=statistics.mean([r.memory_delta for r in self.results]),
            peak_memory_usage=max([r.memory_after for r in self.results]),
            tests_under_3min=len([r for r in successful_results
                                 if r.response_time < self.performance_targets['max_response_time_seconds']]),
            performance_goal_met=False
        )

        # Check if performance goal is met
        success_rate = (summary.passed_tests / summary.total_tests * 100) if summary.total_tests > 0 else 0
        summary.performance_goal_met = (
            summary.p95_response_time < self.performance_targets['max_response_time_seconds'] and
            success_rate >= self.performance_targets['success_rate_percent']
        )

        return summary

    def calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def print_summary(self, summary: TestSummary):
        """Print formatted test summary"""
        print("\n" + "=" * 70)
        print("📈 PERFORMANCE TEST SUMMARY")
        print("=" * 70)

        print(f"\n📊 Test Results:")
        print(f"  Total tests: {summary.total_tests}")
        print(f"  Passed: {summary.passed_tests}")
        print(f"  Failed: {summary.failed_tests}")
        print(f"  Success rate: {summary.passed_tests/summary.total_tests*100:.1f}%")

        print(f"\n⏱️ Response Times:")
        print(f"  Average: {summary.avg_response_time:.2f}s")
        print(f"  Minimum: {summary.min_response_time:.2f}s")
        print(f"  Maximum: {summary.max_response_time:.2f}s")
        print(f"  P95: {summary.p95_response_time:.2f}s")
        print(f"  P99: {summary.p99_response_time:.2f}s")

        print(f"\n💾 Memory Usage:")
        print(f"  Average delta: {summary.avg_memory_usage:.1f} MB")
        print(f"  Peak usage: {summary.peak_memory_usage:.1f} MB")

        print(f"\n🎯 Performance Goals:")
        print(f"  Target: <{self.performance_targets['max_response_time_seconds']}s response time")
        print(f"  Tests under target: {summary.tests_under_3min}/{summary.total_tests}")

        if summary.performance_goal_met:
            print(f"\n✅ PERFORMANCE VALIDATION PASSED")
        else:
            print(f"\n❌ PERFORMANCE VALIDATION FAILED")
            print(f"  P95 response time exceeds target or success rate too low")

    def save_report(self, summary: TestSummary):
        """Save detailed performance report"""
        report_file = Path(__file__).parent / "performance_report.md"

        with open(report_file, 'w') as f:
            f.write("# Performance Validation Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Summary section
            f.write("## Executive Summary\n\n")
            f.write(f"- **Performance Goal**: {'✅ MET' if summary.performance_goal_met else '❌ NOT MET'}\n")
            f.write(f"- **Success Rate**: {summary.passed_tests}/{summary.total_tests} ")
            f.write(f"({summary.passed_tests/summary.total_tests*100:.1f}%)\n")
            f.write(f"- **P95 Response Time**: {summary.p95_response_time:.2f}s\n")
            f.write(f"- **Target**: <{self.performance_targets['max_response_time_seconds']}s\n\n")

            # Detailed metrics
            f.write("## Performance Metrics\n\n")
            f.write("### Response Times\n")
            f.write(f"- Average: {summary.avg_response_time:.2f}s\n")
            f.write(f"- Minimum: {summary.min_response_time:.2f}s\n")
            f.write(f"- Maximum: {summary.max_response_time:.2f}s\n")
            f.write(f"- P95: {summary.p95_response_time:.2f}s\n")
            f.write(f"- P99: {summary.p99_response_time:.2f}s\n\n")

            f.write("### Resource Usage\n")
            f.write(f"- Average Memory Delta: {summary.avg_memory_usage:.1f} MB\n")
            f.write(f"- Peak Memory Usage: {summary.peak_memory_usage:.1f} MB\n\n")

            # Individual test results
            f.write("## Detailed Test Results\n\n")
            f.write("| Test ID | Response Time | Status | Memory Delta | Error |\n")
            f.write("|---------|---------------|--------|--------------|-------|\n")

            for metric in self.results[:20]:  # Show first 20 results
                status = "✅" if not metric.error else "❌"
                error = metric.error[:30] if metric.error else "-"
                f.write(f"| {metric.query_id} | {metric.response_time:.2f}s | {status} | ")
                f.write(f"{metric.memory_delta:.1f} MB | {error} |\n")

            if len(self.results) > 20:
                f.write(f"\n*... and {len(self.results) - 20} more test results*\n")

            # Optimization recommendations
            f.write("\n## Recommendations\n\n")
            if summary.max_response_time > self.performance_targets['max_response_time_seconds']:
                f.write("- ⚠️ Some queries exceed the 3-minute target\n")
                f.write("- Consider optimizing the slowest queries\n")
                f.write("- Review chunk size and parallel processing\n")

            if summary.avg_memory_usage > 100:
                f.write("- ⚠️ High memory usage detected\n")
                f.write("- Consider streaming responses\n")
                f.write("- Optimize data structures\n")

            if summary.performance_goal_met:
                f.write("- ✅ System meets performance requirements\n")
                f.write("- Ready for production deployment\n")

        print(f"\n📄 Detailed report saved to: {report_file}")

    def save_raw_results(self):
        """Save raw test results as JSON"""
        results_file = Path(__file__).parent / "performance_results.json"

        results_data = {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'api_base_url': self.api_base_url,
                'timeout': self.timeout,
                'targets': self.performance_targets
            },
            'results': [asdict(r) for r in self.results]
        }

        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)

        print(f"📊 Raw results saved to: {results_file}")


async def main():
    """Main entry point for performance testing"""
    parser = argparse.ArgumentParser(description="Performance validation testing")
    parser.add_argument(
        "--config",
        default="performance_config.yaml",
        help="Configuration file (default: performance_config.yaml)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test (fewer scenarios)"
    )
    args = parser.parse_args()

    # Create validator
    validator = PerformanceValidator(args.config)

    if args.quick:
        # Reduce test scenarios for quick test
        validator.test_scenarios = validator.test_scenarios[:2]
        validator.concurrent_tests = 1

    await validator.setup()

    try:
        # Run all tests
        summary = await validator.run_all_tests()

        # Print summary
        validator.print_summary(summary)

        # Save reports
        validator.save_report(summary)
        validator.save_raw_results()

        # Exit code based on performance goal
        return 0 if summary.performance_goal_met else 1

    finally:
        await validator.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)