#!/usr/bin/env python3
"""Small authenticated HTTP bridge to the existing dev-only Scout wrapper."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import time
import re
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from backend.scripts.expert_scout import MAX_SHOW_KEYS
from backend.scripts.verify_citations import extract_keys

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output/scout_web"
TERMINAL = {"completed", "partial", "error", "stopped"}


def source_link(item):
    """Build a public link from corpus metadata, never from the model's guess."""
    key = item.get("source_key", "")
    if item.get("error") or not key:
        return None
    if key.startswith("video_hub:"):
        try:
            url = urlsplit(item.get("video_url") or "")
        except ValueError:
            return None
        if url.scheme != "https" or url.username or url.password or url.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
            return None
        query = [(name, value) for name, value in parse_qsl(url.query, keep_blank_values=True)
                 if name not in {"t", "start", "time_continue"}]
        seconds = item.get("video_timestamp_s")
        label = " · ".join(str(value) for value in (item.get("author_name"), item.get("video_title")) if value) or "Видео"
        if isinstance(seconds, int) and not isinstance(seconds, bool) and seconds >= 0:
            query.append(("t", f"{seconds}s"))
            minutes, secs = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            label += f" · {hours}:{minutes:02d}:{secs:02d}" if hours else f" · {minutes}:{secs:02d}"
        return {"url": urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), "")), "label": label}
    channel = (item.get("channel_username") or "").lstrip("@")
    message_id = key.partition(":")[2]
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{3,31}", channel) or not message_id.isdigit():
        return None
    label = item.get("author_name") or f"@{channel}"
    return {"url": f"https://t.me/{channel}/{message_id}", "label": f"{label} · пост {message_id}"}


async def resolve_sources(answer):
    """Read only cited metadata through the existing read-only Scout helper."""
    keys = extract_keys(answer)
    links = {}
    env = dict(os.environ)
    env.pop("SCOUT_WEB_PASSWORD_HASH", None)
    for offset in range(0, len(keys), MAX_SHOW_KEYS):
        batch = keys[offset:offset + MAX_SHOW_KEYS]
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                str(ROOT / "backend/.venv/bin/python"), str(ROOT / "backend/scripts/expert_scout.py"),
                "show", *batch, "--json", "--comments-limit", "0", "--max-chars", "1",
                cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            output, _ = await asyncio.wait_for(process.communicate(), 15)
            if process.returncode != 0:
                continue
            for item in json.loads(output):
                if isinstance(item, dict) and item.get("source_key") in batch:
                    link = source_link(item)
                    if link:
                        links[item["source_key"]] = link
        except (OSError, ValueError, TypeError, asyncio.TimeoutError):
            # Missing metadata must not turn into an invented link or lose the answer.
            pass
        finally:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
    return links


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=6000)


def authorize(x_scout_password: str = Header(default="")):
    expected = os.environ.get("SCOUT_WEB_PASSWORD_HASH", "")
    actual = hashlib.sha256(x_scout_password.encode()).hexdigest()
    if not expected or not secrets.compare_digest(actual, expected):
        raise HTTPException(401, "Неверный пароль")


