"""Shared Vertex AI authentication helpers.

Supports service account credentials from either:
- VERTEX_AI_SERVICE_ACCOUNT_JSON
- VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH
- GOOGLE_APPLICATION_CREDENTIALS

Falls back to Application Default Credentials when available.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .. import config

logger = logging.getLogger(__name__)

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class VertexAICredentialsError(RuntimeError):
    """Raised when Vertex AI credentials are missing or invalid."""


def _load_json_credentials(raw_json: str):
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise VertexAICredentialsError(
            "VERTEX_AI_SERVICE_ACCOUNT_JSON contains invalid JSON"
        ) from exc

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=[_CLOUD_PLATFORM_SCOPE],
    )
    return credentials, info.get("project_id"), "VERTEX_AI_SERVICE_ACCOUNT_JSON"


def _load_file_credentials(path: str):
    credentials = service_account.Credentials.from_service_account_file(
        path,
        scopes=[_CLOUD_PLATFORM_SCOPE],
    )
    return credentials, credentials.project_id, path


def _load_default_credentials():
    credentials, project_id = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])
    return credentials, project_id, "application_default_credentials"


def _load_credentials() -> Tuple[Optional[Any], Optional[str], Optional[str]]:
    if config.VERTEX_AI_SERVICE_ACCOUNT_JSON:
        return _load_json_credentials(config.VERTEX_AI_SERVICE_ACCOUNT_JSON)

    credential_path = (
        config.VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH
        or config.GOOGLE_APPLICATION_CREDENTIALS_PATH
    )
    if credential_path:
        return _load_file_credentials(credential_path)

    try:
        return _load_default_credentials()
    except DefaultCredentialsError:
        return None, None, None


class VertexAIAuthManager:
    """Manages Google auth credentials and access tokens for Vertex AI."""

    def __init__(self):
        self._credentials, detected_project_id, self._source = _load_credentials()
        self._project_id = config.VERTEX_AI_PROJECT_ID or detected_project_id
        self._location = config.VERTEX_AI_LOCATION
        self._refresh_lock = asyncio.Lock()

        if self.is_configured():
            logger.info(
                "✅ Vertex AI auth configured: project=%s location=%s source=%s",
                self._project_id,
                self._location,
                self._source,
            )
        else:
            logger.error(
                "❌ Vertex AI auth is not configured. "
                "Set VERTEX_AI_SERVICE_ACCOUNT_JSON, "
                "VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH, or GOOGLE_APPLICATION_CREDENTIALS."
            )

    @property
    def project_id(self) -> str:
        if not self._project_id:
            raise VertexAICredentialsError("Vertex AI project_id is not configured")
        return self._project_id

    @property
    def location(self) -> str:
        return self._location

    def is_configured(self) -> bool:
        return bool(self._credentials and self._project_id)

    async def get_access_token(self) -> str:
        if not self._credentials:
            raise VertexAICredentialsError("Vertex AI credentials are not configured")

        async with self._refresh_lock:
            if (
                not self._credentials.valid
                or self._credentials.expired
                or not self._credentials.token
            ):
                await asyncio.to_thread(self._credentials.refresh, Request())

        if not self._credentials.token:
            raise VertexAICredentialsError("Vertex AI access token refresh failed")

        return self._credentials.token


_auth_manager: Optional[VertexAIAuthManager] = None


def get_vertex_ai_auth_manager() -> VertexAIAuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = VertexAIAuthManager()
    return _auth_manager
