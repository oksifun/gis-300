from rest_framework.routers import DefaultRouter

from app.personnel.api.v4.views import (
    AccessWorkerViewSet,
    CopyWorkerPermissionsViewSet,
    DepartmentsViewSet,
    DepartmentsPublicViewSet,
    DismissedWorkerViewSet,
    ResendPasswordMailViewSet,
    SystemDepartmentsViewSet,
    TemplateMessageViewSet,
    VcardExportSuperViewSet,
    WorkerTimerViewSet,
    WorkerSearchViewSet,
    WorkerManagementViewSet,
    WorkerViewSet,
    WorkerBaseInfoViewSet,
    WorkerTicketAccessLevelViewSet,
    WorkerServicedHousesViewSet,
    WorkersViewSet,
    WorkerFilesViewSet,
)

personnel_router = DefaultRouter()
personnel_router.register(
    'models/worker',
    WorkerViewSet,
    basename='workers'
)
personnel_router.register(
    'models/worker_base_info',
    WorkerBaseInfoViewSet,
    basename='worker_base_info'
)
personnel_router.register(
    'models/worker/change_tickets_access_level',
    WorkerTicketAccessLevelViewSet,
    basename='worker_change_tickets_access_level'
)
personnel_router.register(
    'models/worker/management',
    WorkerManagementViewSet,
    basename='worker_management'
)
personnel_router.register(
    'models/department',
    DepartmentsViewSet,
    basename='departments'
)
personnel_router.register(
    'models/departments_public',
    DepartmentsPublicViewSet,
    basename='departments_public'
)
personnel_router.register(
    'models/system_department',
    SystemDepartmentsViewSet,
    basename='system_departments'
)
personnel_router.register(
    'worker/serviced_houses',
    WorkerServicedHousesViewSet,
    basename='houses'
)

personnel_router.register(
    'models/workers',
    WorkersViewSet,
    basename='workers'
)
personnel_router.register(
    'models/workers/files',
    WorkerFilesViewSet,
    basename='workers_files'
)

personnel_router.register(
    'worker/vcards',
    VcardExportSuperViewSet,
    basename='workers/vcards'
)

personnel_router.register(
    'worker/resend_mail',
    ResendPasswordMailViewSet,
    basename='workers/resend_mail'
)

personnel_router.register(
    'worker/timer',
    WorkerTimerViewSet,
    basename='workers/timer'
)

personnel_router.register(
    'worker/dismiss_worker',
    DismissedWorkerViewSet,
    basename='workers/dismiss_worker'
)

personnel_router.register(
    'worker/access_worker',
    AccessWorkerViewSet,
    basename='workers/access_worker'
)

personnel_router.register(
    'worker/copy_permissions',
    CopyWorkerPermissionsViewSet,
    basename='workers/copy_permissions'
)

personnel_router.register(
    'worker/search_worker',
    WorkerSearchViewSet,
    basename='workers/search_Worker'
)

personnel_router.register(
    'worker/messenger',
    TemplateMessageViewSet,
    basename='workers'
)

