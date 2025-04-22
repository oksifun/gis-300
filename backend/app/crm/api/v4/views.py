from collections import defaultdict
from datetime import datetime
from functools import reduce
import operator

from bson import ObjectId
from dateutil.relativedelta import relativedelta
from django.http.response import JsonResponse, Http404, HttpResponseNotFound
from mongoengine import Q
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from api.v4.authentication import RequestAuth
from api.v4.permissions import SuperUserOnly
from api.v4.serializers import CustomJsonEncoder, json_serializer
from api.v4.viewsets import BaseLoggedViewSet
from api.v4.universal_crud import BaseCrudViewSet
from app.crm.models.crm import (
    CRM, CRMEvent, CRM_STATUS_CHOICE, EVENT_TYPE, EventResult
)
from app.personnel.models.personnel import Worker
from app.requests.models.request import Request, Ticket
from lib.dates import start_of_day, end_of_day
from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.provider.main import Provider
from processing.models.tasks.base import Task
from app.accruals.models.accrual_document import AccrualDoc

from .serializers import (
    CRMActionsSerializer,
    CRMCustomSerializer,
    CRMEventCreateSerializer,
    CRMEventListSerializer,
    CRMEventSerializer,
    CRMIdSerializer,
    CRMProviderSerializer,
    CRMTasksSerializer,
    MonitoringSerializer,
)

DEPARTMENTS_ORDER = {
    # АДМИНИСТРАЦИЯ
    ObjectId("526236c6e0e34c474382367f"): 1,
    # 1 ОТДЕЛ: РАЗРАБОТКА АПК "Система С-300"
    ObjectId("526236c7e0e34c47438236bd"): 2,
    # 2 ОТДЕЛ: ТЕХНИЧЕСКАЯ ПОДДЕРЖКА, СОГЛАСОВАНИЕ И ВНЕДРЕНИЕ
    ObjectId("5276c324b6e69716614738ed"): 3,
    # 3 ОТДЕЛ: ПРОДВИЖЕНИЕ И ПРОДАЖИ
    ObjectId("5276c331b6e6971603b32228"): 4,
    # 4 ОТДЕЛ: РАСЧЕТЫ
    ObjectId("52dfeb24b6e69777254c944a"): 5,
    # Региональное обособленное подразделение
    ObjectId("5a5737c4c57bd5002f029163"): 6,
    # Контактный центр
    ObjectId("5e68963a6f22fe00136741d9"): 7,
    # БУХГАЛТЕРИЯ
    ObjectId("5eec6cf41600970014528fee"): 8,
}


