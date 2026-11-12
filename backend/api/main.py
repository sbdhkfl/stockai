"""Deployment entrypoint shim (ARCHITECTURE.md §2): uvicorn api.main:app."""
from fairvalue.api.app import app  # noqa: F401
