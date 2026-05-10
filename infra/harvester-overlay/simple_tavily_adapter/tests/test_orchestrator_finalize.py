"""Final report contract tests for the ACP research orchestrator."""
from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Generator
from contextlib import contextmanager

from events import Event
from orchestrator import Orchestrator, Job, JobStatus, PARTIAL_REPORT_FILENAME


@contextmanager
def _event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _orchestrator(tmp_path) -> Orchestrator:
    return Orchestrator(
        hermes_bin="hermes",
        skills=["searcharvester-deep-research"],
        jobs_dir=tmp_path,
        env={},
        timeout_sec=5,
        citation_repair_enabled=False,
    )


def test_finalize_uses_existing_report_file(tmp_path):
    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        workspace.mkdir()
        (workspace / "report.md").write_text("# Final report\n", encoding="utf-8")
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error is None
    assert job.report == "# Final report\n"
    assert (workspace / "report.md").read_text(encoding="utf-8") == "# Final report\n"


def test_finalize_keeps_extract_backed_citations_clean(tmp_path):
    verified_url = "https://example.com/verified"

    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True)
        extract_id = hashlib.md5(verified_url.encode("utf-8")).hexdigest()[:16]
        (extracts_dir / f"{extract_id}.md").write_text("verified source", encoding="utf-8")
        (workspace / "report.md").write_text(
            "# Final report\n\nClaim [1].\n\n## References\n[1] Verified - https://example.com/verified\n",
            encoding="utf-8",
        )
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error is None
    assert "search_only_unverified" not in job.report
    assert job.citation_integrity == {
        "total_urls": 1,
        "verified_urls": 1,
        "unverified_urls": 0,
        "unverified": [],
    }
    done = [event for event in job.events if event.type == "done"][-1]
    assert done.payload["status"] == "completed"
    assert done.payload["citation_integrity"] == job.citation_integrity
    assert "degraded" not in done.payload


def test_finalize_marks_unverified_report_citations(tmp_path):
    verified_url = "https://example.com/verified"
    unverified_url = "https://example.com/search-only"

    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True)
        extract_id = hashlib.md5(verified_url.encode("utf-8")).hexdigest()[:16]
        (extracts_dir / f"{extract_id}.md").write_text("verified source", encoding="utf-8")
        (workspace / "report.md").write_text(
            "# Final report\n\nClaim [1], caveat [2].\n\n"
            "## References\n"
            "[1] Verified - https://example.com/verified\n"
            "[2] Search-only - https://example.com/search-only\n",
            encoding="utf-8",
        )
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error == "citation contract degraded - unverified citations: 1"
    assert job.citation_integrity == {
        "total_urls": 2,
        "verified_urls": 1,
        "unverified_urls": 1,
        "unverified": [unverified_url],
    }
    assert f"{unverified_url} [search_only_unverified]" in job.report
    assert "## Citation Integrity" in job.report
    assert "Search-only/unverified URLs: 1" in job.report
    assert (workspace / "report.md").read_text(encoding="utf-8") == job.report
    done = [event for event in job.events if event.type == "done"][-1]
    assert done.payload["status"] == "completed"
    assert done.payload["degraded"] is True
    assert done.payload["note"] == job.error
    assert done.payload["citation_integrity"] == job.citation_integrity


def test_standard_finalize_repairs_unverified_report_citations(tmp_path):
    repaired_url = "https://example.com/later-extracted"

    async def repairer(url, workspace):
        assert url == repaired_url
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True, exist_ok=True)
        extract_id = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
        (extracts_dir / f"{extract_id}.md").write_text("repaired source", encoding="utf-8")
        return True

    with _event_loop() as loop:
        orch = Orchestrator(
            hermes_bin="hermes",
            skills=["searcharvester-standard-research"],
            jobs_dir=tmp_path,
            env={},
            timeout_sec=5,
            citation_repairer=repairer,
        )
        workspace = tmp_path / "job"
        workspace.mkdir()
        (workspace / "report.md").write_text(
            "# Final report\n\nClaim [1].\n\n"
            f"## References\n[1] Later extracted - {repaired_url}\n",
            encoding="utf-8",
        )
        job = Job(
            id="job",
            query="q",
            mode="standard",
            status=JobStatus.running,
            workspace_path=workspace,
        )

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error is None
    assert job.citation_integrity == {
        "total_urls": 1,
        "verified_urls": 1,
        "unverified_urls": 0,
        "unverified": [],
        "repaired_urls": [repaired_url],
    }
    assert "search_only_unverified" not in job.report
    done = [event for event in job.events if event.type == "done"][-1]
    assert "degraded" not in done.payload
    assert done.payload["citation_integrity"] == job.citation_integrity


def test_deep_finalize_also_repairs_unverified_report_citations(tmp_path):
    repaired_url = "https://example.com/deep-later-extracted"

    async def repairer(url, workspace):
        assert url == repaired_url
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True, exist_ok=True)
        extract_id = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
        (extracts_dir / f"{extract_id}.md").write_text("deep repaired source", encoding="utf-8")
        return True

    with _event_loop() as loop:
        orch = Orchestrator(
            hermes_bin="hermes",
            skills=["searcharvester-deep-research"],
            jobs_dir=tmp_path,
            env={},
            timeout_sec=5,
            citation_repairer=repairer,
        )
        workspace = tmp_path / "job"
        workspace.mkdir()
        (workspace / "report.md").write_text(
            "# Deep final report\n\nClaim [1].\n\n"
            f"## References\n[1] Later extracted - {repaired_url}\n",
            encoding="utf-8",
        )
        job = Job(
            id="job",
            query="q",
            mode="deep",
            status=JobStatus.running,
            workspace_path=workspace,
        )

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error is None
    assert job.citation_integrity == {
        "total_urls": 1,
        "verified_urls": 1,
        "unverified_urls": 0,
        "unverified": [],
        "repaired_urls": [repaired_url],
    }
    assert "search_only_unverified" not in job.report
    done = [event for event in job.events if event.type == "done"][-1]
    assert "degraded" not in done.payload
    assert done.payload["citation_integrity"] == job.citation_integrity


