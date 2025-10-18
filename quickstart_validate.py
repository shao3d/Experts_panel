#!/usr/bin/env python3
"""
Quickstart Validation Script for Experts Panel

This script validates that the project can be started from scratch
and all dependencies are properly configured.
"""

import os
import sys
import subprocess
import json
import time
import sqlite3
from pathlib import Path
from typing import Tuple, List, Dict

# ANSI color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

class QuickstartValidator:
    """Validates project setup and configuration"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.successes = []
        self.project_root = Path(__file__).parent.absolute()

    def print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
        print(f"{BOLD}{BLUE}{text}{RESET}")
        print(f"{BOLD}{BLUE}{'=' * 60}{RESET}\n")

    def print_success(self, message: str):
        """Print success message"""
        print(f"{GREEN}✓{RESET} {message}")
        self.successes.append(message)

    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{YELLOW}⚠{RESET} {message}")
        self.warnings.append(message)

    def print_error(self, message: str):
        """Print error message"""
        print(f"{RED}✗{RESET} {message}")
        self.errors.append(message)

    def check_python_version(self) -> bool:
        """Check Python version is 3.11+"""
        self.print_header("Checking Python Version")

        version = sys.version_info
        if version.major >= 3 and version.minor >= 11:
            self.print_success(f"Python {version.major}.{version.minor}.{version.micro} ✓")
            return True
        else:
            self.print_error(f"Python 3.11+ required, found {version.major}.{version.minor}")
            return False

    def check_node_version(self) -> bool:
        """Check Node.js installation"""
        self.print_header("Checking Node.js")

        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True
            )
            version = result.stdout.strip()
            self.print_success(f"Node.js {version} ✓")

            # Check npm as well
            npm_result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True
            )
            npm_version = npm_result.stdout.strip()
            self.print_success(f"npm {npm_version} ✓")
            return True
        except FileNotFoundError:
            self.print_error("Node.js not found. Please install Node.js 18+")
            return False

    def check_python_dependencies(self) -> bool:
        """Check if Python dependencies are installed"""
        self.print_header("Checking Python Dependencies")

        requirements_file = self.project_root / "backend" / "requirements.txt"

        if not requirements_file.exists():
            self.print_error(f"requirements.txt not found at {requirements_file}")
            return False

        # Check for key packages
        key_packages = [
            "fastapi",
            "sqlalchemy",
            "openai",
            "pydantic",
            "uvicorn",
            "sse-starlette"
        ]

        missing_packages = []

        for package in key_packages:
            try:
                __import__(package.replace("-", "_"))
                self.print_success(f"Package {package} ✓")
            except ImportError:
                missing_packages.append(package)
                self.print_error(f"Package {package} not installed")

        if missing_packages:
            print(f"\n{YELLOW}To install missing packages:{RESET}")
            print(f"cd backend && pip install -r requirements.txt")
            return False

        return True

    def check_npm_dependencies(self) -> bool:
        """Check if npm dependencies are installed"""
        self.print_header("Checking Frontend Dependencies")

        node_modules = self.project_root / "frontend" / "node_modules"
        package_json = self.project_root / "frontend" / "package.json"

        if not package_json.exists():
            self.print_error("frontend/package.json not found")
            return False

        if not node_modules.exists():
            self.print_warning("node_modules not found")
            print(f"\n{YELLOW}To install dependencies:{RESET}")
            print("cd frontend && npm install")
            return False

        # Check for key packages
        key_packages = [
            "react",
            "typescript",
            "vite",
            "@tanstack/react-query",
            "react-markdown",
            "react-syntax-highlighter"
        ]

        with open(package_json, 'r') as f:
            pkg_data = json.load(f)
            deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}

        for package in key_packages:
            if package in deps:
                self.print_success(f"Package {package} ✓")
            else:
                self.print_error(f"Package {package} not in package.json")

        return node_modules.exists()

    def check_database(self) -> bool:
        """Check database setup"""
        self.print_header("Checking Database")

        db_path = self.project_root / "data" / "experts.db"

        if not db_path.exists():
            self.print_error(f"Database not found at {db_path}")
            print(f"\n{YELLOW}To create database:{RESET}")
            print("1. mkdir -p data")
            print("2. sqlite3 data/experts.db < schema.sql")
            return False

        # Check if database has tables
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ["posts", "links", "expert_comments"]

            for table in required_tables:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    self.print_success(f"Table '{table}' exists ({count} rows)")
                else:
                    self.print_error(f"Table '{table}' not found")

            conn.close()

            if not all(t in tables for t in required_tables):
                return False

            # Check if we have data
            if all(t in tables for t in required_tables):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM posts")
                post_count = cursor.fetchone()[0]
                conn.close()

                if post_count == 0:
                    self.print_warning("Database exists but has no posts")
                    print(f"\n{YELLOW}To import data:{RESET}")
                    print("1. Place Telegram JSON export in data/exports/")
                    print("2. cd backend && python -m src.data.json_parser <json_file>")

            return True

        except Exception as e:
            self.print_error(f"Database error: {e}")
            return False

    def check_environment_variables(self) -> bool:
        """Check environment configuration"""
        self.print_header("Checking Environment Variables")

        backend_env = self.project_root / "backend" / ".env"
        env_example = self.project_root / "backend" / ".env.example"

        if not backend_env.exists():
            if env_example.exists():
                self.print_warning(".env not found, but .env.example exists")
                print(f"\n{YELLOW}To create .env:{RESET}")
                print("cp backend/.env.example backend/.env")
                print("Then edit backend/.env and add your OPENAI_API_KEY")
            else:
                self.print_error("No .env or .env.example found")
            return False

        # Check for required variables
        required_vars = ["OPENAI_API_KEY"]
        found_vars = {}

        with open(backend_env, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        found_vars[key.strip()] = value.strip()

        for var in required_vars:
            if var in found_vars:
                value = found_vars[var]
                if value and value != "your_openai_api_key_here":
                    if var == "OPENAI_API_KEY":
                        # Mask the API key
                        masked = value[:7] + "..." + value[-4:] if len(value) > 11 else "***"
                        self.print_success(f"{var} = {masked} ✓")
                else:
                    self.print_error(f"{var} not configured (placeholder value)")
                    return False
            else:
                self.print_error(f"{var} not found in .env")
                return False

        return True

    def check_ports_available(self) -> bool:
        """Check if required ports are available"""
        self.print_header("Checking Port Availability")

        ports = {
            8000: "Backend API",
            5173: "Frontend Dev Server"
        }

        blocked_ports = []

        for port, service in ports.items():
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', port))
                sock.close()

                if result == 0:
                    self.print_warning(f"Port {port} ({service}) is already in use")
                    blocked_ports.append(port)
                else:
                    self.print_success(f"Port {port} ({service}) is available ✓")
            except Exception as e:
                self.print_warning(f"Could not check port {port}: {e}")

        if blocked_ports:
            print(f"\n{YELLOW}Ports in use. You may need to:{RESET}")
            print("1. Stop existing services, OR")
            print("2. Use different ports in configuration")

        return True  # Non-critical, just warning

    def test_backend_startup(self) -> bool:
        """Test if backend can start"""
        self.print_header("Testing Backend Startup")

        try:
            # Start backend process
            process = subprocess.Popen(
                ["python", "-m", "uvicorn", "src.api.main:app", "--port", "8000"],
                cwd=self.project_root / "backend",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            print("Starting backend server...")
            time.sleep(5)  # Give it time to start

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.print_error("Backend failed to start")
                if stderr:
                    print(f"{RED}Error output:{RESET}")
                    print(stderr[:500])  # First 500 chars of error
                return False

            # Test health endpoint
            import requests
            try:
                response = requests.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    self.print_success(f"Backend started successfully ✓")
                    self.print_success(f"Health check: {data['status']}")
                    if data.get('database') == 'healthy':
                        self.print_success("Database connection: healthy ✓")
                    if data.get('openai_configured'):
                        self.print_success("OpenAI API key: configured ✓")
                else:
                    self.print_error(f"Health check failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                self.print_error(f"Could not connect to backend: {e}")

            # Stop the process
            process.terminate()
            process.wait(timeout=5)

            return True

        except Exception as e:
            self.print_error(f"Failed to test backend: {e}")
            return False

    def print_summary(self):
        """Print validation summary"""
        self.print_header("Validation Summary")

        total_checks = len(self.successes) + len(self.warnings) + len(self.errors)

        print(f"{BOLD}Results:{RESET}")
        print(f"  {GREEN}✓ Passed:{RESET} {len(self.successes)}")
        print(f"  {YELLOW}⚠ Warnings:{RESET} {len(self.warnings)}")
        print(f"  {RED}✗ Failed:{RESET} {len(self.errors)}")

        if self.errors:
            print(f"\n{RED}{BOLD}❌ Validation FAILED{RESET}")
            print("\nPlease fix the errors above before running the project.")
        elif self.warnings:
            print(f"\n{YELLOW}{BOLD}⚠️ Validation PASSED with warnings{RESET}")
            print("\nThe project should run, but check the warnings.")
        else:
            print(f"\n{GREEN}{BOLD}✅ Validation PASSED{RESET}")
            print("\nProject is ready to run!")

        # Quick start commands
        print(f"\n{BOLD}Quick Start Commands:{RESET}")
        print("\n1. Start Backend:")
        print("   cd backend")
        print("   uvicorn src.api.main:app --reload --port 8000")

        print("\n2. Start Frontend:")
        print("   cd frontend")
        print("   npm run dev")

        print("\n3. Open Browser:")
        print("   http://localhost:5173")

        if not self.errors:
            print(f"\n{GREEN}Ready to go! 🚀{RESET}")

    def run(self) -> bool:
        """Run all validation checks"""
        print(f"{BOLD}🔍 Experts Panel - Quickstart Validation{RESET}")
        print(f"Project Root: {self.project_root}")

        # Run checks
        checks = [
            self.check_python_version,
            self.check_node_version,
            self.check_python_dependencies,
            self.check_npm_dependencies,
            self.check_database,
            self.check_environment_variables,
            self.check_ports_available,
            self.test_backend_startup,
        ]

        for check in checks:
            try:
                check()
            except Exception as e:
                self.print_error(f"Check failed with exception: {e}")

        # Print summary
        self.print_summary()

        return len(self.errors) == 0


def main():
    """Main entry point"""
    validator = QuickstartValidator()
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()