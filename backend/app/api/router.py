from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.auth import router as auth_router
from app.api.routes.files import router as files_router
from app.api.routes.health import router as health_router
from app.api.routes.meetings import router as meetings_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.quality import router as quality_router
from app.api.routes.teams import invitation_router
from app.api.routes.teams import router as teams_router
from app.api.routes.workers import router as workers_router
from app.core.settings import get_settings

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(workers_router, prefix=get_settings().api_v1_prefix, tags=["workers"])
protected_router = APIRouter(prefix=get_settings().api_v1_prefix)
protected_router.include_router(organizations_router, tags=["organizations"])
protected_router.include_router(auth_router, tags=["auth"])
protected_router.include_router(teams_router, tags=["teams"])
protected_router.include_router(invitation_router, tags=["invitations"])
protected_router.include_router(meetings_router, tags=["meetings"])
protected_router.include_router(files_router, tags=["files"])
protected_router.include_router(analysis_router, tags=["analysis"])
protected_router.include_router(quality_router, tags=["quality"])
api_router.include_router(protected_router)
