import datetime
import json

from bson import ObjectId
from dateutil.relativedelta import relativedelta
from mongoengine import Q, ValidationError
from rest_framework.filters import BaseFilterBackend

from api.v4.base_crud_filters import get_boolean_fields, get_boolean
from app.caching.core.utils import parse_str_number_list
from app.personnel.models.personnel import Worker
from app.requests.models.request import Request
from processing.models.billing.house_group import HouseGroup
from app.requests.models.choices import REQUEST_STATUS_PUBLIC_CHOICES


class ForcedLimitFilter(BaseFilterBackend):
    """
    Принудительная передача лимита, если  не был передан.
    """
    def filter_queryset(self, request, queryset, view):
        if not request.query_params.get('limit'):
            return queryset[:100]
        else:
            return queryset


class NonstandardFilter(BaseFilterBackend):
    """
    Нестандартные фильтры.
    """

    NONSTANDARD_FIELDS = (
        'search_by',
        'worker__in',
        'position__in',
        'department__in',
        'kinds__in',
        'house__id__in',
        'house__id',
        'area_range',
        'actions',
        'by_tenant',
    )

    RELATED_FIELDS = {
        'dispatchers': 'dispatcher__id__in',
        'executors': 'executors__in'
    }

    INDEX_SELECT_KEYS = ('kind', 'house', 'executor', 'dispatcher')
    _ALL_STATUSES = [c[0] for c in REQUEST_STATUS_PUBLIC_CHOICES]

    def filter_queryset(self, request, queryset, view):

        # Сократим для удобства
        rqp = request.query_params
        if rqp:
            query_filter = Q()
            # Выставим значения по умолчанию при их отсутсвии
            # if not [p for p in rqp if 'created_at' in p]:
            #     query_filter &= Q(created_at__gt=datetime.datetime(2000, 1, 1))
            if not [p for p in rqp if 'common_status' in p]:
                query_filter &= Q(common_status__in=self._ALL_STATUSES)

            # Обработка нестандартных полей
            # Денормализация поискового фильтра search_by
            if 'search_by' in rqp:
                main_filter = self.RELATED_FIELDS.get(
                    rqp.get('search_by')
                )
                # Если передан корректрый фильтр
                if main_filter:
                    # Составляем запрос по переданным параметрам,
                    # ранжируя их по приоритету
                    search_by_filter = self._get_worker_search_filter(request)
                    if search_by_filter:
                        workers = Worker.objects(
                            **search_by_filter
                        ).only('id').as_pymongo()
                        query_filter &= Q(**{
                            main_filter: [x['_id'] for x in workers]
                        })
            # Денормализация kinds в fast_kinds
            if 'kinds__in' in rqp:
                kinds = rqp.getlist('kinds__in')
                if kinds:
                    fast_kinds = Request.get_fast_kinds(
                        list(map(ObjectId, kinds))
                    )
                    query_filter &= Q(fast_kinds__in=fast_kinds)
            # Денормализация фильтра houses
            if 'house__id' in rqp or 'house__id__in' in rqp:
                houses = rqp.getlist('house__id__in') or rqp.getlist('house__id')
                if houses:
                    houses = self._check_houses(list(map(ObjectId, houses)))
                    query_filter &= Q(house__id__in=houses)
            # Денормализация area_range
            if 'area_range' in rqp:
                try:
                    parsed_numbers = parse_str_number_list(rqp['area_range'])
                except ValueError as error:
                    raise ValidationError(str(error))
                if rqp.get('area_range'):
                    query_filter &= Q(area__str_number__in=parsed_numbers)

            # Денормализация actions
            if 'actions' in rqp:
                actions_filter = self._get_actions_filter(rqp)
                if actions_filter:
                    # Добавим собранный фильтр к общему фильтру
                    query_filter &= actions_filter
            # Только заявки только от жителей
            if 'by_tenant' in rqp and rqp['by_tenant'] == 'true':
                query_filter &= Q(dispatcher=None) |\
                                Q(dispatcher__id__exists=False)

            # Модель используемая для запроса
            model_fields = queryset._document._fields
            # Поиск всех булевых полей в модели
            boolean_fields = get_boolean_fields(model_fields)
            for param, val in rqp.items():
                # Убираем параметры по которым не нужно фильтровать
                if param not in ('limit', 'offset', *self.NONSTANDARD_FIELDS):
                    boolean = False  # Является ли параметр булевым
                    # Если значение параметра напоминает булево значение
                    if val in ('true', 'false', 'null'):
                        # Если параметр заканчивается на запрос после
                        # которого всегда идет булин
                        if param.endswith('_exists'):
                            boolean = True
                        # Если имя поля из списка булевых
                        # присутсвует в параметре.
                        # Иначе значение останется строковым.
                        elif [True for x in boolean_fields if x in param]:
                            boolean = True
                    if param.endswith('__in') or param.endswith('__nin'):
                        if boolean:
                            val = list(map(get_boolean, rqp.getlist(param)))
                        else:
                            val = rqp.getlist(param)
                    else:
                        if boolean:
                            val = get_boolean(val)
                    query_filter &= Q(**{param: val})
            # return queryset.filter(query_filter).hint(
            #     self.get_hint(query_filter.to_query(Request))
            # )
            return queryset.filter(query_filter)
        else:
            return queryset

    def get_hint(self, query):
        keys = []
        for key in query:
            if key.startswith('number'):
                return 'number_search'
            if key.startswith('tenant'):
                return 'tenant_search'
            if key.startswith('area'):
                return 'journal_area'
            for i_key in self.INDEX_SELECT_KEYS:
                if key.startswith(i_key):
                    keys.append(i_key)
                    break
        if 'dispatcher' in keys:
            if 'kinds' in keys:
                return 'journal_with_dispatcher_and_kinds'
            if 'house' in keys:
                return 'journal_with_dispatcher_and_houses'
            return 'journal_with_dispatcher'
        if 'executor' in keys:
            if 'kinds' in keys:
                return 'journal_with_executor_and_kinds'
            if 'house' in keys:
                return 'journal_with_executor_and_houses'
            return 'journal_with_executor'
        if 'kinds' in keys:
            return 'journal_with_kinds'
        if 'house' in keys:
            return 'journal_with_houses'
        return 'journal'

    @staticmethod
    def _get_worker_search_filter(request):
        """
        Составляем запрос по переданным параметрам,
        ранжируя их по приоритету.
        """

        search_by_filter = dict()
        if 'worker__in' in request.query_params:
            search_by_filter.update(
                id__in=[
                    ObjectId(x)
                    for x in request.query_params.getlist('worker__in')
                ]
            )
        elif 'position__in' in request.query_params:
            search_by_filter.update(
                position__id__in=[
                    ObjectId(x)
                    for x in request.query_params.getlist('position__in')
                ]
            )
        elif 'department__in' in request.query_params:
            search_by_filter.update(
                department__id__in=[
                    ObjectId(x)
                    for x in request.query_params.getlist('department__in')
                ]
            )
        return search_by_filter

    @staticmethod
    def _check_houses(houses: list):
        """
        Проверка. Не являются ли id группами домов.
        Если являются, то нужно получить дома из этих групп.
        """

        real_houses = []
        house_groups = HouseGroup.objects(id__in=houses).as_pymongo()
        # Если все ID оказались "домовыми"
        if not house_groups:
            return houses
        # Иначи вытащим дома из группы
        house_groups = {x['_id']: x for x in house_groups}
        for h_id in houses:
            hg = house_groups.get(h_id)
            if hg:
                real_houses.extend(hg['houses'])
            else:
                real_houses.append(h_id)
        return real_houses

    @staticmethod
    def _get_actions_filter(rqp):
        """ Денормализация actions """

        # Объект приходит строкой. Так что преобразуем его в словарь
        if rqp.get('actions'):
            actions = json.loads(rqp['actions'])
            # Составим запрос пройдя все объекты
            actions_query = Q()
            for action_id, dates in actions.items():
                sub_query = dict(action=ObjectId(action_id))
                if dates.get('dt_from'):
                    sub_query.update(dict(dt_till__gt=dates['dt_from']))
                if dates.get('dt_till'):
                    sub_query.update(dict(dt_from__lt=dates['dt_till']))
                actions_query &= Q(actions__match=sub_query)
            return actions_query


