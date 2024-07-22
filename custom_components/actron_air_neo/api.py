import aiohttp
import logging
from typing import Dict, Any, List
from .const import API_URL, CMD_SET_SETTINGS

_LOGGER = logging.getLogger(__name__)

class ActronApi:
    def __init__(self, username: str, password: str, session: aiohttp.ClientSession = None):
        self.username = username
        self.password = password
        self.bearer_token = None
        self.session = session or aiohttp.ClientSession()

    async def authenticate(self):
        try:
            pairing_token = await self._request_pairing_token()
            self.bearer_token = await self._request_bearer_token(pairing_token)
        except Exception as e:
            _LOGGER.error("Authentication failed: %s", e)
            raise

    async def _request_pairing_token(self) -> str:
        url = f"{API_URL}/api/v0/client/user-devices"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "username": self.username,
            "password": self.password,
            "client": "ios",
            "deviceName": "HomeAssistant",
            "deviceUniqueIdentifier": "HomeAssistant"
        }
        _LOGGER.debug(f"Requesting pairing token from: {url}")
        response = await self._make_request(url, "POST", headers=headers, data=data, auth_required=False)
        return response["pairingToken"]

    async def _request_bearer_token(self, pairing_token: str) -> str:
        url = f"{API_URL}/api/v0/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": pairing_token,
            "client_id": "app"
        }
        _LOGGER.debug(f"Requesting bearer token from: {url}")
        response = await self._make_request(url, "POST", headers=headers, data=data, auth_required=False)
        return response["access_token"]

    async def get_devices(self) -> List[Dict[str, str]]:
        url = f"{API_URL}/api/v0/client/ac-systems?includeNeo=true"
        _LOGGER.debug(f"Fetching devices from: {url}")
        response = await self._make_request(url, "GET")
        devices = []
        if '_embedded' in response and 'ac-system' in response['_embedded']:
            for system in response['_embedded']['ac-system']:
                devices.append({
                    'serial': system.get('serial', 'Unknown'),
                    'name': system.get('description', 'Unknown Device'),
                    'type': system.get('type', 'Unknown')
                })
        _LOGGER.debug(f"Found devices: {devices}")
        return devices

    async def get_ac_status(self, serial: str) -> Dict[str, Any]:
        url = f"{API_URL}/api/v0/client/ac-systems/status/latest?serial={serial}"
        _LOGGER.debug(f"Fetching AC status from: {url}")
        return await self._make_request(url, "GET")

    async def send_command(self, serial: str, command: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{API_URL}/api/v0/client/ac-systems/cmds/send?serial={serial}"
        data = {"command": {**command, "type": CMD_SET_SETTINGS}}
        _LOGGER.debug(f"Sending command to: {url}, Command: {data}")
        return await self._make_request(url, "POST", json=data)

    async def _make_request(self, url: str, method: str, headers: Dict[str, str] = None, data: Dict[str, Any] = None, json: Dict[str, Any] = None, auth_required: bool = True) -> Dict[str, Any]:
        if auth_required and not self.bearer_token:
            raise AuthenticationError("Not authenticated")

        if headers is None:
            headers = {}
        if auth_required:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        _LOGGER.debug(f"Making {method} request to: {url}")
        try:
            async with self.session.request(method, url, headers=headers, data=data, json=json) as response:
                if response.status == 200:
                    _LOGGER.debug(f"Request successful, status code: {response.status}")
                    return await response.json()
                else:
                    text = await response.text()
                    _LOGGER.error(f"API request failed: {response.status}, {text}")
                    raise ApiError(f"API request failed: {response.status}, {text}")
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Network error during API request: {err}")
            raise ApiError(f"Network error during API request: {err}")

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

class AuthenticationError(Exception):
    """Raised when authentication fails."""

class ApiError(Exception):
    """Raised when an API call fails."""