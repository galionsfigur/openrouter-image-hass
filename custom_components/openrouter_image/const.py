"""Constants for the OpenRouter Image integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "openrouter_image"
LOGGER: Final = logging.getLogger(__package__)

BASE_URL: Final = "https://openrouter.ai/api/v1"

SUBENTRY_TYPE_IMAGE: Final = "image"

CONF_ASPECT_RATIO: Final = "aspect_ratio"
CONF_IMAGE_SIZE: Final = "image_size"
CONF_TIMEOUT: Final = "timeout"
CONF_PROMPT_SUFFIX: Final = "prompt_suffix"

DEFAULT_TIMEOUT: Final = 180
DEFAULT_ASPECT_RATIO: Final = "auto"
DEFAULT_IMAGE_SIZE: Final = "auto"

# "auto" means: do not send the parameter at all and let the provider decide.
ASPECT_RATIOS: Final = [
    "auto",
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
]

IMAGE_SIZES: Final = ["auto", "1K", "2K", "4K"]

# Sent to OpenRouter for the leaderboards on openrouter.ai/rankings.
HTTP_REFERER: Final = "https://github.com/home-assistant/openrouter_image"
X_TITLE: Final = "Home Assistant"