class CRMBaseViewSet(BaseLoggedViewSet, LimitOffsetPagination):
    """
    Базовый ViewSet для работы с CRM
    """
    WORKER_FIELDS: set = {
        'last_name',
        'first_name',
        'patronymic_name',
        'phones__code',
        'phones__number',
        'email',
    }
    WORKER_AND_PROVIDER_FIELDS: set = {
        'phones__code',
        'phones__number',
        'email',
    }
    ADDRESS_FIELDS: dict = {
        'fias_street_guid': 'fias_addrobjs__in',
        'fias_house_guid': 'fias_house_guid',
    }
    ADDRESS_FIELDS_SEARCH_CHAIN: set = {
        'provider__address__real__',
        'provider__address__postal__',
        'provider__address__correspondence__',
    }
    CRM_FIELDS: set = {
        'status__in',
        'managers__in',
        'sbis',
        'services__in',
        'signs__in',
        'ticket_rate__in'
    }
    EVENT_CRM_FIELDS: set = {
        'status__in',
        'managers__in',
        'provider__legal_form__in',
        'provider__business_types__in',
        'provider__receipt_type__in',
        'provider__calc_software__in',
    }
    EVENT_ACC_FIELDS: set = {
        'account__id__in',
    }

    def custom_filter(self, params):

        query_filter = Q()
        for p, val in params.items():
            if p.rstrip('__icontains') in self.WORKER_FIELDS:
                param = p.rstrip('__icontains').replace('__', '.')
                raw_query = {'$or': [
                    {'provider.chief.{}'.format(param): {
                        '$regex': val, '$options': 'i'}},
                    {'provider.accountant.{}'.format(param): {
                        '$regex': val, '$options': 'i'}}
                ]}
                q = Q(__raw__=raw_query)
                if (
                        p.rstrip('__icontains')
                        in self.WORKER_AND_PROVIDER_FIELDS
                ):
                    q |= Q(**{'provider__{}'.format(p): val})
            # fias_street_guid - это улица с городом
            # в fias_addobjs город и улица (fias_street_guid)
            # поэтому по конкретному дому отдельно искать надо
            elif p in self.ADDRESS_FIELDS:
                q = Q()
                for chain_item in self.ADDRESS_FIELDS_SEARCH_CHAIN:
                    q |= (
                        Q(**{
                            f'{chain_item}{self.ADDRESS_FIELDS[p]}': val
                        })
                    )
            elif p in self.CRM_FIELDS:
                q = Q(**{p: val})
            elif p == 'provider__str_name__in':
                q = reduce(operator.or_,
                           (Q(provider__str_name__icontains=x) for x in val))
            else:
                q = Q(**{p: val})
            if q:
                query_filter &= q

        return query_filter

    def split_params(self, params) -> (dict, dict):

        events_params = {}
        general_params = {}

        for k, v in params.items():
            if 'tasks' in k or 'actions' in k or k == 'account__id__in':
                events_params[k] = v
            else:
                general_params[k] = v

        return general_params, events_params

    def get_events_filter(self, events_params, prefix) -> Q:
        """
        Выбор действий ограничим годом, если в фильтре не передано иное
        """
        match = Q()
        now = datetime.now()
        if prefix == 'actions':
            date_from = events_params.get(
                f'{prefix}__date_from',
                now - relativedelta(years=1),
            )
            date_till = events_params.get(f'{prefix}__date_till', now)
        else:  # tasks
            date_from = events_params.get(f'{prefix}__date_from',
                                          start_of_day(now))
            date_till = events_params.get(
                f'{prefix}__date_till',
                now + relativedelta(years=1),
            )
        if date_from:
            match &= Q(date__gte=date_from)
        if date_till:
            match &= Q(date__lte=end_of_day(date_till))
        if events_params.get(f'{prefix}__event_type__in'):
            match &= Q(
                event_type__in=events_params[f'{prefix}__event_type__in'],
            )
        for p, val in events_params.items():
            q = None
            if p in self.ADDRESS_FIELDS:
                q = Q()
                for chain_item in self.ADDRESS_FIELDS_SEARCH_CHAIN:
                    q |= (
                        Q(**{
                            f'crm__{chain_item}{self.ADDRESS_FIELDS[p]}': val
                        })
                    )
            elif p in self.EVENT_CRM_FIELDS:
                q = Q(**{f'crm__{p}': val})
            elif p in self.EVENT_ACC_FIELDS:
                q = Q(**{p: val})

            if q:
                match &= q
        return match

    def get_queryset(self, params):

        provider_id = RequestAuth(self.request).get_provider_id()
        general_params, events_params = self.split_params(params)
        queryset = CRM.objects(
            self.custom_filter(general_params),
            owner=provider_id,
        )

        event_filters = Q()
        if events_params:
            for prefix in ['actions', 'tasks']:  # TODO SupportTicket
                for k, v in events_params.items():
                    if prefix in k:
                        event_filters |= (
                                self.get_events_filter(events_params, prefix)
                                & Q(_type=prefix.title()[:-1])  # Action без s
                        )
            if event_filters:
                crm_ids = CRMEvent.objects(
                    Q(crm__owner=provider_id) & event_filters
                ).distinct('crm._id')
                if crm_ids:
                    queryset = queryset.filter(pk__in=crm_ids)

        return queryset


