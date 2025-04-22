from app.caching.api.v4.viewsets import AccrualFilterViewSet
from api.v4.viewsets import HandyRouter


filter_router = HandyRouter()


filter_router.register(
    'forms/accounts_filter',
    AccrualFilterViewSet,
    basename='accounts_filter',
)
