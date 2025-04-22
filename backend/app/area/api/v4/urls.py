from api.v4.viewsets import HandyRouter
from .views import (
    AreaConstantsViewSet, AreasOfHouseViewSet, AreasViewSet, FamilyViewSet,
    MeterExpirationConstantsViewSet, MetersUnitsConstantsViewSet,
)

area_router = HandyRouter()

# CRUD для Area
area_router.register(
    'models/areas',
    AreasViewSet,
    basename='areas'
)
area_router.register(
    'forms/area/families',
    FamilyViewSet,
    basename='forms_area_families'
)
area_router.register(
    'forms/area/constants',
    AreaConstantsViewSet,
    basename='forms_area_constants'
)
area_router.register(
    'forms/area_meter/units_constants',
    MetersUnitsConstantsViewSet,
    basename='forms_area_meter_units_constants'
)
area_router.register(
    'forms/area_meter/expiration_constants',
    MeterExpirationConstantsViewSet,
    basename='forms_area_meter_expiration_constants'
)
area_router.register(
    'forms/house_areas',
    AreasOfHouseViewSet,
    basename='t_coefficient'
)
