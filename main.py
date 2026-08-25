"""Vercel entrypoint — re-exports the FastAPI app from root app.py."""

from app import app

__all__ = ["app"]
