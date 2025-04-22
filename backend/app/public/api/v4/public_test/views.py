from mongoengine import DoesNotExist

import settings
from api.v4.universal_crud import PublicCrudViewSet
from app.area.models.area import Area
from app.meters.models.meter import AreaMeter
from app.public.api.v4.public_test.serializers import (
    PublicTestAreasSerializer,
    PublicTestMeterSerializer,
)


class PublicTestAreaViewSet(PublicCrudViewSet):
    http_method_names = ['get']
    serializer_class = PublicTestAreasSerializer

    def get_queryset(self):
        if not settings.DEVELOPMENT:
            print('+++===+++ -----------------------------------------------')
            raise DoesNotExist('Nothing found')
        return Area.objects(
            house__id='526237d1e0e34c524382c073',
            is_deleted__ne=True,
        ).order_by('order')


class PublicTestMeterViewSet(PublicCrudViewSet):
    serializer_class = PublicTestMeterSerializer

    def get_queryset(self):
        if not settings.DEVELOPMENT:
            raise DoesNotExist('Nothing found')
        return AreaMeter.objects(
            area__house__id='526237d1e0e34c524382c073',
            _type='AreaMeter',
            is_deleted__ne=True,
        )
