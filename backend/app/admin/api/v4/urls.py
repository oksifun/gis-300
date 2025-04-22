from rest_framework.routers import DefaultRouter

from app.admin.api.v4.views import DataRestoreView, DataRestoreConstantsView, \
    SberAutoPayersView

admin_router = DefaultRouter()
admin_router.register(
    'data_restore/restore',
    DataRestoreView,
    basename='data_restore_restore'
)
admin_router.register(
    'data_restore/constants',
    DataRestoreConstantsView,
    basename='data_restore_constants'
)
admin_router.register(
    'admin/sber_autopayers',
    SberAutoPayersView,
    basename='sber_auto_payers'
)
