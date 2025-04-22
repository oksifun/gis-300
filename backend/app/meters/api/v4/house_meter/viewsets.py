from rest_framework.response import Response

from api.v4.authentication import RequestAuth
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet
from api.v4.viewsets import BaseLoggedViewSet
from app.meters.models.meter import HouseMeter

from .serializers import HouseMeterCreateSerializer, HouseMeterGetSerializer, \
    HouseMeterPartialUpdateSerializer, HouseMeterNotePartialUpdateSerializer


class HouseMeterViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    slug = 'house_meters'
    serializer_classes = {
        'list': HouseMeterGetSerializer,
        'retrieve': HouseMeterGetSerializer,
        'partial_update': HouseMeterPartialUpdateSerializer,
        'create': HouseMeterCreateSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        # Документы для данной организации
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        meters = HouseMeter.objects(HouseMeter.get_binds_query(binds))
        return meters


class HouseMeterFilesViewSet(ModelFilesViewSet):
    model = HouseMeter
    slug = 'house_meters'


class HouseMeterNoteViewSet(BaseLoggedViewSet):
    """Добавление примечания к показаниям ОДПУ"""
    slug = ('house_meters', 'house_green_table', 'house_meters_data')

    def partial_update(self, request, pk):
        serializer = HouseMeterNotePartialUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period = serializer.validated_data['period']
        comment = serializer.validated_data['comment']
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        house_meters = HouseMeter.objects(
            HouseMeter.get_binds_query(binds),
            pk=pk,
            readings__period=period
        ).update_one(
            set__readings__S__comment=comment
        )
        return Response(serializer.data)
