"""Platform for Actron Neo sensor integration."""

import logging
from homeassistant.helpers.entity import Entity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Actron Neo sensor entities from a config entry."""
    _LOGGER.info("Setting up Actron Neo sensor platform")

    api = hass.data[DOMAIN]["api"]
    zones = hass.data[DOMAIN]["zones"]
    entities = []
    for zone in zones:
        entities.append(ActronNeoZoneTemperatureSensor(api, zone["id"], zone["name"]))
        entities.append(ActronNeoZoneHumiditySensor(api, zone["id"], zone["name"]))
        entities.append(ActronNeoZoneBatterySensor(api, zone["id"], zone["name"]))
    async_add_entities(entities, update_before_add=True)

class ActronNeoZoneTemperatureSensor(Entity):
    """Representation of an Actron Neo zone temperature sensor."""

    def __init__(self, api, zone_id, zone_name):
        """Initialize the temperature sensor entity."""
        self._api = api
        self._zone_id = zone_id
        self._name = f"Actron Neo Zone {zone_name} Temperature"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the entity."""
        try:
            status = await self._api.get_status()
            if status:
                for zone in status.get("zones", []):
                    if zone.get("zoneId") == self._zone_id:
                        self._state = zone.get("current_temperature")
                        break
        except Exception as e:
            _LOGGER.error(f"Failed to update temperature sensor for zone {self._zone_id}: {e}")

class ActronNeoZoneHumiditySensor(Entity):
    """Representation of an Actron Neo zone humidity sensor."""

    def __init__(self, api, zone_id, zone_name):
        """Initialize the humidity sensor entity."""
        self._api = api
        self._zone_id = zone_id
        self._name = f"Actron Neo Zone {zone_name} Humidity"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the entity."""
        try:
            status = await self._api.get_status()
            if status:
                for zone in status.get("zones", []):
                    if zone.get("zoneId") == self._zone_id:
                        self._state = zone.get("humidity")
                        break
        except Exception as e:
            _LOGGER.error(f"Failed to update humidity sensor for zone {self._zone_id}: {e}")

class ActronNeoZoneBatterySensor(Entity):
    """Representation of an Actron Neo zone battery sensor."""

    def __init__(self, api, zone_id, zone_name):
        """Initialize the battery sensor entity."""
        self._api = api
        self._zone_id = zone_id
        self._name = f"Actron Neo Zone {zone_name} Battery"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the entity."""
        try:
            status = await self._api.get_status()
            if status:
                for zone in status.get("zones", []):
                    if zone.get("zoneId") == self._zone_id:
                        self._state = zone.get("battery_level")
                        break
        except Exception as e:
            _LOGGER.error(f"Failed to update battery sensor for zone {self._zone_id}: {e}")
