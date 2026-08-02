"""The OpenRouter Image integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenRouterAuthError, OpenRouterClient, OpenRouterError

PLATFORMS: list[Platform] = [Platform.AI_TASK]

OpenRouterImageConfigEntry = ConfigEntry[OpenRouterClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenRouterImageConfigEntry
) -> bool:
    """Set up OpenRouter Image from a config entry."""
    client = OpenRouterClient(
        entry.data[CONF_API_KEY], async_get_clientsession(hass)
    )

    try:
        await client.async_verify_key()
    except OpenRouterAuthError as err:
        raise ConfigEntryAuthFailed("Invalid OpenRouter API key") from err
    except OpenRouterError as err:
        raise ConfigEntryNotReady(f"Could not reach OpenRouter: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: OpenRouterImageConfigEntry
) -> None:
    """Reload the entry when its options or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenRouterImageConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
