from api.v4.viewsets import HandyRouter
from app.auth.api.v4.views import (
    ActorViewSet,
    AuthTokenPartnerApiUserViewSet,
    RegisterPartnerApiUserViewSet,
    ActivateUserViewSet,
    FirstStepActivationViewSet,
    DriveThroughAuthViewSet,
)

auth_router = HandyRouter()

auth_router.register(
    'models/actors',
    ActorViewSet,
    basename='actors'
)

auth_router.register(
    'partner_apps/register',
    RegisterPartnerApiUserViewSet,
    basename='register_external_user'
)

auth_router.register(
    'partner_apps/auth',
    AuthTokenPartnerApiUserViewSet,
    basename='external_user_auth'
)

auth_router.register(
    # prefix=r'a/activate/(?P<code>\w+)',
    prefix=r'a/activate/(?P<pk>\w+)/(?P<code>\w+)',
    viewset=ActivateUserViewSet,
    basename='activate_user'
)

auth_router.register(
    prefix=r'registration/first_step_activation',
    viewset=FirstStepActivationViewSet,
    basename='activate_tenant_first_step'
)

auth_router.register(
    'auth/drive-through',
    DriveThroughAuthViewSet,
    basename='drive-through'
)
