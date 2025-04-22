from rest_framework.response import Response

from api.v4.authentication import RequestAuth
from api.v4.serializers import PrimaryKeySerializer
from api.v4.utils import permission_validator
from api.v4.viewsets import BaseLoggedViewSet
from processing.data_producers.billing.meter_processing import close_meter

from .serializers import CloseMeterSerializer


class CloseMeterViewSet(BaseLoggedViewSet):
    """
    Закрытие счетичка
    """

    @permission_validator
    def partial_update(self, request, pk):
        meter = PrimaryKeySerializer.get_validated_pk(pk)
        request_auth = RequestAuth(request)
        current_provider = request_auth.get_provider()
        account = request_auth.get_account()
        binds = request_auth.get_binds()
        serializer = CloseMeterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        close_meter(
            meter=meter,
            values=serializer.validated_data['values'],
            date=serializer.validated_data['date'],
            provider_id=current_provider.pk,
            account_id=account.pk if account else None,
            change_meter_date=serializer.validated_data['date'],
            binds=binds
        )
        return Response()
