"""Config flow for the OpenRouter Image integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import (
    ImageModel,
    OpenRouterAuthError,
    OpenRouterClient,
    OpenRouterError,
)
from .const import (
    ASPECT_RATIOS,
    CONF_ASPECT_RATIO,
    CONF_IMAGE_SIZE,
    CONF_PROMPT_SUFFIX,
    CONF_TIMEOUT,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    IMAGE_SIZES,
    LOGGER,
    SUBENTRY_TYPE_IMAGE,
)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): TextSelector()})


class OpenRouterImageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRouter Image."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types supported by this handler."""
        return {SUBENTRY_TYPE_IMAGE: ImageSubentryFlowHandler}

    async def _async_validate(self, api_key: str) -> tuple[str | None, str | None]:
        """Return (label, error_key)."""
        client = OpenRouterClient(api_key, async_get_clientsession(self.hass))
        try:
            label = await client.async_verify_key()
        except OpenRouterAuthError:
            return None, "invalid_auth"
        except OpenRouterError:
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while validating the API key")
            return None, "unknown"
        return label, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            label, error = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=label or "OpenRouter", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _, error = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_SCHEMA, errors=errors
        )


class ImageSubentryFlowHandler(ConfigSubentryFlow):
    """Handle the flow for adding or reconfiguring an image generator."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.options: dict[str, Any] = {}
        self.models: dict[str, ImageModel] = {}

    @property
    def _is_new(self) -> bool:
        """Return whether this is a newly created subentry."""
        return self.source == SOURCE_USER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a new image generator."""
        self.options = {}
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing image generator."""
        self.options = dict(self._get_reconfigure_subentry().data)
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage the image generator configuration."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            data = {
                CONF_MODEL: user_input[CONF_MODEL],
                CONF_ASPECT_RATIO: user_input.get(
                    CONF_ASPECT_RATIO, DEFAULT_ASPECT_RATIO
                ),
                CONF_IMAGE_SIZE: user_input.get(CONF_IMAGE_SIZE, DEFAULT_IMAGE_SIZE),
                CONF_TIMEOUT: int(user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
                CONF_PROMPT_SUFFIX: user_input.get(CONF_PROMPT_SUFFIX, ""),
            }
            if self._is_new:
                title = user_input[CONF_MODEL]
                if (model := self.models.get(user_input[CONF_MODEL])) is not None:
                    title = model.name
                return self.async_create_entry(title=title, data=data)
            return self.async_update_and_abort(
                entry, self._get_reconfigure_subentry(), data=data
            )

        client: OpenRouterClient = entry.runtime_data
        try:
            models = await client.async_get_image_models()
        except OpenRouterAuthError:
            return self.async_abort(reason="invalid_auth")
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while fetching models")
            return self.async_abort(reason="unknown")

        if not models:
            return self.async_abort(reason="no_image_models")

        self.models = {model.id: model for model in models}

        model_options = [
            SelectOptionDict(value=model.id, label=f"{model.name} ({model.id})")
            for model in models
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=self.options.get(CONF_MODEL),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                            sort=True,
                        )
                    ),
                    vol.Optional(
                        CONF_ASPECT_RATIO,
                        default=self.options.get(
                            CONF_ASPECT_RATIO, DEFAULT_ASPECT_RATIO
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=ASPECT_RATIOS,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="aspect_ratio",
                        )
                    ),
                    vol.Optional(
                        CONF_IMAGE_SIZE,
                        default=self.options.get(CONF_IMAGE_SIZE, DEFAULT_IMAGE_SIZE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=IMAGE_SIZES,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="image_size",
                        )
                    ),
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=self.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=10, max=600, step=10, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_PROMPT_SUFFIX,
                        description={
                            "suggested_value": self.options.get(CONF_PROMPT_SUFFIX, "")
                        },
                    ): TextSelector(),
                }
            ),
        )