class Jobs:
    def __init__(self, directory=STATE_DIR):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.active = None
        self.process = None
        self.current = None
        self.task = None
        self.lock = asyncio.Lock()
        # A service restart must never leave a job pretending to be alive.
        for path in self.directory.glob("*.json"):
            job = json.loads(path.read_text())
            if job["status"] not in TERMINAL:
                job.update(status="error", message="Сервис перезапущен. Повтори вопрос.")
                self.save(job)

    def save(self, job):
        target = self.directory / (job["id"] + ".json")
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False))
        temporary.chmod(0o600)
        temporary.replace(target)

    def get(self, job_id):
        if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
            raise HTTPException(404, "Поиск не найден")
        path = self.directory / (job_id + ".json")
        if not path.exists():
            raise HTTPException(404, "Поиск не найден")
        return json.loads(path.read_text())

    async def start(self, question):
        question = question.strip()
        if not question:
            raise HTTPException(422, "Напиши вопрос")
        async with self.lock:
            if self.active:
                raise HTTPException(409, "Скаут уже занят. Дождись ответа или останови поиск.")
            # Keep a bounded collection of completed results, not a second database.
            paths = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime)
            for path in paths[:-19]:
                path.unlink()
            job = dict(id=secrets.token_hex(16), question=question, status="running",
                       message="Подключаю Скаута…", started_at=time.time(), answer="", elapsed=0)
            self.active = job["id"]
            self.current = job
            self.save(job)
            self.task = asyncio.create_task(self.run(job))
            return job

    async def run(self, job):
        env = dict(os.environ, CODEX_BIN=str(ROOT / "scripts/scout_web_progress.py"),
                   SCOUT_WEB_CODEX_BIN=shutil.which("codex") or "/usr/bin/codex",
                   EXPERT_SCOUT_ENGINE="sol", SCOUT_WEB_PROGRESS="1")
        # The password verifier is not an input to the agent or its tools.
        env.pop("SCOUT_WEB_PASSWORD_HASH", None)
        reader = None
        try:
            async with self.lock:
                if job["status"] == "stopped":
                    return
                self.process = await asyncio.create_subprocess_exec(
                    "bash", str(ROOT / "scripts/expert_scout.sh"), job["question"],
                    cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, start_new_session=True,
                    limit=1024 * 1024)
            async def consume_progress():
                async for raw in self.process.stderr:
                    line = raw.decode(errors="replace")
                    if line.startswith("SCOUT_PROGRESS "):
                        job["message"] = json.loads(line.removeprefix("SCOUT_PROGRESS "))
                        self.save(job)
            reader = asyncio.create_task(consume_progress())
            answer = await self.process.stdout.read()
            code = await self.process.wait()
            await reader
            job["answer"] = answer.decode(errors="replace")
            if job["status"] != "stopped" and job["answer"]:
                job["message"] = "Подготавливаю ссылки на источники…"
                self.save(job)
                job["sources"] = await resolve_sources(job["answer"])
            if job["status"] != "stopped":
                job["status"] = "completed" if code == 0 else "partial" if code in (3, 4) and job["answer"] else "error"
                job["message"] = {"completed": "Готово", "partial": "Ответ не прошёл полную проверку",
                                  "error": "Поиск не завершился. Можно повторить вопрос."}[job["status"]]
        except asyncio.CancelledError:
            raise
        except Exception:
            job.update(status="error", message="Не удалось запустить поиск. Можно повторить вопрос.")
        finally:
            if reader and not reader.done():
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
            job["elapsed"] = round(time.time() - job["started_at"])
            self.save(job)
            self.process = None
            self.active = None
            self.current = None

    async def stop(self, job_id):
        async with self.lock:
            job = self.get(job_id)
            if self.active != job_id:
                return job
            job = self.current
            job.update(status="stopped", message="Поиск остановлен")
            self.save(job)
            process, task = self.process, self.task
        if process and process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                await asyncio.wait_for(process.wait(), 5)
            except asyncio.TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
            except ProcessLookupError:
                pass
        if task:
            await task
        job = self.get(job_id)
        job.update(status="stopped", message="Поиск остановлен", answer="")
        self.save(job)
        return job


@asynccontextmanager
async def lifespan(app):
    if not os.environ.get("SCOUT_WEB_PASSWORD_HASH"):
        raise RuntimeError("SCOUT_WEB_PASSWORD_HASH must be configured")
    app.state.jobs = Jobs()
    yield
    if app.state.jobs.active:
        await app.state.jobs.stop(app.state.jobs.active)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware,
                   allow_origins=[os.environ.get("SCOUT_WEB_ORIGIN", "https://shao3d.github.io")],
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["X-Scout-Password", "Content-Type"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/jobs", dependencies=[Depends(authorize)])
async def start(question: Question):
    return await app.state.jobs.start(question.question)


@app.get("/auth", dependencies=[Depends(authorize)])
async def auth():
    return {"status": "ok"}


@app.get("/jobs/{job_id}", dependencies=[Depends(authorize)])
async def get(job_id: str):
    job = app.state.jobs.get(job_id)
    if job.get("answer") and job["status"] in TERMINAL and "sources" not in job:
        job["sources"] = await resolve_sources(job["answer"])
        app.state.jobs.save(job)
    return job


@app.delete("/jobs/{job_id}", dependencies=[Depends(authorize)])
async def stop(job_id: str):
    return await app.state.jobs.stop(job_id)
