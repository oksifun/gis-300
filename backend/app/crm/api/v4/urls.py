from api.v4.viewsets import HandyRouter
from app.crm.api.v4.views import (
    CRMMonitoring,
    CRMStatisticsViewSet,
    ProvidersActionsViewSet,
    ProviderEventViewSet,
    ProviderEventsViewSet,
    ProviderInfoViewSet,
    ProvidersListViewSet,
    ProviderStatusStatisticViewSet,
    ProvidersTasksViewSet
)

crm_router = HandyRouter()

# Список организаций
crm_router.register(
    'providers/list',
    ProvidersListViewSet,
    basename='providers_list'
)

# Запланированные действия
crm_router.register(
    'providers/tasks',
    ProvidersTasksViewSet,
    basename='providers_tasks'
)

# Совершенные действия
crm_router.register(
    'providers/actions',
    ProvidersActionsViewSet,
    basename='providers_actions'
)

# Статистика по статусам
crm_router.register(
    'providers/statistics',
    ProviderStatusStatisticViewSet,
    basename='providers_statistics'
)

# Информация об организации
crm_router.register(
    'providers/info',
    ProviderInfoViewSet,
    basename='providers_info'
)

# Журнал работы с организацией
crm_router.register(
    'provider/events',
    ProviderEventsViewSet,
    basename='provider_events'
)

# CRUD для actions и tasks
crm_router.register(
    'provider/event',
    ProviderEventViewSet,
    basename='provider_event'
)

# Мониторинг
crm_router.register(
    'providers/monitoring',
    CRMMonitoring,
    basename='providers_monitoring'
)


# Отчет по CRM
crm_router.register(
    'providers/crm_statistics',
    CRMStatisticsViewSet,
    basename='crm_statistics'
)
