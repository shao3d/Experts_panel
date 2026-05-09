from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import google.auth
import requests
from fastapi import FastAPI, HTTPException, Request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

app = FastAPI(title="Vertex OpenAI Proxy", version="0.1.0")

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_DEFAULT_MODEL = os.getenv("VERTEX_DEFAULT_MODEL", "gemini-3-flash-preview")
_DEFAULT_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")
_TIMEOUT_SECONDS = int(os.getenv("VERTEX_PROXY_TIMEOUT_SECONDS", "300"))

_credentials: Any | None = None
_project_id: str | None = None
_thought_signatures_by_call_id: dict[str, str] = {}
_thought_signatures_by_name: dict[str, str] = {}


def _load_credentials() -> tuple[Any, str]:
    raw_json = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
    if raw_json:
        info = json.loads(raw_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=[_CLOUD_PLATFORM_SCOPE]
        )
        return creds, os.getenv("VERTEX_AI_PROJECT_ID") or info["project_id"]

    path = (
        os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if path:
        creds = service_account.Credentials.from_service_account_file(
            path, scopes=[_CLOUD_PLATFORM_SCOPE]
        )
        return creds, os.getenv("VERTEX_AI_PROJECT_ID") or creds.project_id

    creds, detected_project_id = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])
    project_id = os.getenv("VERTEX_AI_PROJECT_ID") or detected_project_id
    if not project_id:
        raise RuntimeError("VERTEX_AI_PROJECT_ID is not configured")
    return creds, project_id


def _get_credentials() -> tuple[Any, str]:
    global _credentials, _project_id
    if _credentials is None or _project_id is None:
        _credentials, _project_id = _load_credentials()
    if not _credentials.valid or _credentials.expired or not _credentials.token:
        _credentials.refresh(GoogleAuthRequest())
    return _credentials, _project_id


def _normalize_model(model: str | None) -> str:
    if not model:
        return _DEFAULT_MODEL
    if model.startswith("google/"):
        return model.replace("google/", "", 1)
    return model


def _location_for_model(model: str) -> str:
    return "global" if model.startswith("gemini-3") else _DEFAULT_LOCATION


def _vertex_url(model: str, project_id: str) -> str:
    location = _location_for_model(model)
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return (
        f"https://{host}/v1/projects/{project_id}/locations/{location}"
        f"/publishers/google/models/{model}:generateContent"
    )


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(str(item.get("text", "")))
                elif "text" in item:
                    chunks.append(str(item.get("text", "")))
            else:
                chunks.append(str(item))
        return "\n".join(part for part in chunks if part)
    return str(content)


def _parse_tool_response(content: Any) -> dict[str, Any]:
    text = _content_to_text(content)
    if not text:
        return {"content": ""}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"content": parsed}
    except json.JSONDecodeError:
        return {"content": text}


def _openai_messages_to_vertex(messages: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    system_parts: list[dict[str, str]] = []
    contents: list[dict[str, Any]] = []
    tool_call_names: dict[str, str] = {}
    pending_tool_response_parts: list[dict[str, Any]] = []

    def flush_tool_responses() -> None:
        if not pending_tool_response_parts:
            return
        contents.append({"role": "user", "parts": list(pending_tool_response_parts)})
        pending_tool_response_parts.clear()

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if role == "system":
            flush_tool_responses()
            text = _content_to_text(content)
            if text:
                system_parts.append({"text": text})
            continue

        if role == "tool":
            name = msg.get("name") or tool_call_names.get(msg.get("tool_call_id", ""))
            if not name:
                name = "tool_result"
            pending_tool_response_parts.append(
                {
                    "functionResponse": {
                        "name": name,
                        "response": _parse_tool_response(content),
                    }
                }
            )
            continue

        flush_tool_responses()
        parts: list[dict[str, Any]] = []
        text = _content_to_text(content)
        if text:
            parts.append({"text": text})

        for tool_call in msg.get("tool_calls") or []:
            call_id = tool_call.get("id")
            function = tool_call.get("function") or {}
            name = function.get("name")
            if call_id and name:
                tool_call_names[call_id] = name
            if name:
                raw_args = function.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {"_raw_arguments": raw_args}
                function_call_part: dict[str, Any] = {"functionCall": {"name": name, "args": args or {}}}
                thought_signature = None
                if call_id:
                    thought_signature = _thought_signatures_by_call_id.get(call_id)
                if thought_signature is None:
                    thought_signature = _thought_signatures_by_name.get(name)
                if thought_signature:
                    function_call_part["thoughtSignature"] = thought_signature
                parts.append(function_call_part)

        if not parts:
            parts.append({"text": ""})

        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": parts,
            }
        )

    flush_tool_responses()
    system_instruction = {"parts": system_parts} if system_parts else None
    return system_instruction, contents


