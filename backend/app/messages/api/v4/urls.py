from rest_framework.routers import DefaultRouter

from app.messages.api.v4.views import GetUserTaskViewSet

messages_router = DefaultRouter()
messages_router.register(
    'user/updates',
    GetUserTaskViewSet,
    basename='user_updates'
)
