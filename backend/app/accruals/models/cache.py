import datetime

from mongoengine import (
    DictField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentListField,
    FloatField,
    ObjectIdField,
    StringField,
    DateTimeField,
    IntField,
    BooleanField,
    EmbeddedDocumentField,
)

from app.accruals.models.choices import (COUNT_TYPE_CHOICES, CountType,)
from app.caching.models.filters import FilterCache
from processing.models.billing.account import Tenant
from app.house.models.house import House
from processing.models.billing.base import BindedModelMixin, ProviderBinds, \
    RelationsProviderBindsProcessingMixin
from processing.models.house_choices import (PrintBillsType,)


class AccrualHouseServiceCacheMethod:
    BY_DOC_DATE = 0
    BY_MONTH = 2


ACCRUAL_HOUSE_SERVICE_CACHE_METHODS_CHOICES = (
    (AccrualHouseServiceCacheMethod.BY_DOC_DATE, 'По дате начисления'),
    (AccrualHouseServiceCacheMethod.BY_MONTH, 'По периоду начисления'),
)


class AccrualHouseServiceCacheTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'house_service_accruals',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('house', 'month', 'provider'),
        ],
    }
    house = ObjectIdField()
    month = DateTimeField()
    provider = ObjectIdField()

    @classmethod
    def add_task(cls, house_id, month, provider_id):
        if not provider_id:
            cls.objects(
                __raw__={
                    'house': house_id,
                    'month': month,
                    'provider': {'$ne': None},
                },
            ).delete()
        existing = cls.objects(
            __raw__={
                'house': house_id,
                'month': month,
                'provider': None,
            },
        ).first()
        if existing:
            return existing
        return cls.objects(
            __raw__={
                'house': house_id,
                'month': month,
                'provider': provider_id,
            },
        ).upsert_one(
            month=month,
        )


class AccrualHouseServiceCache(RelationsProviderBindsProcessingMixin,
                               BindedModelMixin, Document):
    """
    Кэш начислений по услугам для домов нарастающим итогом по дате на первое
    число месяца. Сумма всех начислений дома по услуге с датой раньше первого
    числа указанного месяца с учётом нескольких вариантов фильтра, используемого
    в отчётах
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'house_service_accruals',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('house', 'sector', 'month', 'owner'),
        ],
    }

    created = DateTimeField(default=datetime.datetime.now)
    last_used = DateTimeField()

    house = ObjectIdField()
    owner = ObjectIdField()
    month = DateTimeField()
    sector = StringField()
    service = ObjectIdField()

    value = IntField()
    debt = IntField()

    area_type = StringField()
    is_developer = BooleanField()
    account_type = StringField()
    method = IntField()

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязка к организациям',
    )

    _HOUSE_FIELD_PATH = 'house'
    _HOUSE_FIELD_FILTER_NAME = 'house'

    def save(self, *args, **kwargs):
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        return super().save(*args, **kwargs)

    def has_binds(self):
        return bool(self._binds)


class ReceiptCacheValue(EmbeddedDocument):
    code = StringField()
    area_types = StringField()
    values_name = StringField()
    value = FloatField()


class ReceiptAccrualCache(Document):
    """
    Кэш данных для квитанций
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'receipt_accruals',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            {
                'fields': [
                    'accrual_doc',
                ],
                'unique': True,
            },
        ],
    }

    accrual_doc = ObjectIdField()
    values = EmbeddedDocumentListField(ReceiptCacheValue)

    @classmethod
    def get_or_create(cls, accrual_doc_id):
        obj = cls.objects(accrual_doc=accrual_doc_id).first()
        if not obj:
            obj = cls(
                accrual_doc=accrual_doc_id,
                values=[],
            )
            obj.save()
        return obj

    @classmethod
    def set_value(cls, accrual_doc_id, value,
                  code, area_types_name, values_name):
        cache_obj = cls.get_or_create(accrual_doc_id)
        cls.objects(
            pk=cache_obj.pk,
        ).update(
            add_to_set__values=ReceiptCacheValue(
                code=code,
                area_types=area_types_name,
                values_name=values_name,
                value=value,
            ),
        )


class ReceiptsStatisticsCache(Document):
    """
    Кэш данных для печати квитанций
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'receipts_statistics',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'doc_id',
            'filter_id',
            'house_id',
            'print_type',
            'count_type',
        ],
    }

    doc_id = ObjectIdField(required=True)
    state = StringField(required=True, default='new')
    count_type = StringField(required=True, choices=COUNT_TYPE_CHOICES)
    print_type = StringField(required=False)
    filter_id = ObjectIdField(required=False)
    house_id = ObjectIdField(required=False)
    error_message = StringField(required=False)
    statistics = DictField(required=False)

    def count_statistics(self):
        self.state = 'wip'
        self.save()

        if self.print_type and self.house_id:
            self._save_print_type()
        tenants = self._get_tenants()
        stats = dict(total=len(tenants))
        if tenants:
            disabled = tuple(t['_id'] for t in tenants if t['disabled_paper'])

            channels = tuple(
                tenant['_id'] for tenant in tenants
                if any((
                    tenant['telegram'],
                    tenant['mobile_app'],
                    tenant['email'],
                ))
                and not tenant['print_anyway']
            )
            if self.count_type == CountType.FULL:
                stats['without_channels'] = stats['total'] - len(channels)
                stats['papers_enabled'] = stats['total'] - len(disabled)
            else:
                if self.print_type == PrintBillsType.NO_CHANNELS:
                    stats['have_channels'] = len(channels)
                else:
                    stats['papers_disabled'] = len(disabled)

        self.statistics = stats
        self.state = 'finished'
        self.save()

    def _get_tenants(self):
        if self.filter_id:
            tenant_ids = FilterCache.extract_objs(self.filter_id)
            if not tenant_ids:
                return
            query_kwargs = dict(tenant_ids=tenant_ids)
        else:
            query_kwargs = dict(house_id=self.house_id)
        recipients = Tenant.recipients_channels(**query_kwargs)
        return recipients

    def _save_print_type(self):
        House.objects(
            id=self.house_id
        ).update(
            set__print_bills_type=self.print_type,
        )
