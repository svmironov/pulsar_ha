from __future__ import annotations

import asyncio
import meterbus
import serial
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PORT, CONF_UPDATE_INTERVAL

SENSOR_TYPES = (
    SensorEntityDescription(
        key="energy",
        name="Energy",
        native_unit_of_measurement="MWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="volume",
        name="Volume",
        native_unit_of_measurement="m³",
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="flow_rate",
        name="Flow Rate",
        native_unit_of_measurement="m³/h",
        icon="mdi:water-pump",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp_in",
        name="Temperature In",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp_out",
        name="Temperature Out",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


class PulsarDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, port: str, update_interval: int) -> None:
        super().__init__(
            hass,
            logger=None,
            name="Pulsar Sensor",
            update_interval=timedelta(seconds=update_interval),
        )
        self._port = port
        self._serial = serial.Serial(port, 2400, 8, "E", 1, 0.5)

    async def _async_update_data(self):
        data = {}

        for address in ["79", "82", "22"]:
            try:
                wakeup_frame = bytes.fromhex(
                    f"68 0B 0B 68 73 FD 52 {address} 47 06 23 FF FF FF FF B0 16"
                )
                self._serial.write(wakeup_frame)
                await asyncio.sleep(0.2)

                connected = False
                for _ in range(4):
                    frame = meterbus.load(meterbus.recv_frame(self._serial, 1))
                    if isinstance(frame, meterbus.TelegramACK):
                        connected = True
                        break

                if not connected:
                    continue

                request_frame = bytes.fromhex(f"10 7B {address} FD 16")
                self._serial.write(request_frame)
                await asyncio.sleep(0.2)

                frame = meterbus.load(
                    meterbus.recv_frame(self._serial, meterbus.FRAME_DATA_LENGTH)
                )

                if frame is not None:
                    data[f"ts{address}_energy"] = round(frame.records[0].value / 1163000, 3)
                    data[f"ts{address}_volume"] = round(frame.records[2].value, 0)
                    data[f"ts{address}_flow_rate"] = round(frame.records[4].value, 3)
                    data[f"ts{address}_temp_in"] = round(frame.records[5].value, 0)
                    data[f"ts{address}_temp_out"] = round(frame.records[6].value, 0)

            except Exception as e:
                self.logger.error(f"Error read address {address}: {e}")

        return data


class PulsarSensor(SensorEntity):
    def __init__(self, coordinator: PulsarDataCoordinator, description: SensorEntityDescription, address: str) -> None:
        self.entity_description = description
        self._coordinator = coordinator
        self._address = address
        self._attr_unique_id = f"pulsar_{address}_{description.key}"
        self._attr_name = f"Pulsar {address.capitalize()} {description.name}"

    @property
    def native_value(self):
        key = f"ts{self._address}_{self.entity_description.key}"
        return self._coordinator.data.get(key)

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    port = config_entry.data.get(CONF_PORT)
    update_interval = config_entry.data.get(CONF_UPDATE_INTERVAL)

    coordinator = PulsarDataCoordinator(hass, port, update_interval)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for address in ["79", "82", "22"]:
        for description in SENSOR_TYPES:
            entities.append(PulsarSensor(coordinator, description, address))

    async_add_entities(entities)