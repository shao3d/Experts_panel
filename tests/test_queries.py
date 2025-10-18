#!/usr/bin/env python3
"""
Test Queries Validation Script

Runs a suite of test queries against the API to validate functionality
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import aiohttp
import argparse

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# ANSI colors for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


class TestQueryRunner:
    """Runs test queries and validates results"""

    def __init__(self, config_file: str = "test_queries.json"):
        self.config_file = Path(__file__).parent / config_file
        self.load_config()
        self.results = []
        self.session = None

    def load_config(self):
        """Load test configuration from JSON"""
        with open(self.config_file, 'r') as f:
            config = json.load(f)
            self.test_queries = config['test_queries']
            self.validation_config = config['validation_config']
            self.performance_thresholds = config['performance_thresholds']

    async def setup(self):
        """Setup aiohttp session"""
        self.session = aiohttp.ClientSession()

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
        print(f"{BOLD}{BLUE}{text}{RESET}")
        print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    def print_test_header(self, test: Dict):
        """Print test information"""
        print(f"\n{CYAN}▶ Test {test['id']}: {test['name']}{RESET}")
        print(f"  Query: {test['query']}")
        print(f"  Type: {test['type']}")

    async def run_query(self, query: str) -> Dict[str, Any]:
        """Run a single query against the API"""
        url = f"{self.validation_config['api_base_url']}/api/v1/query"

        start_time = time.time()

        try:
            async with self.session.post(
                url,
                json={"query": query},
                timeout=aiohttp.ClientTimeout(total=self.validation_config['timeout_seconds'])
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    elapsed_time = time.time() - start_time
                    return {
                        "success": True,
                        "data": result,
                        "response_time": elapsed_time,
                        "status_code": response.status
                    }
                else:
                    text = await response.text()
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {text}",
                        "response_time": time.time() - start_time,
                        "status_code": response.status
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timeout",
                "response_time": self.validation_config['timeout_seconds']
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }

    async def run_query_with_sse(self, query: str) -> Dict[str, Any]:
        """Run query and monitor SSE events"""
        url = f"{self.validation_config['api_base_url']}/api/v1/query/stream"
        params = {"query": query}

        start_time = time.time()
        events = []
        result_data = None

        try:
            async with self.session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.validation_config['timeout_seconds'])
            ) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "response_time": time.time() - start_time
                    }

                async for line in response.content:
                    if line:
                        decoded = line.decode('utf-8').strip()
                        if decoded.startswith('data: '):
                            try:
                                event_data = json.loads(decoded[6:])
                                events.append(event_data)

                                # Check for result
                                if event_data.get('type') == 'result':
                                    result_data = event_data.get('result', {})

                                # Check for error
                                if event_data.get('type') == 'error':
                                    return {
                                        "success": False,
                                        "error": event_data.get('error', 'Unknown error'),
                                        "response_time": time.time() - start_time,
                                        "events": events
                                    }

                            except json.JSONDecodeError:
                                continue

                elapsed_time = time.time() - start_time

                return {
                    "success": True if result_data else False,
                    "data": result_data,
                    "response_time": elapsed_time,
                    "events": events,
                    "phases_completed": self._extract_phases(events)
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }

    def _extract_phases(self, events: List[Dict]) -> List[str]:
        """Extract completed phases from events"""
        phases = set()
        for event in events:
            if event.get('type') == 'phase_complete':
                phase = event.get('phase')
                if phase:
                    phases.add(phase)
        return list(phases)

    def validate_result(self, test: Dict, result: Dict) -> Dict[str, Any]:
        """Validate query result against expectations"""
        validation = {
            "passed": True,
            "checks": [],
            "warnings": []
        }

        # Check if query succeeded
        if not result.get('success'):
            validation['passed'] = False
            validation['checks'].append(f"{RED}✗ Query failed: {result.get('error')}{RESET}")
            return validation

        data = result.get('data', {})
        expected = test.get('expected', {})

        # Check response time
        response_time = result.get('response_time', 0)
        if response_time > self.performance_thresholds['max_response_time_seconds']:
            validation['warnings'].append(
                f"{YELLOW}⚠ Slow response: {response_time:.2f}s "
                f"(threshold: {self.performance_thresholds['max_response_time_seconds']}s){RESET}"
            )
        else:
            validation['checks'].append(f"{GREEN}✓ Response time: {response_time:.2f}s{RESET}")

        # Check minimum sources
        sources = data.get('sources', [])
        min_sources = expected.get('min_sources', self.performance_thresholds['min_sources_returned'])
        if len(sources) >= min_sources:
            validation['checks'].append(f"{GREEN}✓ Sources found: {len(sources)} (min: {min_sources}){RESET}")
        else:
            validation['passed'] = False
            validation['checks'].append(
                f"{RED}✗ Insufficient sources: {len(sources)} (min: {min_sources}){RESET}"
            )

        # Check for keywords in answer
        answer = data.get('answer', '').lower()
        keywords = expected.get('keywords', [])
        found_keywords = [kw for kw in keywords if kw.lower() in answer]
        if found_keywords:
            validation['checks'].append(
                f"{GREEN}✓ Keywords found: {', '.join(found_keywords)}{RESET}"
            )
        else:
            validation['warnings'].append(
                f"{YELLOW}⚠ No expected keywords found in answer{RESET}"
            )

        # Check phases (if using SSE)
        if 'phases_completed' in result:
            phases = result['phases_completed']
            required_phases = expected.get('phases_required', [])
            missing_phases = set(required_phases) - set(phases)
            if not missing_phases:
                validation['checks'].append(
                    f"{GREEN}✓ All phases completed: {', '.join(phases)}{RESET}"
                )
            else:
                validation['passed'] = False
                validation['checks'].append(
                    f"{RED}✗ Missing phases: {', '.join(missing_phases)}{RESET}"
                )

        return validation

    async def run_test(self, test: Dict) -> Dict[str, Any]:
        """Run a single test query"""
        self.print_test_header(test)

        # Run query
        if self.validation_config.get('check_sse_events'):
            result = await self.run_query_with_sse(test['query'])
        else:
            result = await self.run_query(test['query'])

        # Validate result
        validation = self.validate_result(test, result)

        # Print validation results
        for check in validation['checks']:
            print(f"  {check}")
        for warning in validation['warnings']:
            print(f"  {warning}")

        # Store result
        test_result = {
            "test": test,
            "result": result,
            "validation": validation,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(test_result)

        return test_result

    async def run_all_tests(self):
        """Run all test queries"""
        self.print_header("Running Test Queries")

        total_tests = len(self.test_queries)
        passed_tests = 0
        failed_tests = 0

        for i, test in enumerate(self.test_queries, 1):
            print(f"\n{BOLD}Test {i}/{total_tests}{RESET}")

            try:
                test_result = await self.run_test(test)

                if test_result['validation']['passed']:
                    passed_tests += 1
                else:
                    failed_tests += 1

                # Small delay between tests
                if i < total_tests:
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"  {RED}✗ Test failed with exception: {e}{RESET}")
                failed_tests += 1

        # Print summary
        self.print_summary(passed_tests, failed_tests, total_tests)

        # Save results if configured
        if self.validation_config.get('save_responses'):
            self.save_results()

        return passed_tests == total_tests

    def print_summary(self, passed: int, failed: int, total: int):
        """Print test summary"""
        self.print_header("Test Summary")

        success_rate = passed / total if total > 0 else 0

        print(f"{BOLD}Results:{RESET}")
        print(f"  {GREEN}✓ Passed: {passed}/{total}{RESET}")
        print(f"  {RED}✗ Failed: {failed}/{total}{RESET}")
        print(f"  Success rate: {success_rate:.1%}")

        # Performance summary
        if self.results:
            response_times = [
                r['result']['response_time']
                for r in self.results
                if 'response_time' in r['result']
            ]
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                max_time = max(response_times)
                min_time = min(response_times)

                print(f"\n{BOLD}Performance:{RESET}")
                print(f"  Average response time: {avg_time:.2f}s")
                print(f"  Fastest response: {min_time:.2f}s")
                print(f"  Slowest response: {max_time:.2f}s")

        # Check against thresholds
        required_rate = self.performance_thresholds['required_success_rate']
        if success_rate >= required_rate:
            print(f"\n{GREEN}{BOLD}✅ VALIDATION PASSED{RESET}")
            print(f"Success rate {success_rate:.1%} meets requirement ({required_rate:.1%})")
        else:
            print(f"\n{RED}{BOLD}❌ VALIDATION FAILED{RESET}")
            print(f"Success rate {success_rate:.1%} below requirement ({required_rate:.1%})")

    def save_results(self):
        """Save test results to file"""
        output_dir = Path(self.validation_config.get('output_dir', 'test_results'))
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"test_results_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n{GREEN}Results saved to: {output_file}{RESET}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run test queries validation")
    parser.add_argument(
        "--config",
        default="test_queries.json",
        help="Test configuration file (default: test_queries.json)"
    )
    parser.add_argument(
        "--no-sse",
        action="store_true",
        help="Disable SSE event checking"
    )
    args = parser.parse_args()

    # Create runner
    runner = TestQueryRunner(args.config)

    # Override SSE checking if requested
    if args.no_sse:
        runner.validation_config['check_sse_events'] = False

    # Setup
    await runner.setup()

    try:
        # Run tests
        success = await runner.run_all_tests()
        return 0 if success else 1
    finally:
        # Cleanup
        await runner.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)