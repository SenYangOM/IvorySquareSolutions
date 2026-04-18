"""L5 FastAPI stub surface.

Re-exports ``app`` so ``uvicorn mvp.api:app`` works as documented in
``mvp_build_goal.md`` §12 Phase 6. The app is constructed via
:func:`mvp.api.server.create_app` at import time; tests that want a
fresh app (e.g. to reset the registry) can import
:func:`mvp.api.server.create_app` directly.
"""

from .server import app, create_app

__all__ = ["app", "create_app"]
