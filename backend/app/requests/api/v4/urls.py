from rest_framework.routers import DefaultRouter

from app.requests.api.v4.views import (
    RequestViewSet,
    RequestCountViewSet,
    RequestCountByDaysViewSet,
    RequestCountByStatusViewSet,
    RequestBlankViewSet,
    RequestsFilesViewSet,
    RequestsSamplesViewSet,
    RequestMonitoringViewSet,
    RequestBoundCallsViewSet,
    RequestAutoSelectExecutor,
    RequestContractingProvidersViewSet,
)

requests_router = DefaultRouter()

# CRUD для Request
requests_router.register(
    'models/requests',
    RequestViewSet,
    basename='requests'
)
# CRUD для получения количество записей Request
requests_router.register(
    'models/requests_count',
    RequestCountViewSet,
    basename='requests_count'
)
requests_router.register(
    'models/requests_count_by_days',
    RequestCountByDaysViewSet,
    basename='requests_count_by_days'
)
requests_router.register(
    'models/requests_count_by_status',
    RequestCountByStatusViewSet,
    basename='requests_count_by_status'
)
# CRUD для RequestBlank
requests_router.register(
    'requests/blank/generate',
    RequestBlankViewSet,
    basename='request_blank'
)
requests_router.register(
    'models/requests/files',
    RequestsFilesViewSet,
    basename='requests_files'
)
requests_router.register(
    'models/requests_samples',
    RequestsSamplesViewSet,
    basename='requests_samples'
)
requests_router.register(
    'requests/monitoring',
    RequestMonitoringViewSet,
    basename='requests_monitoring'
)
requests_router.register(
    'requests/auto_select',
    RequestAutoSelectExecutor,
    basename='requests_auto_select_executor'
)

requests_router.register(
    'requests/bound_calls',
    RequestBoundCallsViewSet,
    basename='requests_bound_calls'
)

requests_router.register(
    'requests/contracting_providers',
    RequestContractingProvidersViewSet,
    basename='requests_contracting_providers'
)
