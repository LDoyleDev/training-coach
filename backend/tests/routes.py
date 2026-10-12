"""Every API route of an app, for tests that check each one."""

from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts


def api_routes(app: FastAPI) -> list[tuple[str, APIRoute]]:
    """Each API route with its full path. Since FastAPI 0.142 ``app.routes`` holds included
    routers as lazy entries, not their routes, so a plain loop over it sees only ``/healthz``."""
    return [
        (context.path or "", context.original_route)
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    ]
