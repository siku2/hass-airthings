import dataclasses

import aiohttp

from .types import JSONObj

__all__ = ["AirthingsException", "HTTPError", "APIError"]


class AirthingsException(Exception):
    ...


@dataclasses.dataclass()
class HTTPError(AirthingsException):
    response_payload: JSONObj
    status: int
    reason: str

    def __str__(self) -> str:
        return f"{self.status}: {self.reason}"

    @classmethod
    def from_response(cls, resp: aiohttp.ClientResponse, payload: JSONObj):
        return cls(response_payload=payload,
                   status=resp.status,
                   reason=resp.reason)


@dataclasses.dataclass()
class APIError(AirthingsException):
    name: str
    description: str
    code: int

    http_error: HTTPError

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"

    @classmethod
    def from_response(cls, resp: aiohttp.ClientResponse, payload: JSONObj):
        http_error = HTTPError.from_response(resp, payload)
        try:
            name = payload["error"]
            description = payload.get("error_description", "no description")
            code = payload["error_code"]
        except KeyError:
            return http_error
        else:
            return cls(name=name,
                       description=description,
                       code=code,
                       http_error=http_error)
