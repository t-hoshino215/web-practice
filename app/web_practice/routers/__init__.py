from web_practice.routers.admin import router as admin_router
from web_practice.routers.auth import router as auth_router
from web_practice.routers.health import router as health_router
from web_practice.routers.messages import router as messages_router
from web_practice.routers.users import router as users_router

__all__ = [
    "admin_router",
    "auth_router",
    "health_router",
    "messages_router",
    "users_router",
]
