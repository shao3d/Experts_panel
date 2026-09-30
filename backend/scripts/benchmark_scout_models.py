#!/usr/bin/env python3
"""Paired headless Scout evaluation without reading run logs or the database.

Luna and Sol use Codex exec and the MCP adapter of the existing Scout plugin.
Runtime Sol/low/fast and Space Bunny use the sanctioned wrapper; a subprocess proxy streams events
to this evaluator in memory while preserving the wrapper's normal output.
The evaluator checks completed source reads and exact quotes, and emits the
answers for human assessment. Scores do not establish semantic entailment.
"""
from __future__ import annotations

import argparse
import json
import importlib.util
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from src.utils.scout_evidence import sources_from_output, read_evidence, tool_calls, finished
_spec = importlib.util.spec_from_file_location("scout_integrity_for_benchmark", ROOT / "backend/scripts/verify_citations.py")
_integrity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_integrity)
QUESTIONS = {
    "telegram_control": "Посмотри, что у acidcrunch написано про камеру в модели Aleph (Runway Aleph). Ищи только у acidcrunch. Если сигнала нет — скажи честно. Нужны конкретные рекомендации, ограничения и source_key.",
    "negative_control": "Какие в корпусе экспертов есть протоколы секвенирования ДНК и биоинформатические пайплайны для NGS-данных? Отвечай только по первоисточникам корпуса; если подтверждений нет, скажи это, не дополняя ответ внешними знаниями.",
    "old_craft": "Ищи только в VideoHub (expert_id=video_hub). Как Max Novak в ролике yUiTmO8AjJc использует Switchlight и Blender для relighting реальной съёмки? Нужны конкретные карты, порядок действий, ручные операции и ограничения. Проверь первоисточники; укажи source_key, автора, дату и таймкоды. Старый материал здесь уместен.",
    "exact_prompts": "Ищи только в VideoHub (expert_id=video_hub), ролик Youri van Hofwegen 2b3Z4rW5VJc — STOP Wasting Credits & Master Seedance 2.5. Какие конкретные приёмы помогают управлять камерой и движением? Приведи две короткие дословные английские цитаты или экранные формулировки, ясно различая речь автора и текст на экране. Нужны source_key и таймкоды; не сочиняй отсутствующие параметры.",
    "compare_authors": "Ищи только в VideoHub (expert_id=video_hub). Сравни, какую роль Blender играет у Max Novak в yUiTmO8AjJc и у Higgsfield AI в reFzEtCG_m8. Что именно делают до генерации, что после, где остаётся ручная работа? Нужны подтверждённые различия с указанием автора, ролика, source_key и таймкода. Не смешивай две методики в одну.",
    "scoped_video": "Ищи только в VideoHub (expert_id=video_hub), ролик Higgsfield AI OiULPvTJ-0E. Какие этапы экономии AI-кредитов представлены в доступных фрагментах? Можно ли по нашей базе уверенно восстановить первые десять минут этого ролика и весь его процесс? Отдельно укажи, какие части ты действительно прочитал, а что остаётся неизвестным. Дай source_key и таймкоды.",
    "false_premise": "Ищи только в VideoHub (expert_id=video_hub), только материалы Max Novak из yUiTmO8AjJc. Подтверди или опровергни по источникам утверждение: он советует поставить temporal_strength=0.37 и экспортировать результат Switchlight в ACEScg. Найди точные подтверждения для каждого параметра; если доказательств нет, скажи это. Не подменяй отсутствие подтверждения доказательством обратного и не используй знания вне корпуса.",
}

PROXY = r'''#!/usr/bin/env python3
import os, subprocess, sys
proc = subprocess.Popen([os.environ["SCOUT_EVAL_ENGINE_BIN"], *sys.argv[1:]], stdout=subprocess.PIPE, text=True)
for line in proc.stdout:
    sys.stdout.write(line)
    sys.stdout.flush()
    sys.stderr.write("SCOUT_EVAL_EVENT " + line)
    sys.stderr.flush()
raise SystemExit(proc.wait())
'''


from src.utils.scout_codex import codex_command


def unpack_sources(output: object) -> list[dict]:
    return sources_from_output(output)


