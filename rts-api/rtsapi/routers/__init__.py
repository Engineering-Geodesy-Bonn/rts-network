from fastapi import Request
from fastapi.requests import HTTPConnection

from rtsapi.core import Core


def get_core(connection: HTTPConnection) -> Core:
    return connection.app.state.core


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
