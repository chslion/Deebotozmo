import datetime
import logging
from typing import Union

import aiohttp
from aiohttp import ClientResponseError

from deebotozmo.commands import Command, GetCleanLogs
from deebotozmo.models import Vacuum, RequestAuth
from deebotozmo.util import sanitize_data

_LOGGER = logging.getLogger(__name__)


class EcovacsJSON:
    REQUEST_HEADERS = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)",
    }

    def __init__(
            self,
            session: aiohttp.ClientSession,
            auth: RequestAuth,
            portal_url: str,
            verify_ssl: Union[bool, str],
    ):
        self._session = session
        self._auth = auth
        self.portal_url = portal_url
        self.verify_ssl = verify_ssl

    async def send_command(self, command: Command, vacuum: Vacuum) -> dict:
        json, base_url, url_with_params = self._get_json_and_url(command, vacuum)

        _LOGGER.debug(f"Calling {base_url} with {sanitize_data(json)}")

        try:
            # todo use maybe async_timeout?
            async with self._session.post(
                    url_with_params, headers=EcovacsJSON.REQUEST_HEADERS, json=json, timeout=60, ssl=self.verify_ssl
            ) as res:
                res.raise_for_status()
                if res.status != 200:
                    _LOGGER.warning(f"Error calling API ({res.status}): {base_url}")
                    return {}

                json = await res.json()
                _LOGGER.debug(f"Got {json}")
                return json
        except ClientResponseError as err:
            if err.status == 502:
                _LOGGER.info("Error calling API (502): Unfortunately the ecovacs api is unreliable. "
                             f"URL was: {base_url}")
            else:
                _LOGGER.warning(f"Error calling API ({err.status}): {base_url}")

        return {}

    def _get_json_and_url(self, command: Command, vacuum: Vacuum) -> (dict, str, str):
        json = {"auth": self._auth}
        base_url = self.portal_url
        params = "?"

        if command.name == GetCleanLogs().name:
            json.update({
                "td": command.name,
                "did": vacuum.did,
                "resource": vacuum.resource,
            })

            base_url += f"/lg/log.do"
        else:
            payload = {
                "header": {
                    "pri": "1",
                    "ts": datetime.datetime.now().timestamp(),
                    "tzm": 480,
                    "ver": "0.0.50"
                }
            }

            if len(command.args) > 0:
                payload["body"] = {
                    "data": command.args
                }

            json.update({
                "cmdName": command.name,
                "payload": payload,
                "payloadType": "j",
                "td": "q",
                "toId": vacuum.did,
                "toRes": vacuum.resource,
                "toType": vacuum.get_class,
            })

            base_url += f"/iot/devmanager.do"
            params += "mid={json['toType']}&did={json['toId']}&"

        params += f"td={json.get('td')}&u={json['auth']['userid']}&cv=1.67.3&t=a&av=1.3.1"
        return json, base_url, base_url + params
