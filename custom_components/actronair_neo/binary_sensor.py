"""Support for ActronAir Neo diagnostic sensors."""
from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant.components.binary_sensor import (  # type: ignore
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.entity import EntityCategory  # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore

from .const import DOMAIN
from .coordinator import ActronDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ActronAir Neo diagnostic sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        ActronFilterStatusSensor(coordinator),
        ActronSystemStatusSensor(coordinator),
    ]
    async_add_entities(entities)


class ActronDiagnosticBase(CoordinatorEntity):
    """Base class for diagnostic entities."""

    def __init__(self, coordinator: ActronDataCoordinator, unique_suffix: str, name: str) -> None:
        """Initialize the base diagnostic entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{unique_suffix}"
        self._attr_name = name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.device_id)},
            "name": "ActronAir Neo",
            "manufacturer": "ActronAir",
            "model": self.coordinator.data["main"]["model"],
            "sw_version": self.coordinator.data["main"]["firmware_version"],
        }


class ActronFilterStatusSensor(ActronDiagnosticBase, BinarySensorEntity):
    """Binary sensor for filter status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ActronDataCoordinator) -> None:
        """Initialize the filter status sensor."""
        super().__init__(coordinator, "filter_status", "Filter Status")

    @property
    def is_on(self) -> bool:
        """Return True if filter needs cleaning."""
        return self.coordinator.data["main"].get("filter_clean_required", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "last_cleaned": "Unknown",  # Could be added if API provides this
            "recommended_cleaning_interval": "3 months",
            "status": "Needs Cleaning" if self.is_on else "Clean",
        }


