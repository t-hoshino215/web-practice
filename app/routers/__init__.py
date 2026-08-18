from routers.auth import router as auth_router
from routers.health import router as health_router
from routers.messages import router as messages_router
from routers.users import router as users_router

__all__ = [
    "auth_router",
    "health_router",
    "messages_router",
    "users_router",
]