def evaluate_events(engine: str, events: list[dict], answer: str) -> dict:
    completed_calls = tool_calls(events)
    calls = [{"tool": c["tool"], "args": c["args"], "status": c["status"],
              "output_error": not c["successful"]} for c in completed_calls]
    sources = read_evidence(events)
    keys = sorted(set(re.findall(r"\b[a-z][a-z_]{2,}:\d+\b", answer)))
    quotes = re.findall(r'[«“"]([^»”"]{25,300})[»”"]', answer)
    quote_checks = []
    for quote in quotes:
        norm = lambda s: " ".join(s.lower().replace("ё", "е").split())
        matches = [key for key, source in sources.items()
                   if norm(quote) in norm(source.get("content", ""))]
        quote_checks.append({"quote": quote, "exactly_in_read_sources": matches})
    return {
        "integrity": _integrity.assess_answer(answer, events, lookup_unread=False),
        "tool_calls": len(calls), "calls": calls,
        "read_sources": len(sources),
        "fully_read_sources": sum(s["fully_read"] for s in sources.values()),
        "citations_incompletely_read": [key for key in keys if key in sources and not sources[key]["fully_read"]],
        "cited_keys": keys,
        "citations_without_captured_show": [key for key in keys if key not in sources],
        "quote_checks": quote_checks,
        "source_cards": [{"source_key": key, "author": s.get("author_name"),
                          "video_title": s.get("video_title"), "video_link": s.get("video_link"),
                          "content_preview": s.get("content", "")[:900]}
                         for key, s in sources.items() if key in keys],
    }


def run_process(command: list[str], env: dict, timeout: float) -> subprocess.CompletedProcess:
    """Bound the whole headless process tree, including MCP and helper children."""
    with subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=True) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            return subprocess.CompletedProcess(command, 124, stdout, stderr + "\n# scout-eval-timeout\n")
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def run(engine: str, case: str, timeout: int, *, question: str | None = None) -> dict:
    question = question if question is not None else QUESTIONS[case]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=".scout-eval-", dir=ROOT) as work:
        env = dict(os.environ)
        if engine in ("luna", "sol"):
            command = codex_command(engine) + [question]
        else:
            proxy = Path(work) / "opencode-proxy"
            proxy.write_text(PROXY); proxy.chmod(0o700)
            if engine == "bunny":
                env["EXPERT_SCOUT_ENGINE"] = "bunny"
                env["SCOUT_EVAL_ENGINE_BIN"] = str(Path.home() / ".opencode/bin/opencode")
                env["OPENCODE_BIN"] = str(proxy)
            else:
                env["EXPERT_SCOUT_ENGINE"] = "sol"
                env["SCOUT_EVAL_ENGINE_BIN"] = shutil.which("codex")
                env["CODEX_BIN"] = str(proxy)
            env["EXPERT_SCOUT_TIMEOUT"] = str(timeout)
            command = ["bash", str(ROOT / "scripts/expert_scout.sh"), question]
        proc = run_process(command, env, timeout + 90)
    events = []
    event_lines = proc.stdout.splitlines() if engine in ("luna", "sol") else [
        line.removeprefix("SCOUT_EVAL_EVENT ") for line in proc.stderr.splitlines()
        if line.startswith("SCOUT_EVAL_EVENT ")]
    for line in event_lines:
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    if engine in ("luna", "sol"):
        answers = [e.get("item", {}).get("text", "") for e in events
                   if e.get("type") == "item.completed"
                   and e.get("item", {}).get("type") == "agent_message"]
        answer = answers[-1] if answers else ""
    else:
        answer = proc.stdout.strip()
    return {
        "engine": engine, "case": case, "question": question,
        "duration_seconds": round(time.monotonic() - started, 1), "exit": proc.returncode,
        "run_completed": finished(events),
        "answer": answer,
        "diagnostics": [line for line in proc.stderr.splitlines()
                        if line.startswith(("# scout-run:", "# scout-eval-timeout")) or "Error" in line][:8],
        **evaluate_events(engine, events, answer),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["luna", "sol", "bunny", "runtime"], required=True)
    parser.add_argument("--case", choices=QUESTIONS, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    result = run(args.engine, args.case, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["exit"] == 0 and result["run_completed"] and result["answer"] and result["integrity"]["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
