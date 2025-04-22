from rest_framework.routers import DefaultRouter

from app.gis.api.v4.view import (
    GisTasksConstants,
    GisQueuedViewSet,
    GisGuidViewSet,
    GisTaskViewSet,
    GisOperationViewSet,
    GisRecordViewSet,
    FullRecordViewSet,
    GisProviderNSIViewSet,
    GisCommonNsiViewSet,
    HouseProvidersViewSet,
    GisSendRequestViewSet,
    GisFetchResultViewSet, AllGisRecordViewSet, GisRecordErrorsViewSet,
)

gis_router = DefaultRouter()

gis_router.register(
    'gis/send_request',
    GisSendRequestViewSet,
    basename='gis_send_request',
)
gis_router.register(
    'gis/fetch_result',
    GisFetchResultViewSet,
    basename='gis_fetch_result',
)

gis_router.register(
    'gis/operations',
    GisOperationViewSet,
    basename='gis_operations',
)

gis_router.register(
    'gis/tasks',
    GisTaskViewSet,
    basename='gis_tasks',
)

gis_router.register(
    'gis/records',  # TODO operations
    GisRecordViewSet,
    basename='gis_records',
)

gis_router.register(
    'gis/full_records',
    FullRecordViewSet,
    basename='gis_full_records',
)

gis_router.register(
    'gis/all_records',
    AllGisRecordViewSet,
    basename='all_records',
)

gis_router.register(
    'gis/error_guids',
    GisRecordErrorsViewSet,
    basename='error_guids',
)

gis_router.register(
    'gis/guids',
    GisGuidViewSet,
    basename='gis_guids',
)

gis_router.register(
    'gis/scheduled',
    GisQueuedViewSet,
    basename='gis_scheduled',
)

gis_router.register(
    'gis/constants',
    GisTasksConstants,
    basename='gis_tasks_constants',
)

gis_router.register(
    'gis/common_nsi',
    GisCommonNsiViewSet,
    basename='gis_common_nsi',
)

gis_router.register(
    'gis/provider_nsi',
    GisProviderNSIViewSet,
    basename='gis_provider_nsi',
)

gis_router.register(
    'gis/house_providers',
    HouseProvidersViewSet,
    basename='gis_providers',
)
