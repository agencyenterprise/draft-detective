"""CORS for the API, with unhandled errors answered inside it."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lib.api.server_error_middleware import ServerErrorJSONMiddleware


def add_cors_middleware(app: FastAPI) -> None:
    """Add CORS, and inside it the middleware that turns an unhandled error into a JSON 500.

    `add_middleware` wraps what came before, so the error middleware goes first
    and CORS second: the 500 then carries the CORS headers like any response.
    """
    app.add_middleware(ServerErrorJSONMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Expose Tus headers, and the download filename, so frontend can read them
        expose_headers=[
            "Content-Disposition",
            "Upload-Offset",
            "Upload-Length",
            "Upload-Expires",
            "Tus-Version",
            "Tus-Resumable",
            "Tus-Extension",
            "Tus-Max-Size",
            "Location",
        ],
    )
