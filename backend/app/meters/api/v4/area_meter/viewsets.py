from bson import ObjectId

from api.v4.authentication import RequestAuth
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet
from app.area.models.area import Area
from app.meters.models.meter import AreaMeter
from app.meters.models.meter_event import MeterReadingEvent

from .serializers import AreaMeterCreateSerializer, AreaMeterListSerializer, \
    AreaMeterRetrieveSerializer, AreaMeterUpdateSerializer, \
    MeterReadingEventSerializer


class AreaMeterViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    serializer_classes = {
        'list': AreaMeterListSerializer,
        'create': AreaMeterCreateSerializer,
        'partial_update': AreaMeterUpdateSerializer,
        'retrieve': AreaMeterRetrieveSerializer
    }
    slug = ('apartment_meters', 'request_log')

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        query = {'is_deleted__ne': True,}
        provider = request_auth.get_provider_id()
        if provider==ObjectId('553e5c6aeb049b001b652020'):
            query = self.check_query_for_ses(query)
        meters = AreaMeter.objects(
            AreaMeter.get_binds_query(binds),
            **query
        ).order_by('order', 'serial_number')
        return meters

    def check_query_for_ses(self, query):
        """
        Ужасный костыль для ограничения видимости счетчиков ГВС
        для двух домов в организации СЭС
        Удалить при первой же возможности
        """
        house_ids = [
            ObjectId('534cefc9f3b7d47f1d69a7d9'),
            ObjectId('52e8eb7fb6e6974167de599d'),
        ]
        area_to_compare = Area.objects(
            id=self.request.query_params.get('area__id')
        ).first()
        areas_to_except = Area.objects(
            house__id__in=house_ids
        ).as_pymongo().only('id')
        areas_to_except_ids = [area['_id'] for area in areas_to_except]
        if area_to_compare.id in areas_to_except_ids:
            query.update({'_type__0__ne': 'HotWaterAreaMeter',})
        return query

    def partial_update(self, request, *args, **kwargs):
        request.data['change_meter_date'] = None
        return super().partial_update(request, *args, **kwargs)


class AreaMeterEventsViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    http_method_names = ['get']
    serializer_class = MeterReadingEventSerializer
    slug = 'apartment_meters'

    def get_queryset(self):
        return MeterReadingEvent.objects.all()


class AreaMeterFilesViewSet(ModelFilesViewSet):
    model = AreaMeter
    slug = 'apartment_meters'
