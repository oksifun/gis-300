from api.v4.viewsets import HandyRouter
from .viewsets import (
    HouseConstantsViewSet, HouseDetailViewSet,
    HouseFilesViewSet, HouseViewSet, PorchartViewSet
)

house_router = HandyRouter()

house_router.register(
    'forms/house/constants',
    HouseConstantsViewSet,
    basename='forms_house_constants'
)
house_router.register(
    'models/houses',
    HouseViewSet,
    basename='houses'
)
house_router.register(
    'models/house',
    HouseDetailViewSet,
    basename='house'
)
house_router.register(
    'models/porchart',
    PorchartViewSet,
    basename='porchart'
)
house_router.register(
    'models/house/files',
    HouseFilesViewSet,
    basename='house_files'
)
