import datetime

from mongoengine import Document, ReferenceField, StringField, ListField, \
    ObjectIdField, DictField, DateTimeField

from processing.models.billing.provider.main import Provider
from processing.models.choices import FILTER_CODES_CHOICES, \
    FILTER_PURPOSES_CHOICES, FILTER_PREPARED_DATA_TYPES


class FilterCache(Document):
    """
    Кэш фильтров для отчётов и других. При наличии цели (purpose) фильтр заранее
    должен подготовить данные, которые потом могут быть использованы
    этой "целью"
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'filters',
    }

    provider = ReferenceField(Provider, verbose_name='Организация')
    code = StringField(
        choices=FILTER_CODES_CHOICES,
        default='',
        verbose_name='Системный код фильтра',
    )
    objs = ListField(ObjectIdField(), verbose_name='ИД объектов фильтра')
    purpose = StringField(
        choices=FILTER_PURPOSES_CHOICES,
        verbose_name='Цель использования фильтра',
    )
    extra = DictField(verbose_name='Дополнительные данные фильтра')
    readiness = ListField(
        StringField(),
        verbose_name='Коды готовых данных',
    )
    used = DateTimeField(verbose_name='Дата последнего использования')

    @classmethod
    def extract_objs(cls, filter_id):
        filter_ins = cls.objects(
            pk=filter_id,
        ).only(
            'objs',
        ).as_pymongo().get()
        cls.objects(
            pk=filter_id,
        ).update(
            used=datetime.datetime.now(),
        )
        return filter_ins['objs']


class FilterPreparedData(Document):
    """
    Данные, подготовленные фильтрами. Данные хранятся в виде списка словарей
    любой структуры. Данные хранят время создания и последнего использования для
    возможности удаления через определённый срок
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'filters_data',
    }

    filter_id = ReferenceField(FilterCache, verbose_name='Фильтр')
    code = StringField(
        choices=FILTER_PREPARED_DATA_TYPES,
        verbose_name='Код типа данных'
    )
    data = ListField(DictField(), verbose_name='Данные в виде списка')
    created = DateTimeField(verbose_name='Время создания')
    used = DateTimeField(verbose_name='Время последнего использования')

