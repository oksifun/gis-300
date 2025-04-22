from mongoengine import (
    DateTimeField, Document, EmbeddedDocument, EmbeddedDocumentField,
    FloatField, IntField, ListField, ReferenceField, StringField,
)

from app.house.models.house import House
from processing.models.billing.provider.main import Provider
from processing.models.billing.service_type import ServiceType
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES


class HouseServiceAccrualsCached(EmbeddedDocument):
    service = ReferenceField(ServiceType, verbose_name='Услуга')

    total = IntField(verbose_name='Сумма начисленного')
    debt = IntField(verbose_name='Сумма положительного начисленного')
    value = IntField(verbose_name='Сумма начисления по тарифу')
    recalculations = IntField(verbose_name='Сумма перерасчётов')
    shortfalls = IntField(verbose_name='Сумма недопоставок')
    privileges = IntField(verbose_name='Сумма льгот')
    consumption = FloatField(verbose_name='Сумма расхода')
    tariff = ListField(IntField(), verbose_name='Список использованных тарифов')


class HouseAccrualsCached(Document):
    """
    Суммарные начисления по домам для отчётов
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'house_accruals',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'house',
            {
                'fields': [
                    'house',
                    'provider',
                    'sector',
                    'accounts_filter',
                    'month',
                ],
                'unique': True,
            },
        ],
    }

    provider = ReferenceField(Provider, verbose_name='Организация')
    house = ReferenceField(House, verbose_name='Дом')
    services = ListField(EmbeddedDocumentField(HouseServiceAccrualsCached))
    penalties = IntField(verbose_name='Сумма пени')
    month = DateTimeField(verbose_name='Месяц начисления')
    sector = StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES,
                         verbose_name='Направление')
    accounts_filter = StringField(verbose_name='Код фильтра по жителям')