class BaseEventsViewSet(CRMBaseViewSet):
    """
    Базовый ViewSet для работы с совершенными/запланированными действиями
    """
    EVENT_TYPE = None
    EVENT_ORDER = None
    http_method_names = ['get']
    permission_classes = (SuperUserOnly,)
    serializer_class = None
    slug = 'providers'

    NOT_DENORMALIZED_FIELDS = [
        'sbis',
        'services__in',
        'signs__in',
        'ticket_rate__in',
        'provider__str_name__in',
        'email__icontains',
        'phones__code__icontains',
        'phones__number__icontains',
        'provider__receipt_type__in',
        'provider__calc_software__in',
        'provider__terminal__in',
        'first_name__icontains',
        'last_name__icontains',
        'patronymic_name__icontains',
    ]

    def split_params(self, params):
        events_params = {}
        general_params = {}

        for k, v in params.items():
            if k in self.NOT_DENORMALIZED_FIELDS:
                general_params[k] = v
            else:
                events_params[k] = v
        return general_params, events_params

    def get_type_keys(self):
        types = {
            'Action': 'actions',
            'Task': 'tasks',
        }
        return types[self.EVENT_TYPE]

    def get_queryset(self, params):
        """
        Получаем идентификаторы CRM для формирования запроса событий
        """
        prefix = self.get_type_keys()
        provider_id = RequestAuth(self.request).get_provider_id()
        general_params, events_params = self.split_params(params)
        crm_ids: list = []
        if general_params:
            custom_filter = self.custom_filter(general_params)
            general_queryset = CRM.objects(
                owner=provider_id).filter(custom_filter)
            crm_ids = [item.id for item in general_queryset]
        q = Q(
            crm__owner=provider_id,
            _type=self.EVENT_TYPE,
        )
        if crm_ids:
            q &= Q(crm__id__in=crm_ids)
        events_filter = self.get_events_filter(events_params, prefix)
        if events_filter:
            q &= events_filter
        pipeline = [
            {
                '$lookup': {
                    'from': 'Provider',
                    'localField': 'crm.provider._id',
                    'foreignField': '_id',
                    'as': 'provider_info',
                }
            },
            {'$unwind': '$provider_info'},
            {
                '$addFields': {
                    'provider': {
                        'str_name': '$provider_info.str_name',
                        'address': '$provider_info.address',
                    }
                }
            },
            {
                '$project': {
                    'provider_info': 0
                }
            },
            {'$sort': self.EVENT_ORDER}
        ]
        return CRMEvent.objects(q).aggregate(
            *pipeline, allowDiskUse=True
        )

    @staticmethod
    def add_workers_info(data):
        worker_ids = list()
        for item in data:
            if item.get('contact_persons'):
                worker_ids.extend(item['contact_persons'])
        workers = {
            item.id: {'_id': item.id, 'str_name': item.str_name}
            for item in Worker.objects(id__in=worker_ids)
        }
        for item in data:
            c_list = list()
            if item.get('contact_persons'):
                for p in item['contact_persons']:
                    if workers.get(p):
                        c_list.append(workers[p])
                item['contact_persons'] = c_list

    @staticmethod
    def get_statistics(data):
        statuses = [x[0] for x in CRM_STATUS_CHOICE]
        stat = {x: {t[0]: 0 for t in EVENT_TYPE} for x in statuses}
        for item in data:
            r_item = stat[item['status']]
            r_item[item['event_type']] += 1
        return {'count': len(data), 'statistics': [stat]}

    def list(self, request, *args, **kwargs):

        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        data = list(self.get_queryset(serializer.validated_data))
        self.add_workers_info(data)
        results = self.paginate_queryset(data, request)  # допускается list
        response = self.get_paginated_response(
            CustomJsonEncoder.perform_encode(results))
        response.data['meta'] = self.get_statistics(data)

        return response