class StatisticDaysFilter(NonstandardFilter):
    """ Фильтр для получения статистки по дням """

    # Дополнение списка полей, исключенных для фильтрации
    NONSTANDARD_FIELDS = (
        'date_from',
        'date_till',
        *NonstandardFilter.NONSTANDARD_FIELDS
    )

    def filter_queryset(self, request, queryset, view):
        # Получаем заявки прошедшие через Нестандартный фильтр
        queryset = super().filter_queryset(request, queryset, view)
        date_from = request.query_params.get(
            'date_from', datetime.datetime.now()
        )
        date_till = request.query_params.get(
            'date_till', date_from - relativedelta(years=1)
        )
        queryset = queryset.filter(
            created_at__lte=date_from,
            created_at__gte=date_till
        )
        # Теперь сформируем статистику
        pipeline = [
            {'$project': {'date': '$created_at', 'status': '$common_status'}},
            {'$group': {
                '_id': {
                    'year': {'$year': "$date"},
                    'month': {'$month': "$date"},
                    'day': {'$dayOfMonth': "$date"},
                },
                'date': {'$first': '$date'},
                'count': {'$sum': 1}
            }},
        ]

        data = {}
        results = iter(queryset.aggregate(*pipeline))
        for el in results:
            data_iso = datetime.datetime(
                el['date'].year, el['date'].month, el['date'].day
            )
            data[data_iso] = {
                'date': el['_id'],
                'date_iso': data_iso,
                'count': el['count'],
            }

        date_till = datetime.datetime(
            date_till.year, date_till.month, date_till.day
        )
        for x in range((date_from - date_till).days):
            day = (date_till + relativedelta(days=x))
            if day not in data:
                data[day] = {
                    'date': {
                        'day': day.day, 'month': day.month, 'year': day.year
                    },
                    'date_iso': day,
                    'count': 0,
                }
        return sorted(data.values(), key=lambda k: k['date_iso'])


class StatisticStatusesFilter(NonstandardFilter):
    """ Фильтр для получения статистки по статусам """

    def filter_queryset(self, request, queryset, view):
        # Получаем заявки прошедшие через Нестандартный фильтр
        queryset = super().filter_queryset(request, queryset, view)
        pipeline = [{
            '$group':
                {
                    '_id': '$common_status',
                    'x': {'$first': '$common_status'},
                    'y': {'$sum': 1},
                }
        }]
        return list(queryset.aggregate(*pipeline))
