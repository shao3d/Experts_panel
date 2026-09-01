#!/usr/bin/env python3
"""Contract tests for the shareable generic Reddit Search client."""

from __future__ import annotations

import os
import stat
import subprocess
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parents[2]
INSTALLER = ROOT / "clients" / "reddit-search-generic" / "install.sh"
RUNNER = ROOT / "scripts" / "reddit_search_runner.py"
BUILDER = ROOT / "scripts" / "build_reddit_search_generic_client.sh"


def test_generic_installer_uses_reddit_only_token_without_printing_it(tmp_path):
    install_root = tmp_path / "share" / "reddit-search"
    bin_dir = tmp_path / "bin"
    config_dir = tmp_path / "config"
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "install.sh").write_bytes(INSTALLER.read_bytes())
    (package_dir / "reddit_search_runner.py").write_bytes(RUNNER.read_bytes())
    (package_dir / "AGENT_INSTRUCTIONS.md").write_text(
        "Run reddit-search for explicit Reddit requests.\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "REDDIT_SEARCH_API_TOKEN": "brother-test-token",
            "REDDIT_SEARCH_INSTALL_ROOT": str(install_root),
            "REDDIT_SEARCH_BIN_DIR": str(bin_dir),
            "REDDIT_SEARCH_CONFIG_DIR": str(config_dir),
        }
    )
    result = subprocess.run(
        ["bash", str(package_dir / "install.sh")],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "brother-test-token" not in result.stdout
    assert "brother-test-token" not in result.stderr
    token_file = config_dir / "token"
    assert token_file.read_text(encoding="utf-8") == "brother-test-token"
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    assert (bin_dir / "reddit-search").is_file()
    assert (install_root / "reddit_search_runner.py").is_file()
    assert (config_dir / "AGENT_INSTRUCTIONS.md").is_file()


def test_personalized_package_installs_without_questions_and_removes_extracted_token(tmp_path):
    token_source = tmp_path / "oleg-token"
    token_source.write_text("personal-test-token", encoding="utf-8")
    output_dir = tmp_path / "dist"
    env = os.environ.copy()
    env.update(
        {
            "REDDIT_SEARCH_TOKEN_FILE": str(token_source),
            "REDDIT_SEARCH_PACKAGE_NAME": "reddit-search-oleg-test",
            "REDDIT_SEARCH_PACKAGE_OUTPUT_DIR": str(output_dir),
        }
    )
    build = subprocess.run(
        ["bash", str(BUILDER)], env=env, text=True, capture_output=True, check=False
    )
    assert build.returncode == 0, build.stderr
    assert "personal-test-token" not in build.stdout + build.stderr

    archive = output_dir / "reddit-search-oleg-test.zip"
    extract_dir = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as package:
        assert "reddit-search-oleg-test/.reddit-search-token" in package.namelist()
        assert "reddit-search-oleg-test/AGENT_SETUP.md" in package.namelist()
        package.extractall(extract_dir)

    package_dir = extract_dir / "reddit-search-oleg-test"
    install_root = tmp_path / "installed" / "share"
    bin_dir = tmp_path / "installed" / "bin"
    config_dir = tmp_path / "installed" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "token").write_text("stale-token", encoding="utf-8")
    install_env = os.environ.copy()
    install_env.update(
        {
            "REDDIT_SEARCH_INSTALL_ROOT": str(install_root),
            "REDDIT_SEARCH_BIN_DIR": str(bin_dir),
            "REDDIT_SEARCH_CONFIG_DIR": str(config_dir),
        }
    )
    install = subprocess.run(
        ["bash", str(package_dir / "install.sh"), "--non-interactive"],
        env=install_env,
        text=True,
        input="",
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    assert "personal-test-token" not in install.stdout + install.stderr
    assert (config_dir / "token").read_text(encoding="utf-8") == "personal-test-token"
    assert stat.S_IMODE((config_dir / "token").stat().st_mode) == 0o600
    assert not (package_dir / ".reddit-search-token").exists()

    class ApiHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/health"
            body = b'{"status":"healthy","diagnostics":{"database":{"status":"connected"}}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            assert self.path == "/api/v1/agent/reddit-search"
            assert self.headers.get("Authorization") == "Bearer personal-test-token"
            body = b'{"status":"abstained","message":"test fixture","sources":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    command_env = install_env.copy()
    command_env["REDDIT_SEARCH_API_URL"] = (
        f"http://127.0.0.1:{server.server_port}/api/v1/agent/reddit-search"
    )
    try:
        doctor = subprocess.run(
            [str(bin_dir / "reddit-search"), "--doctor"],
            env=command_env,
            text=True,
            capture_output=True,
            check=False,
        )
        smoke = subprocess.run(
            [str(bin_dir / "reddit-search"), "--json", "test question"],
            env=command_env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

    assert doctor.returncode == 0, doctor.stderr
    assert '"health_status": "healthy"' in doctor.stdout
    assert smoke.returncode == 0, smoke.stderr
    assert '"status": "abstained"' in smoke.stdout
    assert "personal-test-token" not in doctor.stdout + doctor.stderr + smoke.stdout + smoke.stderr