def _sanitize_schema(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"$schema", "$id"}:
                continue
            if key == "additionalProperties" and isinstance(item, bool):
                continue
            cleaned[key] = _sanitize_schema(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_schema(item) for item in value]
    return value


def _openai_tools_to_vertex(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None

    declarations: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        fn = tool.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        declarations.append(
            {
                "name": name,
                "description": fn.get("description", ""),
                "parameters": _sanitize_schema(fn.get("parameters") or {"type": "object", "properties": {}}),
            }
        )

    if not declarations:
        return None
    return [{"functionDeclarations": declarations}]


def _generation_config(body: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "temperature": body.get("temperature", 0.7),
        "candidateCount": 1,
    }
    max_tokens = body.get("max_tokens") or body.get("max_completion_tokens")
    if max_tokens:
        config["maxOutputTokens"] = max_tokens
    if body.get("top_p") is not None:
        config["topP"] = body["top_p"]
    if body.get("top_k") is not None:
        config["topK"] = body["top_k"]
    response_format = body.get("response_format") or {}
    if response_format.get("type") == "json_object":
        config["responseMimeType"] = "application/json"
    return config


def _vertex_to_openai(vertex_response: dict[str, Any], model: str) -> dict[str, Any]:
    candidate = (vertex_response.get("candidates") or [{}])[0]
    parts = ((candidate.get("content") or {}).get("parts") or [])

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for part in parts:
        if "text" in part:
            text_parts.append(part.get("text") or "")
        if "functionCall" in part:
            fc = part["functionCall"] or {}
            name = fc.get("name") or "tool_call"
            args = fc.get("args") or {}
            call_id = f"call_{uuid.uuid4().hex[:24]}"
            thought_signature = part.get("thoughtSignature") or part.get("thought_signature")
            if thought_signature:
                _thought_signatures_by_call_id[call_id] = thought_signature
                _thought_signatures_by_name[name] = thought_signature
            tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )

    content = "".join(text_parts)
    message: dict[str, Any] = {"role": "assistant", "content": content or None}
    finish_reason = "stop"
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"

    usage = vertex_response.get("usageMetadata") or {}
    return {
        "id": f"chatcmpl_{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": vertex_response.get("modelVersion") or model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        _, project_id = _get_credentials()
        configured = True
    except Exception as exc:
        project_id = None
        configured = False
        return {"ok": False, "configured": configured, "error": str(exc)}
    return {
        "ok": True,
        "configured": configured,
        "project_id": project_id,
        "location": _DEFAULT_LOCATION,
        "default_model": _DEFAULT_MODEL,
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    model = _DEFAULT_MODEL
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "created": 0,
                "owned_by": "google-vertex-ai",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict[str, Any]:
    body = await request.json()
    if body.get("stream"):
        raise HTTPException(status_code=400, detail="Streaming is not supported by this proxy")

    model = _normalize_model(body.get("model"))
    system_instruction, contents = _openai_messages_to_vertex(body.get("messages") or [])
    if not contents:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": _generation_config(body),
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ],
    }

    if system_instruction:
        payload["systemInstruction"] = system_instruction

    vertex_tools = _openai_tools_to_vertex(body.get("tools"))
    if vertex_tools:
        payload["tools"] = vertex_tools

    credentials, project_id = _get_credentials()
    url = _vertex_url(model, project_id)
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=_TIMEOUT_SECONDS,
    )

    if not response.ok:
        try:
            error = response.json()
        except ValueError:
            error = {"error": {"message": response.text}}
        raise HTTPException(status_code=response.status_code, detail=error)

    return _vertex_to_openai(response.json(), model)
