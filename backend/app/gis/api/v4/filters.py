from bson import ObjectId
from mongoengine import QuerySet, Q

from rest_framework.filters import BaseFilterBackend
from rest_framework.request import Request
from rest_framework.viewsets import GenericViewSet  # : APIView

from app.gis.models.guid import GUID
from utils.drf.authentication import RequestAuth
from utils.drf.crud_filters import get_boolean_fields, ParamsFilter, get_boolean


class ProviderIdFilter(BaseFilterBackend):
    """Фильтр по полю provider_id"""
    def filter_queryset(self, request, queryset, view):

        request_auth = RequestAuth(request)

        if (request_auth.is_slave() or  # режим внешнего управления?
                not request_auth.is_super()):  # не супер пользователь?
            return queryset.filter(
                # request.user.provider.id возвращает организацию сотрудника
                provider_id=request_auth.get_provider_id(),  # работает в
            )
        else:  # режим супер-пользователя (ЗАО "Отдел")!
            return queryset  # WARN всех провайдеров


class ObjectTagFilter(BaseFilterBackend):
    """Фильтр по полю GUID.tag"""
    def filter_queryset(self,
            request: Request, queryset: QuerySet, view: GenericViewSet):
        tag: str = request.query_params.get('tag')  # или None

        if not tag:
            return queryset
        elif tag in GUID.DATED_TAGS:  # устаревший признак объекта?
            tag = GUID.DATED_TAGS[tag]
            # request.query_params._mutable = True  # WARN не рекомендуется
            # request.query_params['tag'] = tag  # передается в ParamsFilter

        if view.lookup_field in view.kwargs:
            object_field: str = 'object_id'
            view.kwargs[object_field] = ObjectId(view.kwargs.pop(view.lookup_field))
            view.lookup_field = object_field  # используется в get_object

        return queryset.filter(tag=tag)


class ErrorTextFilter(BaseFilterBackend):
    """Фильтр по полю GUID.error"""
    def filter_queryset(self,
            request: Request, queryset: QuerySet, view: GenericViewSet):
        if 'error' in request.query_params:  # : QueryDict ~ dict
            error: str = request.query_params['error'].strip()  # не None
            if error:  # получено значение атрибута?
                return queryset.filter(error__icontains=error)  # re.IGNORECASE
            else:  # пустая строка?
                return queryset.filter(error=None)
        elif request.query_params.get('status') == 'error':
            return queryset.filter(error__ne=None)

        return queryset  # error__[ne/иной оператор] передается в ParamsFilter


class MongoParamsFilter(BaseFilterBackend):
    """Фильтр по параметрам с синтаксисом запросов MongoDB"""
    def filter_queryset(self,
            request: Request, queryset: QuerySet, view: GenericViewSet):
        if not request.query_params:
            return queryset

        model_fields: dict = queryset._document._fields  # поля модели запроса
        boolean_fields: list = get_boolean_fields(model_fields)  # булевы поля

        query_filter = Q()
        for param, value in request.query_params.items():
            # отбрасываем параметры по которым не нужно фильтровать
            if param in ('limit', 'offset', *ParamsFilter.EXCLUDE_FIELDS):
                continue
            elif any(query_param.startswith(param.split('__')[0])  # (error)__ne
                    for query_param in queryset._query):  # запрос кэшируется
                # print('DUP PARAM', param, 'IN', queryset._query)
                continue

            is_boolean = False  # параметр имеет булево значение?
            if value in ('true', 'false', 'null'):  # значение похоже на булево?
                if param.endswith('__exists'):  # запрос с булевым значением?
                    is_boolean = True
                # параметр содержит название одного из булевых?
                elif any(field_name in param for field_name in boolean_fields):
                    is_boolean = True

            if param.endswith('__in') or param.endswith('__nin'):
                value = list(
                    map(get_boolean, request.query_params.getlist(param))
                ) if is_boolean else request.query_params.getlist(param)
            elif is_boolean:
                value = get_boolean(value)

            query_filter &= Q(**{param: value})  # : Q

        return queryset.filter(query_filter)
