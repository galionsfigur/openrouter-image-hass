"""Minimal async client for the OpenRouter REST API.

Only the few endpoints needed for image generation are implemented, so the
integration stays free of third-party requirements.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import BASE_URL, HTTP_REFERER, LOGGER, X_TITLE


class OpenRouterError(Exception):
    """Base error for the OpenRouter API."""


class OpenRouterAuthError(OpenRouterError):
    """Raised when the API key is rejected."""


class OpenRouterConnectionError(OpenRouterError):
    """Raised when OpenRouter cannot be reached."""


@dataclass(frozen=True, slots=True)
class ImageModel:
    """An OpenRouter model that can return images."""

    id: str
    name: str


class OpenRouterClient:
    """Thin wrapper around the OpenRouter HTTP API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._api_key = api_key
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": HTTP_REFERER,
            "X-Title": X_TITLE,
        }

    async def _request(
        self, method: str, path: str, *, json: Any = None, timeout: int = 30
    ) -> dict[str, Any]:
        """Perform a request and return the decoded JSON body."""
        try:
            response = await self._session.request(
                method,
                f"{BASE_URL}{path}",
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=timeout),
            )
        except TimeoutError as err:
            raise OpenRouterConnectionError(
                f"Timeout after {timeout}s while talking to OpenRouter"
            ) from err
        except aiohttp.ClientError as err:
            raise OpenRouterConnectionError(f"Error talking to OpenRouter: {err}") from err

        if response.status in (401, 403):
            raise OpenRouterAuthError("OpenRouter rejected the API key")

        try:
            body = await response.json(content_type=None)
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError) as err:
            raise OpenRouterError("OpenRouter returned a non-JSON response") from err

        if response.status >= 400 or (isinstance(body, dict) and body.get("error")):
            message = "unknown error"
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict):
                    message = str(error.get("message", error))
                elif error is not None:
                    message = str(error)
            raise OpenRouterError(f"OpenRouter error ({response.status}): {message}")

        if not isinstance(body, dict):
            raise OpenRouterError("Unexpected response from OpenRouter")

        return body

    async def async_verify_key(self) -> str:
        """Validate the API key and return a label for the config entry."""
        body = await self._request("GET", "/key")
        data = body.get("data") or {}
        label = data.get("label")
        return str(label) if label else "OpenRouter"

    async def async_get_image_models(self) -> list[ImageModel]:
        """Return all models that can produce images as output."""
        body = await self._request("GET", "/models")
        models: list[ImageModel] = []
        for raw in body.get("data") or []:
            if not isinstance(raw, dict):
                continue
            architecture = raw.get("architecture") or {}
            modalities = architecture.get("output_modalities") or []
            if "image" not in modalities:
                continue
            model_id = raw.get("id")
            if not model_id:
                continue
            models.append(ImageModel(id=str(model_id), name=str(raw.get("name") or model_id)))
        models.sort(key=lambda model: model.name.lower())
        LOGGER.debug("Found %s image capable models", len(models))
        return models

    async def async_generate_image(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        image_config: dict[str, str] | None = None,
        timeout: int = 180,
    ) -> dict[str, Any]:
        """Call chat/completions asking for an image back."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "modalities": ["image", "text"],
            "stream": False,
        }
        if image_config:
            payload["image_config"] = image_config

        return await self._request(
            "POST", "/chat/completions", json=payload, timeout=timeout
        )
