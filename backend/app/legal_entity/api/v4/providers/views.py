from mongoengine import Q

from api.v4.viewsets import BaseLoggedViewSet
from app.crm.models.crm import CRM
from app.legal_entity.api.v4.providers.serializers import (
    ProvidersSearchSerializer
)
from processing.models.billing.provider.main import Provider
from processing.models.choices import ProviderTicketRate


class ProvidersSearchViewSet(BaseLoggedViewSet):
    """
    Поиск конкретной организации по ключевым словам
    """

    def list(self, request):
        serializer = ProvidersSearchSerializer(data=request.query_params)
        data = self.search_provider(**serializer.validated_data)
        return self.json_response({'data': data})

    @staticmethod
    def search_provider(**kwargs):
        """
        Поиск конкретной организации по определенным поисковым параметрам
        :param legal_form: форма организации
        :param name: Название
        :param ogrn: ОГРН
        :param inn: ИНН
        :return: list список организаций
        """
        # Разрешенные поисковые параметры
        params = 'legal_form', 'name', 'ogrn', 'inn', 'offset', 'limit'
        # Блок проверки, что переданы верные поисковые параметры,
        # нет лишних и переданы вообще
        if not any(map(lambda x: x in params, kwargs)) \
                or any(map(lambda x: x not in params, kwargs)):
            return []
        # Блок проверки того, что хотя бы один ключ не пустой
        if not any(map(lambda x: kwargs[x], kwargs)):
            return []
        query = Q(_type__ne='BankProvider')
        if 'legal_form' in kwargs.keys() and kwargs['legal_form'] != ['']:
            query &= Q(legal_form__in=kwargs['legal_form'])

        for param in kwargs:
            if param == 'legal_form':
                continue
            value = kwargs[param]
            if value:
                param = 'name__icontains' if param == 'name' else param
                if param not in ['limit', 'offset']:
                    query &= Q(**{param: value})
        fields = (
            'id',
            'str_name',
            'ogrn',
            'inn',
            'address',
            'business_types',
        )
        all_providers = tuple(
            Provider.objects(query).only(*fields).order_by('-id').as_pymongo()
        )
        # доп фильтрация по CRM, оставляем только тех у кого статус client
        provider_ids = [item['_id'] for item in all_providers]
        clients = list(CRM.objects(
            status='client', provider__id__in=provider_ids
        ).as_pymongo())
        clients = {item['provider']['_id']: item for item in clients}
        providers = list()
        for item in all_providers:
            if item['_id'] in list(clients.keys()):
                client = clients[item['_id']]
                item['sbis'] = client.get('sbis', False)
                item['managers'] = list(map(str, client.get('managers', [])))
                item['ticket_rate'] = client.get('ticket_rate',
                                                 ProviderTicketRate.LOW)
                item['crm_status'] = client['status']
                providers.append(item)
        offset = int(kwargs.get('offset', 0))
        limit = int(kwargs.get('limit', 100))
        return providers[offset: offset + limit]
