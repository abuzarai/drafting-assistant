"""Offline-only tests: fictional configuration, no dotenv/ADC or external I/O."""

import os
import socket

import dotenv
import pytest

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["ENV"] = "production"
os.environ["INTERNAL_API_KEY"] = "test-internal-key"
os.environ["EXPRESS_INTERNAL_URL"] = "http://express.invalid"
for name in (
    "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT",
    "GCP_PROJECT_ID", "GOOGLE_GENAI_USE_VERTEXAI",
):
    os.environ.pop(name, None)
os.environ["GEMINI_API_KEY"] = "offline-fictional-key"


def forbidden(*args, **kwargs):
    raise AssertionError("Tests forbid network, dotenv discovery and provider allocation")


dotenv.load_dotenv = forbidden
dotenv.main.DotEnv.__init__ = forbidden


@pytest.fixture(autouse=True)
def offline_boundaries(monkeypatch):
    from google import genai
    import asyncpg

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(genai, "Client", forbidden)
    monkeypatch.setattr(asyncpg, "create_pool", forbidden)
