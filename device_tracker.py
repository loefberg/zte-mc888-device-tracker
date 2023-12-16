"""Support for ZTE MC888 routers."""
from __future__ import annotations

from http import HTTPStatus
import json
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> ZTEDeviceScanner:
    """Validate the configuration and returns a ZTE scanner."""
    return ZTEDeviceScanner(config[DOMAIN])


class ZTEDeviceScanner(DeviceScanner):
    """Class which queries a wireless router from ZTE."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]

        self.req = requests.Request(
            "GET",
            "http://{}/goform/goform_get_cmd_process?isTest=false&cmd=station_list".format(host),
            headers={"Referer": "http://{}/".format(host)}
        ).prepare()

        self.last_results = {}

        self.success_init = self._update_zte_info()

    # inherited
    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_zte_info()

        return list(self.last_results.keys())

    # inherited
    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        return self.last_results.get(device, None)

    def _update_zte_info(self):
        """Ensure the information from the router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Scanning")

        try:
            response = requests.Session().send(self.req, timeout=60)

            # Calling and parsing the Tomato api here. We only need the
            # wldev and dhcpd_lease values.
            if response.status_code == HTTPStatus.OK:
                try:
                    root = json.loads(response.text)
                    self.last_results = { entry["mac_addr"]: entry["hostname"] for entry in root["station_list"] }
                    return True
                except ValueError:
                    _LOGGER.exception("Failed to parse response from router: " + response.text)
                    return False

            if response.status_code == HTTPStatus.UNAUTHORIZED:
                # Authentication error
                _LOGGER.exception(
                    "Failed to authenticate, not yet implemented"
                )
                return False

        except requests.exceptions.ConnectionError:
            # We get this if we could not connect to the router 
            _LOGGER.exception(
                "Failed to connect to the router"
            )
            return False

        except requests.exceptions.Timeout:
            # We get this if we could not connect to the router 
            _LOGGER.exception("Connection to the router timed out")
            return False

