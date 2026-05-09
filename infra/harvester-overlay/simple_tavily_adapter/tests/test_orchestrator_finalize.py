"""Final report contract tests for the ACP research orchestrator."""
from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager

from events import Event
from orchestrator import Orchestrator, Job, JobStatus


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
