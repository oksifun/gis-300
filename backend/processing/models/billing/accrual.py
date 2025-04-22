from datetime import datetime

from mongoengine import Document, StringField, DateTimeField, \
    EmbeddedDocumentField, EmbeddedDocumentListField, EmbeddedDocument, \
    FloatField, IntField, BooleanField, \
    ObjectIdField, LazyReferenceField, ListField, DictField, ValidationError

from app.c300.core.delete_data import soft_delete_object
from processing.models.billing.base import ProviderBinds, BindedModelMixin, \
    ChangeBlockingMixin
from processing.models.billing.embeddeds.accrual_document import \
    DenormalizedAccrualDocument
from processing.models.billing.embeddeds.tenant import DenormalizedTenant

from processing.models.choices import *


class ServiceTotals(EmbeddedDocument):
    recalculations = IntField()
    shortfalls = IntField()
    privileges = IntField()
    privileges_info = IntField()


class Privilege(EmbeddedDocument):
    category = ObjectIdField(
        verbose_name='Ссылка на категорию льготы в справочнике',
        null=True,
    )
    tenant = LazyReferenceField(
        'processing.models.billing.account.Account',
        verbose_name='Житель-льготник',
        null=True,
    )
    value = IntField(required=True, verbose_name='Значение льготы')
    count = IntField(
        required=True,
        min_value=0,
        default=1,
        verbose_name='Количество человек, на которых расчитана льгота'
    )
    is_info = BooleanField(
        required=True,
        default=False,
        verbose_name='Справочная льгота не влияет на итоговую сумму начислений'
    )
    consumption = FloatField(required=False, default=0.0)
    area = FloatField(required=False, default=0.0)