class ProvidersActionsViewSet(BaseEventsViewSet):
    """
    Страница "Совершенные действия"
    """
    EVENT_TYPE = 'Action'
    EVENT_ORDER = {'date': -1}
    serializer_class = CRMActionsSerializer


class ProvidersTasksViewSet(BaseEventsViewSet):
    """
    Страница "Запланированные действия"
    """
    EVENT_TYPE = 'Task'
    EVENT_ORDER = {'date': 1}
    serializer_class = CRMTasksSerializer


class ProviderStatusStatisticViewSet(CRMBaseViewSet):
    """
    Страница "Статистика по статусам"
    """
    http_method_names = ['get']
    permission_classes = (SuperUserOnly,)
    serializer_class = CRMCustomSerializer
    slug = 'providers'

    @staticmethod
    def get_stat(queryset):
        pipeline = [{'$group': {'_id': '$status', 'count': {'$sum': 1}}}]
        result = queryset.aggregate(*pipeline)
        return [dict(count=x['count'], status=x['_id']) for x in result]

    def list(self, request):
        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        queryset = self.get_queryset(serializer.validated_data)
        data = self.get_stat(queryset)
        return JsonResponse({'data': data},
                            json_dumps_params={'default': json_serializer})


class ProvidersListViewSet(CRMBaseViewSet):
    """
    Страница список организаций
    """
    http_method_names = ['get']
    permission_classes = (SuperUserOnly,)
    serializer_class = CRMCustomSerializer
    slug = 'providers'

    def list(self, request):
        params = self.serializer_class(data=request.query_params)
        params.is_valid(raise_exception=True)
        queryset = self.get_queryset(params.validated_data)
        results = self.paginate_queryset(queryset, request)
        serializer = CRMProviderSerializer(results, many=True)
        response = self.get_paginated_response(serializer.data)
        return response


class ProviderInfoViewSet(BaseCrudViewSet):
    """
    Информация об организации для карточки организации
    """
    http_method_names = ['get', 'patch']
    permission_classes = (SuperUserOnly,)
    slug = 'providers'
    serializer_class = CRMProviderSerializer
    lookup_field = 'provider__id'

    def get_queryset(self):
        provider_id = RequestAuth(self.request).get_provider_id()
        return CRM.objects(
            owner=provider_id,
        )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Http404:
            provider = Provider.objects(pk=kwargs['provider__id']).first()
            if not provider:
                return HttpResponseNotFound()
            owner = RequestAuth(self.request).get_provider_id()
            instance = CRM.get_or_create(provider, owner_id=owner)
        serializer = self.get_serializer(instance)
        return Response(self._process_results(serializer, request))


class ProviderEventsViewSet(BaseCrudViewSet):
    """
    Журнал работы с организацией в карточке организации
    """
    permission_classes = (SuperUserOnly,)
    http_method_names = ['get']
    serializer_classes = {
        'list': CRMIdSerializer,
    }
    slug = 'providers'

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        return CRMEvent.objects

    def list(self, request, *args, **kwargs):
        """
        Список совершенных/запланированных действий по организации
        в обратном порядке по полю date
        """
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        crm_id = serializer.validated_data['crm_id']
        queryset = self.get_queryset().filter(
            crm__id=crm_id
        ).exclude('crm').order_by('-date')
        results = self.paginate_queryset(queryset)
        events = CRMEventListSerializer(results, many=True)
        return self.get_paginated_response(events.data)


class ProviderEventViewSet(BaseCrudViewSet):
    """
    Работа с одним событием по организации
    """
    permission_classes = (SuperUserOnly,)
    http_method_names = ['post', 'patch', 'delete']
    serializer_classes = {
        'create': CRMEventCreateSerializer,
        'retrieve': CRMEventSerializer,
        'partial_update': CRMEventSerializer,
    }
    slug = 'providers'

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        provider_id = RequestAuth(self.request).get_provider_id()
        return CRMEvent.objects(
            crm__owner=provider_id,
            _type__in=['Action', 'Task'],
        )


