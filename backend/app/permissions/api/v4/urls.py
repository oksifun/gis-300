from rest_framework.routers import DefaultRouter

from app.permissions.api.v4.views import TabAvailableViewSet

permission_router = DefaultRouter()

permission_router.register(
    'tabs/available',
    TabAvailableViewSet,
    basename='tabs_available'
)