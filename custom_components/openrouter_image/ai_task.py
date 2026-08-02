"""AI Task platform for OpenRouter Image."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
import struct
from typing import Any

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterImageConfigEntry
from .api import OpenRouterAuthError, OpenRouterClient, OpenRouterError
from .const import (
    CONF_ASPECT_RATIO,
    CONF_IMAGE_SIZE,
    CONF_PROMPT_SUFFIX,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_IMAGE,
)

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterImageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_IMAGE:
            continue
        async_add_entities(
            [OpenRouterImageAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenRouterImageAITaskEntity(ai_task.AITaskEntity):
    """An AI Task entity that generates images through OpenRouter."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_IMAGE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    def __init__(
        self, entry: OpenRouterImageConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self.model: str = subentry.data[CONF_MODEL]
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="OpenRouter",
            model=self.model,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _client(self) -> OpenRouterClient:
        return self.entry.runtime_data

    def _image_config(self) -> dict[str, str]:
        """Build the image_config payload, skipping 'auto' values."""
        config: dict[str, str] = {}
        aspect_ratio = self.subentry.data.get(CONF_ASPECT_RATIO)
        if aspect_ratio and aspect_ratio != "auto":
            config["aspect_ratio"] = aspect_ratio
        image_size = self.subentry.data.get(CONF_IMAGE_SIZE)
        if image_size and image_size != "auto":
            config["image_size"] = image_size
        return config

    async def _async_build_messages(
        self, task: ai_task.GenImageTask
    ) -> list[dict[str, Any]]:
        """Turn the task into an OpenRouter chat message list."""
        prompt = task.instructions
        if suffix := self.subentry.data.get(CONF_PROMPT_SUFFIX):
            prompt = f"{prompt}\n\n{suffix}"

        parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for attachment in task.attachments or []:
            if not (attachment.mime_type or "").startswith("image/"):
                raise HomeAssistantError(
                    f"Only image attachments are supported, got {attachment.mime_type}"
                )
            data_url = await self.hass.async_add_executor_job(
                _encode_file, attachment.path, attachment.mime_type
            )
            parts.append({"type": "image_url", "image_url": {"url": data_url}})

        return [{"role": "user", "content": parts}]

    async def _async_generate_image(
        self,
        task: ai_task.GenImageTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenImageTaskResult:
        """Handle an image generation task."""
        messages = await self._async_build_messages(task)
        timeout = int(self.subentry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))

        try:
            response = await self._client.async_generate_image(
                model=self.model,
                messages=messages,
                image_config=self._image_config() or None,
                timeout=timeout,
            )
        except OpenRouterAuthError as err:
            raise HomeAssistantError(
                "OpenRouter rejected the API key, please reconfigure the integration"
            ) from err
        except OpenRouterError as err:
            raise HomeAssistantError(f"Error generating image: {err}") from err

        choices = response.get("choices") or []
        if not choices:
            raise HomeAssistantError("OpenRouter returned no choices")

        message = choices[0].get("message") or {}
        images = message.get("images") or []
        text = message.get("content")
        if isinstance(text, list):
            text = " ".join(
                part.get("text", "")
                for part in text
                if isinstance(part, dict) and part.get("type") == "text"
            ).strip()

        if not images:
            detail = f": {text}" if text else ""
            raise HomeAssistantError(
                f"Model {self.model} did not return an image{detail}. "
                "Make sure the selected model supports image output"
            )

        url = ((images[0].get("image_url") or {}).get("url")) or ""
        if not url.startswith("data:"):
            raise HomeAssistantError(
                "OpenRouter returned an image reference that is not a data URL"
            )

        image_data, mime_type = _decode_data_url(url)
        width, height = _image_dimensions(image_data)

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=self.entity_id,
                content=text or "",
            )
        )

        LOGGER.debug(
            "Generated %s bytes (%s) with %s", len(image_data), mime_type, self.model
        )

        return ai_task.GenImageTaskResult(
            image_data=image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=mime_type,
            width=width,
            height=height,
            model=response.get("model") or self.model,
            revised_prompt=text or None,
        )


def _encode_file(path: Path, mime_type: str) -> str:
    """Read a file from disk and return it as a base64 data URL."""
    file_path = Path(path)
    if not file_path.exists():
        raise HomeAssistantError(f"Attachment {file_path} does not exist")
    size = file_path.stat().st_size
    if size > MAX_ATTACHMENT_BYTES:
        raise HomeAssistantError(
            f"Attachment {file_path.name} is too large ({size} bytes)"
        )
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _decode_data_url(url: str) -> tuple[bytes, str]:
    """Split a data URL into raw bytes and a MIME type."""
    try:
        header, encoded = url.split(",", 1)
    except ValueError as err:
        raise HomeAssistantError("Malformed data URL from OpenRouter") from err

    mime_type = "image/png"
    meta = header.removeprefix("data:").removesuffix(";base64")
    if meta:
        mime_type = meta.split(";")[0]

    try:
        return base64.b64decode(encoded, validate=False), mime_type
    except (binascii.Error, ValueError) as err:
        raise HomeAssistantError("Could not decode image data from OpenRouter") from err


def _image_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Best-effort width/height extraction for PNG, JPEG and WebP."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            width, height = struct.unpack(">II", data[16:24])
            return int(width), int(height)

        if data[:2] == b"\xff\xd8":
            index = 2
            while index + 9 < len(data):
                if data[index] != 0xFF:
                    index += 1
                    continue
                marker = data[index + 1]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    index += 2
                    continue
                length = struct.unpack(">H", data[index + 2 : index + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                    return int(width), int(height)
                index += 2 + length

        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X":
                width = int.from_bytes(data[24:27], "little") + 1
                height = int.from_bytes(data[27:30], "little") + 1
                return width, height
            if chunk == b"VP8L":
                bits = int.from_bytes(data[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if chunk == b"VP8 ":
                width, height = struct.unpack("<HH", data[26:30])
                return (width & 0x3FFF), (height & 0x3FFF)
    except (struct.error, IndexError, ValueError):
        LOGGER.debug("Could not determine image dimensions", exc_info=True)

    return None, None