class CRMMonitoring(CRMBaseViewSet):
    """
    Страница Мониторинг
    """
    http_method_names = ['get']
    permission_classes = (SuperUserOnly,)
    serializer_class = CRMCustomSerializer
    slug = 'providers'

    @staticmethod
    def get_registry_statuses(providers):
        # не будем учитывать даные старше года
        date = start_of_day(datetime.now()) - relativedelta(years=1)
        # для каждой организации определить количество документов по месяцам
        query = [{'$match': {
            'sector_binds.provider': {'$in': providers},
            'date_from': {'$gte': date},
            'status': {'$in': CONDUCTED_STATUSES},
        }},
            {'$project': {
                'sector_binds.provider': 1,
                'date_from': 1,
                'sent_registries.date': 1,
            }},
            {'$unwind': '$sector_binds'},
            {'$group': {
                '_id': {
                    'provider': '$sector_binds.provider',
                    'month': '$date_from',
                },
                'count': {'$sum': 1},
                'sent_date': {'$max': '$sent_registries.date'}
            }},
            {'$group': {
                '_id': '$_id.provider',
                'months': {'$push': {
                    'month': '$_id.month',
                    'count': '$count',
                    'sent_date': '$sent_date',
                }}
            }}]
        months = AccrualDoc.objects.aggregate(*query)
        # для каждой организации оставляем два последних месяца
        result = {}
        for m in months:
            p_data = sorted(
                m['months'],
                key=lambda i: i['month'],
                reverse=True
            )[0: 2]
            if not p_data:
                result[m['_id']] = None
            elif len(p_data) == 1:
                result[m['_id']] = p_data[0]['sent_date']
            elif p_data[0]['count'] >= p_data[1]['count']:
                result[m['_id']] = p_data[0]['sent_date']
            else:
                result[m['_id']] = p_data[1]['sent_date']
        return result

    @staticmethod
    def get_gis_statuses(providers):
        a_pipeline = [
            {'$match': {
                'provider': {'$in': providers},
                'status': 'done',
                '_cls': 'Task.ZipSiblingsFilesTask',
            }},
            {'$project': {
                'provider': 1,
                'created': 1,
            }},
            {'$group': {
                '_id': '$provider',
                'date': {'$max': '$created'},
            }},
        ]
        gis = list(Task.objects.aggregate(*a_pipeline))
        return {g['_id']: g['date'] for g in gis}

    @staticmethod
    def get_module_stat(providers, model, on_date, provider_name=None,
                        dt_name=None, match_query=None, last_only=False):
        """
        Собираем аггрегационный запрос на получение количества записей модуля
        """
        dt_name = dt_name or 'created_at'
        provider_name = provider_name or 'provider'
        match_query = match_query or {}
        match_query.update({
            'provider': {'$in': providers},
            'on_date': {'$gte': on_date},
        })

        agg_query = [
            {'$project': {
                'on_date': '${}'.format(dt_name),
                'provider': '${}'.format(provider_name),
            }},
            {'$match': match_query},
            {'$sort': {dt_name: 1}},
            {'$group': {
                '_id': '$provider',
                'last_at': {'$last': '$on_date'},
            }}
        ]

        if not last_only:
            agg_query[-1]['$group']['count'] = {'$sum': 1}
        result = list(model.objects.aggregate(*agg_query))
        return result[0] if result else {}

    @staticmethod
    def get_summary_info(provider_ids):
        crm_summaries = CRMEvent.objects(__raw__={
            'is_summary': True,
            'summary_date': {'$gte': datetime.now()},
            'provider._id': {'$in': provider_ids}
        }
        )
        crm_summary = {}
        for c in crm_summaries:
            c_s = crm_summary.setdefault(c.provider, [])
            c_s.append(c)
        return crm_summary

    def get_activity(self, providers):
        on_date = start_of_day(datetime.now())
        tickets = self.get_module_stat(providers, Ticket,
                                       on_date - relativedelta(months=1),
                                       'created_by.department.provider',
                                       'initial.created_at')
        requests = self.get_module_stat(providers, Request,
                                        on_date - relativedelta(months=1),
                                        'provider._id')
        registries = self.get_registry_statuses(providers)
        gis = self.get_gis_statuses(providers)

        return {x: {
            'Ticket': tickets.get(x, 0),
            'Request': requests.get(x, 0),
            'Registry': registries.get(x, None),
            'GIS': gis.get(x, None),
        } for x in providers}

    def list(self, request):
        params = self.serializer_class(data=request.query_params)
        params.is_valid(raise_exception=True)
        queryset = self.get_queryset(params.validated_data)

        provider_ids = [item.provider.id for item in queryset]
        providers_activity = self.get_activity(provider_ids)
        crm_summary = self.get_summary_info(provider_ids)
        data = []
        for item in queryset:
            provider_id = item.provider.id
            item.extra = dict()
            if (
                    item.last_task
                    and item.last_task.date
                    and item.last_task.date < datetime.now()
            ):
                item.extra['is_missed'] = True
            if providers_activity:
                item.extra['activity'] = providers_activity.get(provider_id)

            if provider_id in crm_summary:
                provider_summary = reversed(sorted(
                    crm_summary[provider_id],
                    key=lambda i: i.summary_date
                ))
                item.extra['summary_comments'] = \
                    [s.comment for s in provider_summary]

            data.append(item)
        results = self.paginate_queryset(data, request)
        serializer = MonitoringSerializer(results, many=True)
        response = self.get_paginated_response(serializer.data)
        return response


