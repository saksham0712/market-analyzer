"""Vercel entrypoint — re-exports the FastAPI app from web.app."""

from web.app import app

__all__ = ["app"]
