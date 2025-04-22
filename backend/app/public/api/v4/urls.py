from rest_framework.routers import DefaultRouter

from app.public.api.v4.public_test.views import PublicTestAreaViewSet, \
    PublicTestMeterViewSet
from app.public.api.v4.views import PublicPayTaskViewSet, \
    PublicQrAccountViewSet, PublicQrActionViewSet, CallStarterViewSet

dialing_router = DefaultRouter()

dialing_router.register(
    'public_qr/call_starter',
    CallStarterViewSet,
    basename="verification-call",
)

dialing_router.register(
    'public_qr/dialing',
    PublicPayTaskViewSet,
    basename="verification-call",
)

dialing_router.register(
    'public_qr/get_account',
    PublicQrAccountViewSet,
    basename="collect-accounts",
)

dialing_router.register(
    'public_qr/account_actions',
    PublicQrActionViewSet,
    basename="collect-accounts",
)

public_test_router = DefaultRouter()
public_test_router.register(
    'areas',
    PublicTestAreaViewSet,
    basename='public-test-area',
)
public_test_router.register(
    'meters',
    PublicTestMeterViewSet,
    basename='public-test-meter',
)