class ActronSystemStatusSensor(ActronDiagnosticBase, BinarySensorEntity):
    """Binary sensor for system status."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:hvac"

    # Class constants
    UNKNOWN_VALUE: Final = "Unknown"
    YES_VALUE: Final = "Yes"
    NO_VALUE: Final = "No"
    ENABLED_VALUE: Final = "Enabled"
    DISABLED_VALUE: Final = "Disabled"
    RUNNING_VALUE: Final = "Running"
    OFF_VALUE: Final = "Off"
    ACTIVE_VALUE: Final = "Active"
    INACTIVE_VALUE: Final = "Inactive"

    def __init__(self, coordinator: ActronDataCoordinator) -> None:
        """Initialize the system status sensor."""
        super().__init__(coordinator, "system_status", "System Status")

    def _validate_status(self, status: dict[str, Any]) -> bool:
        """Validate the status data structure."""
        try:
            # Check if we have the basic data structure
            if not isinstance(status, dict):
                return False

            # Define required paths in the data structure
            required_paths = [
                ("SystemStatus_Local",),
                ("LiveAircon",),
                ("AirconSystem",),
            ]

            # Check each path exists
            for path in required_paths:
                current = status
                for key in path:
                    if not isinstance(current, dict) or key not in current:
                        _LOGGER.debug("Missing required key: %s", key)
                        return False
                    current = current.get(key, {})

            return True

        except Exception as err:
            _LOGGER.debug("Status validation failed: %s", err)
            return False

    # Formatting helper methods
    def _format_temperature(self, value: Any) -> str:
        """Format temperature value."""
        if value is None or value == self.UNKNOWN_VALUE:
            return self.UNKNOWN_VALUE
        try:
            return f"{float(value):.1f}°C"
        except (ValueError, TypeError):
            return str(value)

    def _format_percentage(self, value: Any) -> str:
        """Format percentage value."""
        if value is None or value == self.UNKNOWN_VALUE:
            return self.UNKNOWN_VALUE
        try:
            return f"{float(value):.1f}%"
        except (ValueError, TypeError):
            return str(value)

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime to human readable string."""
        if not isinstance(seconds, (int, float)) or seconds < 0:
            return self.UNKNOWN_VALUE

        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def _format_wifi_signal(self, signal: int | float | None) -> str:
        """Format WiFi signal strength."""
        if not isinstance(signal, (int, float)):
            return self.UNKNOWN_VALUE

        strength = (
            "Excellent" if signal > -50
            else "Good" if signal > -60
            else "Fair" if signal > -70
            else "Poor"
        )
        return f"{signal} dBm ({strength})"

    def _format_zones(self, zones: dict[str, Any]) -> dict[str, Any]:
        """Format zone information with improved presentation."""
        try:
            formatted_zones = {}
            for zone_name, zone_data in zones.items():
                if not isinstance(zone_data, dict):
                    continue

                # Create a formatted string for each value
                formatted_zone = {
                    "state": "Active" if zone_data.get("is_enabled", False) else "Inactive",
                    "temperature": self._format_temperature(zone_data.get("temp")),
                    "humidity": self._format_percentage(zone_data.get("humidity")),
                    "current_operation": self._get_zone_operation(zone_data)
                }

                # Add peripheral data if available
                peripheral_data = self.coordinator.get_zone_peripheral(zone_name)
                if peripheral_data:
                    battery_level = peripheral_data.get("RemainingBatteryCapacity_pc")
                    if battery_level is not None:
                        formatted_zone["status"] = {
                            "battery": self._format_percentage(battery_level),
                            "signal": peripheral_data.get("Signal_of3", self.UNKNOWN_VALUE),
                            "last_seen": peripheral_data.get("LastConnectionTime", self.UNKNOWN_VALUE),
                            "connection": peripheral_data.get("ConnectionState", self.UNKNOWN_VALUE)
                        }

                # Add to formatted zones with a cleaner name
                clean_name = zone_data.get("name", "").strip()
                formatted_zones[clean_name] = formatted_zone

            return formatted_zones

        except Exception as err:
            _LOGGER.error("Error formatting zones: %s", err)
            return {}

    def _get_zone_operation(self, zone_data: dict[str, Any]) -> str:
        """Get the current operation mode for a zone."""
        if not zone_data.get("is_enabled", False):
            return "Off"
        
        # If we have performance data for the zone, we could add more states here
        return "Running"

    # Data getter methods
    def _get_zones_status(self) -> dict[str, Any]:
        """Get status information for all zones."""
        zones = {}
        for zone_id, zone_data in self.coordinator.data.get("zones", {}).items():
            zones[zone_data["name"]] = {
                "enabled": zone_data["is_enabled"],
                "temperature": zone_data["temp"],
                "humidity": zone_data["humidity"]
            }

            peripheral_data = self.coordinator.get_zone_peripheral(zone_id)
            if peripheral_data and "RemainingBatteryCapacity_pc" in peripheral_data:
                zones[zone_data["name"]].update({
                    "battery_level": peripheral_data["RemainingBatteryCapacity_pc"],
                    "signal_strength": peripheral_data.get("Signal_of3", self.UNKNOWN_VALUE),
                    "last_connection": peripheral_data.get("LastConnectionTime", self.UNKNOWN_VALUE),
                    "connection_state": peripheral_data.get("ConnectionState", self.UNKNOWN_VALUE)
                })
        return zones

    def _get_connection_info(self, status: dict[str, Any]) -> dict[str, Any]:
        """Get connection status information."""
        system_status = status.get("SystemStatus_Local", {})
        wifi_info = system_status.get("WiFi", {})
        cloud_info = status.get("Cloud", {})

        return {
            "wifi_signal": self._format_wifi_signal(system_status.get("WifiStrength_of3")),
            "wifi_ssid": wifi_info.get("ApSSID", self.UNKNOWN_VALUE),
            "wifi_firmware": wifi_info.get("FirmwareVersion", self.UNKNOWN_VALUE),
            "connection_state": cloud_info.get("ConnectionState", self.UNKNOWN_VALUE),
            "uptime": self._format_uptime(system_status.get("Uptime_s", 0)),
            "wifi_errors": wifi_info.get("HardwareErrorCount", 0),
            "last_status_update": self.coordinator.data["raw_data"].get("lastStatusUpdate", self.UNKNOWN_VALUE)
        }

    def _get_outdoor_unit_info(self, status: dict[str, Any]) -> dict[str, Any]:
        """Get outdoor unit status information."""
        live_aircon = status.get("LiveAircon", {})
        outdoor_unit = live_aircon.get("OutdoorUnit", {})

        return {
            "coil_temperature": self._format_temperature(outdoor_unit.get("CoilTemp")),
            "ambient_temperature": self._format_temperature(
                status.get("SystemStatus_Local", {})
                .get("SensorInputs", {})
                .get("SHTC1", {})
                .get("Temperature_oC")
            ),
            "compressor_state": live_aircon.get("CompressorMode", self.UNKNOWN_VALUE),
            "compressor_power": f"{outdoor_unit.get('CompPower', 0)} W",
            "compressor_speed": f"{outdoor_unit.get('CompSpeed', 0)} RPM",
            "compressor_status": (
                self.RUNNING_VALUE if outdoor_unit.get("CompressorOn") else self.OFF_VALUE
            ),
            "valve_position": outdoor_unit.get("ReverseValvePosition", self.UNKNOWN_VALUE),
            "defrost_mode": (
                self.ACTIVE_VALUE if outdoor_unit.get("DefrostMode") else self.INACTIVE_VALUE
            )
        }

    def _get_performance_metrics(self, status: dict[str, Any]) -> dict[str, Any]:
        """Get system performance metrics."""
        live_aircon = status.get("LiveAircon", {})

        return {
            "compressor_capacity": f"{live_aircon.get('CompressorCapacity', 0)}%",
            "target_temperature": self._format_temperature(
                live_aircon.get("CompressorChasingTemperature")
            ),
            "current_temperature": self._format_temperature(
                live_aircon.get("CompressorLiveTemperature")
            ),
            "fan_pwm": f"{live_aircon.get('FanPWM', 0)}%",
            "fan_rpm": f"{live_aircon.get('FanRPM', 0)} RPM",
            "coil_inlet": self._format_temperature(live_aircon.get("CoilInlet")),
            "fan_status": (
                self.RUNNING_VALUE if live_aircon.get("AmRunningFan") else self.OFF_VALUE
            ),
            "system_status": (
                self.RUNNING_VALUE if live_aircon.get("SystemOn") else self.OFF_VALUE
            )
        }

    def _get_hardware_info(self, status: dict[str, Any]) -> dict[str, Any]:
        """Get hardware information."""
        aircon_system = status.get("AirconSystem", {})
        indoor_unit = aircon_system.get("IndoorUnit", {})
        outdoor_unit = aircon_system.get("OutdoorUnit", {})

        return {
            "model": aircon_system.get("MasterWCModel", self.UNKNOWN_VALUE),
            "indoor_unit": {
                "model": indoor_unit.get("NV_ModelNumber", self.UNKNOWN_VALUE),
                "firmware": f"v{indoor_unit.get('IndoorFW', self.UNKNOWN_VALUE)}",
                "serial": indoor_unit.get("SerialNumber", self.UNKNOWN_VALUE),
                "supported_fan_modes": indoor_unit.get("NV_SupportedFanModes", self.UNKNOWN_VALUE),
                "auto_fan": (
                    self.ENABLED_VALUE if indoor_unit.get("NV_AutoFanEnabled")
                    else self.DISABLED_VALUE
                )
            },
            "outdoor_unit": {
                "family": outdoor_unit.get("Family", self.UNKNOWN_VALUE),
                "model": outdoor_unit.get("ModelNumber", self.UNKNOWN_VALUE),
                "firmware": f"v{outdoor_unit.get('SoftwareVersion', self.UNKNOWN_VALUE)}",
                "serial": outdoor_unit.get("SerialNumber", self.UNKNOWN_VALUE)
            },
            "controller": {
                "model": aircon_system.get("MasterWCModel", self.UNKNOWN_VALUE),
                "firmware": f"v{aircon_system.get('MasterWCFirmwareVersion', self.UNKNOWN_VALUE)}",
                "serial": aircon_system.get("MasterSerial", self.UNKNOWN_VALUE)
            }
        }

    # Entity properties
    @property
    def is_on(self) -> bool:
        """Return True if system is running."""
        return self.coordinator.data["main"]["is_on"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        try:
            data = self.coordinator.data["main"]
            raw_data = self.coordinator.data["raw_data"]
            
            # Basic attributes we know we can access
            attributes = {
                # Basic system state - These are reliable
                "compressor_state": data.get("compressor_state", self.UNKNOWN_VALUE),
                "operating_mode": data.get("mode", self.UNKNOWN_VALUE),
                "fan_mode": data.get("fan_mode", self.UNKNOWN_VALUE),
                "defrosting": self.YES_VALUE if data.get("defrosting") else self.NO_VALUE,
                "quiet_mode": (
                    self.ENABLED_VALUE if data.get("quiet_mode") else self.DISABLED_VALUE
                ),
                "away_mode": (
                    self.ENABLED_VALUE if data.get("away_mode") else self.DISABLED_VALUE
                ),
                
                # Environmental conditions - These are reliable
                "indoor_temperature": self._format_temperature(data.get("indoor_temp")),
                "indoor_humidity": self._format_percentage(data.get("indoor_humidity")),
                
                # System info - These are reliable
                "filter_status": (
                    "Needs Cleaning" if data.get("filter_clean_required") else "Clean"
                ),
                "firmware_version": f"v{data.get('firmware_version', self.UNKNOWN_VALUE)}",
            }

            # Check if we have zones data
            zones = self.coordinator.data.get("zones", {})
            if zones:
                attributes["zones"] = self._format_zones(zones)

            # Try to get status data for extended diagnostics
            status = raw_data.get("lastKnownState", {}).get(
                f"<{self.coordinator.device_id.upper()}>", {}
            )

            # Only add extended diagnostics if we have valid data
            if status:
                system_status = status.get("SystemStatus_Local", {})
                if system_status:
                    attributes["connection"] = {
                        "wifi_signal": self._format_wifi_signal(system_status.get("WifiStrength_of3")),
                        "wifi_firmware": system_status.get("WiFi", {}).get("FirmwareVersion", self.UNKNOWN_VALUE),
                        "uptime": self._format_uptime(system_status.get("Uptime_s", 0)),
                    }

                live_aircon = status.get("LiveAircon", {})
                if live_aircon:
                    attributes["performance"] = {
                        "fan_status": (
                            self.RUNNING_VALUE if live_aircon.get("AmRunningFan") else self.OFF_VALUE
                        ),
                        "system_status": (
                            self.RUNNING_VALUE if live_aircon.get("SystemOn") else self.OFF_VALUE
                        )
                    }

                aircon_system = status.get("AirconSystem", {})
                if aircon_system:
                    attributes["hardware"] = {
                        "model": aircon_system.get("MasterWCModel", self.UNKNOWN_VALUE),
                        "firmware": f"v{aircon_system.get('MasterWCFirmwareVersion', self.UNKNOWN_VALUE)}"
                    }

            return attributes

        except Exception as err:
            _LOGGER.error("Error getting attributes: %s", err)
            return {
                "error": "Failed to get attributes",
                "error_details": str(err)
            }