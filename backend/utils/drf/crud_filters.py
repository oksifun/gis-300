from mongoengine import Q, BooleanField, EmbeddedDocumentField, \
    EmbeddedDocumentListField
from rest_framework.filters import BaseFilterBackend


class LimitFilterBackend(BaseFilterBackend):
    """
    Фильтрует по полю limit.
    """
    def filter_queryset(self, request, queryset, view):
        limit = request.query_params.get('limit')
        offset = int(request.query_params.get('offset') or 0)
        if limit:
            return queryset[offset: offset + int(limit)]
        else:
            return queryset


class ParamsFilter(BaseFilterBackend):
    """
    Фильтрует по остальным параметрам.
    """
    EXCLUDE_FIELDS = ['sort_date__gte', 'sort_date__lte']

    def filter_queryset(self, request, queryset, view):
        if request.query_params:
            # Модель используемая для запроса
            model_fields = queryset._document._fields
            # Поиск всех булевых полей в модели
            boolean_fields = get_boolean_fields(model_fields)
            query_filter = Q()
            for param, val in request.query_params.items():
                # Убираем параметры по которым не нужно фильтровать
                if param not in ('limit', 'offset', *self.EXCLUDE_FIELDS):
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
                            val = list(map(
                                get_boolean, request.query_params.getlist(param)
                            ))
                        else:
                            val = request.query_params.getlist(param)
                    else:
                        if boolean:
                            val = get_boolean(val)
                    query_filter &= Q(**{param: val})
            return queryset.filter(query_filter)
        else:
            return queryset


def get_boolean(value: str):

    if value == 'true':
        return True
    elif value == 'false':
        return False
    elif value == 'null':
        return
    else:
        raise ValueError('Not a boolean string!')


def get_boolean_fields(model, boolean_fields=None):
    """
    Рекурсивный поиск всех булевых полей модели.
    """

    boolean_fields = [] if boolean_fields is None else boolean_fields
    for field in model:
        # Добавляем булево поле к списку
        if isinstance(model[field], BooleanField):
            boolean_fields.append(field)
        # Если поле вложенное, то проверим его поля
        elif isinstance(model[field], EmbeddedDocumentField):
            get_boolean_fields(
                model[field].document_type._fields, boolean_fields
            )
        elif isinstance(model[field], EmbeddedDocumentListField):
            get_boolean_fields(
                model[field].field.document_type._fields, boolean_fields
            )
    return boolean_fields