class CRMStatisticsViewSet(CRMBaseViewSet):
    """
    Страница Статистика по CRM
    """
    http_method_names = ['get']
    permission_classes = (SuperUserOnly,)
    serializer_class = CRMCustomSerializer
    slug = 'providers'
    EVENT_RESULTS = (EventResult.GOOD, EventResult.BAD)
    TYPES_LIST = list(t[0] for t in EVENT_TYPE)

    def _get_workers_info(self, worker_ids):
        request_auth = RequestAuth(self.request)
        provider_id = request_auth.get_provider_id()
        workers = list(Worker.objects(__raw__={
            '_id': {'$in': worker_ids},
            'provider._id': provider_id,
            'is_deleted': {'$ne': True},
        }).as_pymongo())
        workers_dict = dict()
        for item in workers:
            department = item.get('department', {})
            workers_dict[item['_id']] = {
                'short_name': item['short_name'],
                'department_id': department.get('_id', None),
                'department': department.get('name', ''),
                'position': item.get('position', {}).get('name', '')
            }
        return workers_dict

    def _get_statuses(self, queryset):
        query = [
            {'$group': dict(
                _id={'type': '$event_type', 'account': '$account._id'},
                account_info={'$first': '$account'},
                **{
                    key: {
                        '$sum': {
                            '$cond': [
                                {'$eq': ['$result', key]},
                                {'$literal': 1},
                                {'$literal': 0},
                            ],
                        }
                    }
                    for key in self.EVENT_RESULTS
                }
            )},
            {
                '$project': dict(
                    account_info='$account_info.short_name',
                    account='$_id.account',
                    type='$_id.type',
                    **{key: 1 for key in self.EVENT_RESULTS}
                ),
            },
            {
                '$match': {
                    '$or': [{key: {'$gt': 0}} for key in self.EVENT_RESULTS]
                }
            },
            {
                '$group': {
                    '_id': '$account',
                    'res': {'$push': '$$ROOT'}
                }
            }
        ]
        return list(queryset.aggregate(*query))

    def get_queryset(self, params):
        provider_id = RequestAuth(self.request).get_provider_id()
        general_params, events_params = self.split_params(params)
        crm_ids = list()
        if general_params:
            custom_filter = self.custom_filter(general_params)
            general_queryset = CRM.objects(
                owner=provider_id).filter(custom_filter)
            crm_ids = [item.id for item in general_queryset]
        q = Q(
            crm__owner=provider_id,
        )
        if crm_ids:
            q &= Q(crm__id__in=crm_ids)
        full_events_q = Q()
        if events_params:
            for prefix in ('actions', 'tasks'):
                events_q = Q()
                for k, v in events_params.items():
                    if f'{prefix}__date_from' in k:
                        events_q &= Q(date__gte=v)
                    elif f'{prefix}__date_till' in k:
                        events_q &= Q(date__lte=v)
                if any(filter(lambda x: (prefix in x), events_params.keys())):
                    events_q &= Q(_type=f'{prefix.title()[:-1]}')
                full_events_q |= events_q
            if 'account__id__in' in events_params.keys():
                full_events_q &= Q(
                    account__id__in=events_params['account__id__in']
                )
        if full_events_q:
            q &= full_events_q
        return CRMEvent.objects(q)

    def _get_formatted_rows(self, statuses, workers):
        body = list()
        raw_rows = list()
        for item in statuses:
            x = dict()
            for k in item['res']:
                x[k['type']] = {'bad': k['bad'], 'good': k['good']}
            for t in self.TYPES_LIST:
                x.setdefault(t, {'bad': 0, 'good': 0})
            x['account_id'] = item['_id']
            x['account_info'] = item['res'][0]['account_info']
            x.update(workers.get(item['_id'], {}))
            raw_rows.append(x)

        groupped_depts = defaultdict(list)
        for item in raw_rows:
            if not item.get('department_id'):
                continue
            groupped_depts[item['department_id']].append(item)

        for k, v in groupped_depts.items():
            obj = {
                'department_order': DEPARTMENTS_ORDER[v[0]['department_id']],
                'department': [x['department'] for x in v],
                'department_id': v[0]['department_id'],
                'position': [x.get('position', '') for x in v],
                'short_name': [x['short_name'] for x in v],
                'total': list()
            }
            for name in self.TYPES_LIST:
                obj[name] = [x.get(name, {'bad': 0, 'good': 0}) for x in v]
            for t1, t2, t3, t4 in zip(*[obj[kk] for kk in self.TYPES_LIST]):
                t = {
                    'good': sum([x['good'] for x in (t1, t2, t3, t4)]),
                    'bad': sum([x['bad'] for x in (t1, t2, t3, t4)]),
                }
                obj['total'].append(t)
            body.append(obj)
        body = sorted(body, key=lambda a: a['department_order'])
        return body

    @staticmethod
    def _get_header():
        schema = {
            'position': 'Должность',
            'short_name': 'Ф.И.О.',
            'department': 'Отдел',
            'department_id': 'Идентификатор отдела',
            'total': 'Итого'
        }
        schema.update({x[0]: x[1] for x in EVENT_TYPE})
        return [{'key': k, 'value': v} for k, v in schema.items()]

    def _get_caption(self):
        request_auth = RequestAuth(self.request)
        return {
            "provider": request_auth.get_provider().str_name,
            "report_created_at": datetime.now(),
            "report_name": "Отчет по действиям с организациями",
            "worker": request_auth.get_account_anyway().short_name
        }

    def list(self, request):
        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        queryset = self.get_queryset(serializer.validated_data)
        statuses = self._get_statuses(queryset)
        account_ids = [item['_id'] for item in statuses]
        workers = self._get_workers_info(account_ids)
        body = self._get_formatted_rows(statuses, workers)
        caption = self._get_caption()
        header = self._get_header()
        result = CustomJsonEncoder.perform_encode({
            'body': body,
            'header': header,
            'caption': caption
        })
        return self.json_response(data={'data': result})