class Recalculation(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    reason = StringField(
        choices=RECALCULATION_REASON_TYPE_CHOICES,
        default=RecalculationReasonType.MANUAL,
        verbose_name='Причина перерасчёта'
    )
    value = IntField(verbose_name='Значение перерасчета', required=True)
    date_from = DateTimeField(
        default=None,
        verbose_name='Дата начала перерасчета'
    )
    date_till = DateTimeField(
        default=None,
        verbose_name='Дата окончания перерасчета'
    )
    consumption = FloatField(
        required=False,
        default=0.0,
        verbose_name='Перерасчитываемый расход',
    )
    consumption_type = StringField(
        choices=CONSUMPTION_TYPE_CHOICES,
        default=ConsumptionType.METER_WO,
        verbose_name='Как был посчитан перерасчитываемый расход',
    )


class VendorEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    contract = ObjectIdField(null=True, verbose_name='ID договора')


class ServiceEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    tariff = IntField(
        required=True,
        verbose_name='Использованное значение тарифа',
    )
    service_type = ObjectIdField(
        required=True,
        verbose_name='Признак платежа',
    )
    vendor = EmbeddedDocumentField(
        VendorEmbedded,
        verbose_name='Поставщик услуги'
    )
    value = IntField(required=True, verbose_name='Начислено')
    privileges = EmbeddedDocumentListField(Privilege, verbose_name='Льготы')
    recalculations = EmbeddedDocumentListField(
        Recalculation,
        verbose_name='Перерасчеты',
    )
    shortfalls = EmbeddedDocumentListField(
        Recalculation,
        verbose_name='Недопоставки',
    )
    consumption = FloatField(
        required=True,
        default=0.0,
        verbose_name='Расход услуги',
    )
    norma = FloatField(
        required=False,
        default=0.0,
        verbose_name='Найденный при расчёте норматив',
    )
    allow_pennies = BooleanField(
        default=True,
        verbose_name='Участвует ли услуга в расчёте пеней',
    )
    totals = EmbeddedDocumentField(
        ServiceTotals,
        verbose_name='Суммарные данные',
    )
    comment = StringField(verbose_name='Комментарий к начислению по статье')
    method = StringField(
        choices=CONSUMPTION_TYPE_CHOICES,
        verbose_name='Метод расчета',
    )
    result = IntField(verbose_name='Результат начисления по услуге')
    reversal = BooleanField(
        verbose_name='Строка является сторно, т.е. результат отрицательный',
    )
    # относится к старым начислениям, новые не должны иметь этот ключ
    split = BooleanField(
        default=False,
        verbose_name='Должен быть расщеплён автоматически',
    )
    warnings = ListField(StringField())


class Settings(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    use_penalty = BooleanField(
        required=True,
        verbose_name='Учитывать начисление при расчёте пеней',
    )


class Penalty(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    period = DateTimeField(
        null=True,
        verbose_name='Месяц просроченной задолженности',
    )
    value = IntField(required=True, verbose_name='Рассчитанная сумма пени')
    value_include = IntField(
        required=True,
        verbose_name='Сумма пени, включённая в это начисление',
    )
    value_return = IntField(required=True, verbose_name='Ручной возврат пени')
    is_unpaid = BooleanField(
        required=True,
        default=False,
        verbose_name='Задолженность не погашена на момент расчёта',
    )
    subject_to_refund = BooleanField(verbose_name='Подлежит возврату')


class UnpaidService(EmbeddedDocument):
    """
    Неоплаченная услуга
    """
    id = ObjectIdField(db_field="_id")
    value = IntField(required=True, verbose_name='Сумма долга')
    service_type = LazyReferenceField(
        'processing.models.billing.service_type.ServiceType',
        required=True,
        verbose_name='Услуга',
    )


class Totals(EmbeddedDocument):
    """
    Суммарные денормализованные данные
    """
    id = ObjectIdField(db_field="_id")
    penalties = IntField(verbose='Итого пеней')
    # todo удалить после миграции
    additionals = IntField(verbose_name='Итого дополнительных сумм')


class IsAutoPayment(EmbeddedDocument):
    status = StringField(choices=('wait', 'ready', 'new'),)
    payment_try = DateTimeField(default=datetime.now)


class Accrual(ChangeBlockingMixin, BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Accrual',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.pr',
            {
                'name': 'debtors_mixin',
                'fields': [
                    'account.area.house.id',
                    '_binds.pr',
                    'sector_code',
                    'doc.status',
                    'month',
                ],
            }
        ],
    }
    doc = EmbeddedDocumentField(
        DenormalizedAccrualDocument,
        required=True,
        verbose_name='Входит в документ начислений за указанную дату',
    )
    account = EmbeddedDocumentField(
        DenormalizedTenant,
        required=True,
        verbose_name='Лицевой счёт',
    )
    month = DateTimeField(
        required=True,
        verbose_name='Месяц, на который расчитано начисление'
    )
    sector_code = StringField(
        required=True,
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        default=AccrualsSectorType.RENT,
        verbose_name='Направление начислений',
    )
    is_auto_payment = EmbeddedDocumentField(
        IsAutoPayment,
        verbose_name="Оплата автоплатежом"
    )
    debt = IntField(
        required=True,
        verbose_name='Натуральный долг жителя'
    )
    value = IntField(required=True, verbose_name='Сумма начисленного')
    services = EmbeddedDocumentListField(
        ServiceEmbedded,
        default=[],
        verbose_name='Начисления по услугам',
    )
    penalties = EmbeddedDocumentListField(
        Penalty,
        default=[],
        verbose_name='Пени',
    )
    penalty_vendor = EmbeddedDocumentField(
        VendorEmbedded,
        verbose_name='Поставщик услуги'
    )
    subsidy = IntField(verbose_name='Сумма субсидии')
    settings = EmbeddedDocumentField(
        Settings,
        required=True,
        verbose_name='Настройки'
    )
    tariff_plan = ObjectIdField(
        # required=True,
        verbose_name='Тарифный план',
    )
    unpaid_services = EmbeddedDocumentListField(
        UnpaidService,
        default=[],
        verbose_name='Непогашенные услуги',
    )
    unpaid_total = IntField(verbose_name='Остаток от погашения')
    repaid_at = DateTimeField(verbose_name='Дата погашения начисления')
    totals = EmbeddedDocumentField(
        Totals,
        required=True,
        verbose_name='Суммарные данные',
    )
    bill = IntField(
        null=True,
        verbose_name='Сумма выписанной квитанции',
    )
    owner = ObjectIdField(
        verbose_name='Организация-получатель',
    )
    is_deleted = BooleanField()

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    consumption_methods = ListField(DictField())

    def delete(self, **write_concern):
        if self.doc.status not in ('wip', 'edit'):
            raise ValidationError('Allowed only for wip statuses')
        self.check_change_permissions()
        soft_delete_object(self)

    def save(self, *args, **kwargs):
        if not kwargs.get('ignore_lock'):
            self.check_change_permissions()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        self.restrict_changes()
        self.do_i_have_auto_pay()

        return super().save(*args, **kwargs)

    def update(self, *args, **kwargs):
        self.check_change_permissions()
        super().update(**kwargs)

    def do_i_have_auto_pay(self):
        from processing.models.billing.account import Tenant
        if self._created:
            tenant = Tenant.objects(id=self.account.id).first()
            if tenant and tenant.p_settings:
                for setting in tenant.p_settings:
                    if setting.sector == self.sector_code and setting.auto:
                        self.is_auto_payment.status = 'new'

    def _get_providers_binds(self):
        from processing.models.billing.provider.main import ProviderRelations

        result = {self.doc.provider, self.owner}
        relations = ProviderRelations.objects(
            provider=self.doc.provider
        ).only('slaves').as_pymongo().first()
        if relations:
            slaves = {
                x['provider']
                for x in relations['slaves']
                if self.account.area.house.id in x['houses']
            }
            if slaves:
                result |= slaves
        return list(result)

    @classmethod
    def process_provider_binds(cls, provider_id, force=False):
        from processing.models.billing.provider.main import ProviderRelations

        pushed = 0
        pulled = 0
        # кто разрешил смотреть свои документы
        relations = ProviderRelations.objects(
            slaves__provider=provider_id,
        ).as_pymongo()
        masters_houses = []
        for r in relations._iter_results():
            for s in r['slaves']:
                if s['provider'] == provider_id:
                    masters_houses.append((r['provider'], s['houses']))
        # удалиться из чужих документов
        res = cls.objects(
            doc__provider__ne=provider_id,
            owner__nin=[p[0] for p in masters_houses] + [provider_id],
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id, full_result=True)
        pulled += res.modified_count
        # добавиться в свои документы
        res = cls.objects(__raw__={'$or': [
            {'doc.provider': provider_id},
            {'owner': provider_id},
        ]}).update(add_to_set___binds__pr=provider_id, full_result=True)
        pushed += res.modified_count
        # добавиться в чужие разрешённые документы
        for master_houses in masters_houses:
            s_pushed, s_pulled = cls._process_provider_master_binds(
                master_id=master_houses[0],
                slave_id=provider_id,
                houses=master_houses[1],
                force=force,
            )
            pushed += s_pushed
            pulled += s_pulled
        return pushed, pulled

    @classmethod
    def _process_provider_master_binds(cls, master_id, slave_id, houses,
                                       force=False):
        pushed = 0
        pulled = 0
        # выясним, в какие дома надо добавить, а из каких удалить
        houses_disallow = cls.objects(
            __raw__={
                '_binds.pr': slave_id,
                'owner': master_id,
                'doc.provider': {'$ne': slave_id},
                'account.area.house._id': {'$nin': houses}
            },
        ).distinct(
            'account.area.house._id',
        )
        if force:
            houses_allow = houses
        else:
            houses_allow = cls.objects(
                __raw__={
                    '_binds.pr': {'$ne': slave_id},
                    'owner': master_id,
                    'doc.provider': {'$ne': slave_id},  # todo: Лишнее?
                    'account.area.house._id': {'$in': houses}
                },
            ).distinct(
                'account.area.house._id'
            )

        # удалиться из запрещённых домов
        for h in houses_disallow:
            res = cls.objects(__raw__={
                '_binds.pr': slave_id,
                'account.area.house._id': h,
                'doc.provider': {'$ne': slave_id},
                'owner': master_id,
            }).update(
                pull___binds__pr=slave_id,
                full_result=True,
            )
            pulled += res.modified_count
        # добавиться в разрешённые дома
        for h in houses_allow:
            res = cls.objects(__raw__={
                'account.area.house._id': h,
                'owner': master_id,
            }).update(
                add_to_set___binds__pr=slave_id,
                full_result=True,
            )
            pushed += res.modified_count
        return pushed, pulled

    @classmethod
    def get_last_period_by_sector(cls, tenant_id, sector):
        last_accrual = cls.objects(
            account__id=tenant_id,
            sector_code=sector
        ).order_by(
            '-month',
        ).only(
            'month',
        ).as_pymongo().first()
        return last_accrual['month']
