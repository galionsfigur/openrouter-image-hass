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
# Selector option keys must match [a-z0-9-_]+ (hassfest translation key rules),
# so ":" can't be used here. ASPECT_RATIO_API_VALUES maps them to the strings
# OpenRouter actually expects.
ASPECT_RATIOS: Final = [
    "auto",
    "1_1",
    "2_3",
    "3_2",
    "3_4",
    "4_3",
    "4_5",
    "5_4",
    "9_16",
    "16_9",
    "21_9",
]

ASPECT_RATIO_API_VALUES: Final[dict[str, str]] = {
    ratio: ratio.replace("_", ":") for ratio in ASPECT_RATIOS if ratio != "auto"
}

IMAGE_SIZES: Final = ["auto", "1k", "2k", "4k"]

IMAGE_SIZE_API_VALUES: Final[dict[str, str]] = {
    size: size.upper() for size in IMAGE_SIZES if size != "auto"
}

# Sent to OpenRouter for the leaderboards on openrouter.ai/rankings.
HTTP_REFERER: Final = "https://github.com/home-assistant/openrouter_image"
X_TITLE: Final = "Home Assistant"
