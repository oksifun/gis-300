from rest_framework.routers import DefaultRouter

from app.hcs_export.api.v4.views import ExportEmptyHcsViewSet

hcs_router = DefaultRouter()

hcs_router.register(
    'export/empty_hcs',
    ExportEmptyHcsViewSet,
    basename='export_empty_hcs'
)
