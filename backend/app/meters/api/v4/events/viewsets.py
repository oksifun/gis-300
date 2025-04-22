from django.http.response import JsonResponse
from mongoengine import Q

from api.v4.authentication import RequestAuth
from api.v4.viewsets import BaseLoggedViewSet
from processing.models.billing.account import Account

from app.meters.models.meter_event import MeterReadingEvent
from .serializers import MeterEventsSerializer



class MeterEventsViewSet(BaseLoggedViewSet):
    slug = 'apartment_meters'

    def get_queryset(self, meter_id, provider_id):
        query = {'meter': meter_id}
        sort = '-created_at'
        events = tuple(
            MeterReadingEvent.objects(**query).order_by(sort)
        )
        # Получим ID акков и с ID организации их рабочего подразделения,
        # если есть
        creators = list({x['created_by'] for x in events if x['created_by']})
        query = (
                Q(id__in=creators)
                & (
                        Q(_type='Tenant')
                        | Q(department__provider=provider_id)
                )
        )
        fields = 'id', 'str_name'
        accounts = {
            x['_id']: x
            for x in Account.objects(query).only(*fields).as_pymongo()
        }
        for event in events:
            account = accounts.get(event.created_by)
            event.str_name = account['str_name'] if account else ''
        return events

    def retrieve(self, request, pk):
        provider_id = RequestAuth(request).get_provider_id()
        queryset = self.get_queryset(pk, provider_id)
        serializer = MeterEventsSerializer(queryset, many=True)
        return JsonResponse(data=dict(results=serializer.data))

