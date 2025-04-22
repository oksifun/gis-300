from api.v4.viewsets import HandyRouter
from app.tenants.api.v4.viewsets import (
    TenantCoefficientViewSet,
    TenantCoefficientImportViewSet, TenantCoefficientsViewSet
)

tenant_router = HandyRouter()

tenant_router.register(
    'forms/tenant/coefficient',
    TenantCoefficientViewSet,
    basename='t_coefficient'
)
tenant_router.register(
    'forms/tenant/coefficients',
    TenantCoefficientsViewSet,
    basename='tenant_coefficients'
)
tenant_router.register(
    'forms/tenant/coefficient_import',
    TenantCoefficientImportViewSet,
    basename='t_coefficient_import'
)