def test_finalize_normalizes_markdown_backtick_urls(tmp_path):
    verified_url = "https://example.com/verified"

    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True)
        extract_id = hashlib.md5(verified_url.encode("utf-8")).hexdigest()[:16]
        (extracts_dir / f"{extract_id}.md").write_text("verified source", encoding="utf-8")
        (workspace / "report.md").write_text(
            "# Final report\n\n## References\n"
            f"- Verified — `{verified_url}`\n",
            encoding="utf-8",
        )
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error is None
    assert job.citation_integrity == {
        "total_urls": 1,
        "verified_urls": 1,
        "unverified_urls": 0,
        "unverified": [],
    }
    assert "search_only_unverified" not in job.report


def test_standard_finalize_degrades_when_extracts_exist_but_report_has_no_urls(tmp_path):
    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True)
        (extracts_dir / "abc123.md").write_text("source text", encoding="utf-8")
        (workspace / "report.md").write_text(
            "# Final report\n\nSource: abc123.md\n",
            encoding="utf-8",
        )
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.completed
    assert job.error == "citation contract degraded - no report URLs"
    assert job.citation_integrity == {
        "total_urls": 0,
        "verified_urls": 0,
        "unverified_urls": 0,
        "unverified": [],
    }
    assert "## Citation Integrity" in job.report
    done = [event for event in job.events if event.type == "done"][-1]
    assert done.payload["degraded"] is True
    assert done.payload["note"] == job.error


def test_finalize_recovers_only_final_lead_message_when_report_file_missing(tmp_path):
    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        workspace.mkdir()
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)
        job.events = [
            Event.now(
                job_id="job",
                agent_id="sub-a-1",
                parent_id="lead",
                type="message",
                payload={"text": "### Findings\nSub-agent evidence must not leak."},
            ),
            Event.now(
                job_id="job",
                agent_id="lead",
                parent_id=None,
                type="message",
                payload={"text": "# Final report\n\nOnly this should be saved.\n\nREPORT_SAVED: ./report.md"},
            ),
        ]

        loop.run_until_complete(orch._finalize_success(job))

    report_path = workspace / "report.md"
    assert job.status == JobStatus.completed
    assert job.error == "report.md missing - recovered final lead message"
    assert job.report == "# Final report\n\nOnly this should be saved."
    assert report_path.read_text(encoding="utf-8") == job.report
    assert "Sub-agent evidence" not in job.report
    done = [event for event in job.events if event.type == "done"][-1]
    assert done.payload["status"] == "completed"
    assert done.payload["degraded"] is True
    assert done.payload["report_bytes"] == len(job.report)


def test_finalize_fails_without_report_or_final_lead_message(tmp_path):
    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        workspace.mkdir()
        job = Job(id="job", query="q", status=JobStatus.running, workspace_path=workspace)
        job.events = [
            Event.now(
                job_id="job",
                agent_id="sub-a-1",
                parent_id="lead",
                type="message",
                payload={"text": "Sub-agent output is not a final report."},
            )
        ]

        loop.run_until_complete(orch._finalize_success(job))

    assert job.status == JobStatus.failed
    assert job.report is None
    assert not (workspace / "report.md").exists()
    assert job.error == "agent finished without report.md or final lead message"


def test_timeout_partial_report_packages_existing_progress(tmp_path):
    with _event_loop() as loop:
        orch = _orchestrator(tmp_path)
        workspace = tmp_path / "job"
        extracts_dir = workspace / "extracts"
        extracts_dir.mkdir(parents=True)
        (extracts_dir / "source-a.md").write_text(
            "# Source A\n\nExtracted source body.",
            encoding="utf-8",
        )
        (workspace / "plan.md").write_text("# Plan\n", encoding="utf-8")
        job = Job(
            id="job",
            query="compare realistic deep research workflows",
            mode="deep",
            status=JobStatus.running,
            workspace_path=workspace,
        )
        job.events = [
            Event.now(
                job_id="job",
                agent_id="lead",
                type="tool_call",
                payload={
                    "id": "call-1",
                    "title": "delegate task",
                    "preview": "Round 1 researchers",
                },
            ),
            Event.now(
                job_id="job",
                agent_id="sub-call-1-1",
                parent_id="lead",
                type="spawn",
                payload={"goal": "Find current sources about deep research UX."},
            ),
            Event.now(
                job_id="job",
                agent_id="sub-call-1-1",
                parent_id="lead",
                type="message",
                payload={"text": "Found two extract-backed sources and one caveat."},
            ),
            Event.now(
                job_id="job",
                agent_id="sub-call-1-1",
                parent_id="lead",
                type="done",
                payload={"status": "completed"},
            ),
        ]

        loop.run_until_complete(
            orch._persist_partial_report(job, "exceeded timeout of 5s")
        )

    partial_path = workspace / PARTIAL_REPORT_FILENAME
    assert partial_path.exists()
    assert job.partial_report == partial_path.read_text(encoding="utf-8")
    assert "Partial Deep Research Report" in job.partial_report
    assert "not a final research report" in job.partial_report
    assert "compare realistic deep research workflows" in job.partial_report
    assert "Sub-agent status counts" in job.partial_report
    assert "Found two extract-backed sources" in job.partial_report
    assert "source-a.md" in job.partial_report
