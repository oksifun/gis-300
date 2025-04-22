from datetime import datetime

from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentListField, \
    DateTimeField, BooleanField, IntField, EmbeddedDocumentField, StringField, \
    ObjectIdField, ListField, DictField, DynamicField

from processing.models.billing.base import BindedModelMixin, ProviderBinds, \
    ChangeBlockingMixin
from processing.models.billing.embeddeds.tenant import DenormalizedTenant
from processing.models.billing.embeddeds.vendor import VendorEmbedded


class ServiceTypeAsEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    value = IntField(required=True)
    redeemed = IntField()
    service_type = ObjectIdField(required=True)
    vendor = EmbeddedDocumentField(
        VendorEmbedded,
        verbose_name='Поставщик услуги'
    )
    vendor_paid = BooleanField()
    vendor_payment = ObjectIdField()

    def __str__(self):
        return "{value}".format(value=self.value)


class DenormalizedHouse(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")


class DenormalizedArea(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField())
    house = EmbeddedDocumentField(DenormalizedHouse)


class ReferDocEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    date = DateTimeField(required=True)
    provider = ObjectIdField(required=True)


class DenormalizedPaymentOrAccrual(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    account = EmbeddedDocumentField(DenormalizedTenant)
    doc = EmbeddedDocumentField(ReferDocEmbedded)
    sector_code = StringField(required=True)
    service_type = ObjectIdField(null=True)

    date = DateTimeField(required=True)


class DenormalizedAccrual(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    month = DateTimeField()
    date = DateTimeField()
    wrong_debt = DynamicField(db_field="_wrong_debt")

    def __str__(self):
        return "DenormalizedAccrual {id} : {month}".format(
            id=self.id,
            month=self.month,
        )


class OffsetOperationAccount:
    BANK = 0  # операции по расчётному счёту (51)
    OWN_SERVICE = 1  # оказанние услуг ЖКХ (86)
    CORRECTION = 2  # транзит для корректировок платежей
    CORRECTION_SERVICE = 3  # транзит для корректировок возвратов

    SERVICE_DEBT = 4  # задолженность по услуге (76.5)
    ADVANCE_PAYMENT = 5  # авансовые платежи (62.2.1)
    ADVANCE_REFUND = 6  # авансы, созданные возвратами (немыслимое) (62.2.2)


class OffsetOperation:
    PAYMENT = (  # платёж за услугу
        OffsetOperationAccount.BANK,  # 0
        OffsetOperationAccount.SERVICE_DEBT,  # 4
    )
    REFUND = (  # возврат по услуге
        OffsetOperationAccount.OWN_SERVICE,  # 1
        OffsetOperationAccount.SERVICE_DEBT,  # 4
    )
    PAYMENT_ADVANCE = (  # авансовый платёж
        OffsetOperationAccount.BANK,  # 0
        OffsetOperationAccount.ADVANCE_PAYMENT,  # 5
    )
    REFUND_ADVANCE = (  # возврат по услуге, ставший авансом (немыслимое)
        OffsetOperationAccount.OWN_SERVICE,  # 1
        OffsetOperationAccount.ADVANCE_REFUND,  # 6
    )
    REDEEM_PAYMENT = (  # полное сторно платежа (возврат без корректировки)
        OffsetOperationAccount.SERVICE_DEBT,  # 4
        OffsetOperationAccount.BANK,  # 0
    )
    REVERSE_PAYMENT = (  # сторно платежа
        OffsetOperationAccount.SERVICE_DEBT,  # 4
        OffsetOperationAccount.CORRECTION,  # 2
    )
    REASSIGN_PAYMENT = (  # перераспределение сторнированного платежа
        OffsetOperationAccount.CORRECTION,  # 2
        OffsetOperationAccount.SERVICE_DEBT,  # 4
    )
    REASSIGN_PAYMENT_ADVANCE = (  # аванс при перераспределении сторно платежа
        OffsetOperationAccount.CORRECTION,  # 2
        OffsetOperationAccount.ADVANCE_REFUND,  # 6
    )
    REVERSE_REFUND = (  # сторно возврата (например, услуга-сальдо)
        OffsetOperationAccount.SERVICE_DEBT,  # 4
        OffsetOperationAccount.CORRECTION_SERVICE,  # 3
    )
    REASSIGN_REFUND = (  # перераспределение сторнированного возврата
        OffsetOperationAccount.CORRECTION_SERVICE,  # 3
        OffsetOperationAccount.SERVICE_DEBT,  # 4
    )
    REASSIGN_REFUND_ADVANCE = (  # аванс при перераспределении сторно возврата
        OffsetOperationAccount.CORRECTION_SERVICE,  # 3
        OffsetOperationAccount.ADVANCE_REFUND,  # 6
    )
    REVERSE_REASSIGN_REFUND_ADVANCE = (  # сторно такого аванса
        OffsetOperationAccount.ADVANCE_REFUND,  # 6
        OffsetOperationAccount.CORRECTION_SERVICE,  # 3
    )
    REDEEM_ADVANCE_BY_PAYMENT = (  # сторно аванса путём сторно платежа
        OffsetOperationAccount.ADVANCE_PAYMENT,  # 5
        OffsetOperationAccount.BANK,  # 0
    )
    REVERSE_ADVANCE_BY_REFUND = (  # сторно аванса путём сторно немыслимого
        OffsetOperationAccount.ADVANCE_REFUND,  # 6
        OffsetOperationAccount.OWN_SERVICE,  # 1
    )
    PAYMENT_ADVANCE_REPAYMENT = (  # зачёт авансового платежа
        OffsetOperationAccount.ADVANCE_PAYMENT,  # 5
        OffsetOperationAccount.SERVICE_DEBT,  # 4
    )
    PAYMENT_ADVANCE_REPAYMENT_REDEEM = (  # отмена зачёта авансового платежа
        OffsetOperationAccount.SERVICE_DEBT,  # 4
        OffsetOperationAccount.ADVANCE_PAYMENT,  # 5
    )
    REFUND_ADVANCE_REPAYMENT = (  # зачёт аванса-возврата
        OffsetOperationAccount.ADVANCE_REFUND,  # 6
        OffsetOperationAccount.SERVICE_DEBT,  # 4
    )


# столбец "платежи"
PAYMENT_OFFSET_OPERATIONS = [
    OffsetOperation.PAYMENT,  # 0 - 4
    OffsetOperation.REDEEM_PAYMENT,  # 4 - 0
    OffsetOperation.PAYMENT_ADVANCE,  # 0 - 5
    OffsetOperation.REDEEM_ADVANCE_BY_PAYMENT,  # 5 - 0
    OffsetOperation.REVERSE_REASSIGN_REFUND_ADVANCE,  # 6 - 3
]
# столбец "платежи без аванса"
PAYMENT_NO_ADVANCE_OFFSET_OPERATIONS = [
    OffsetOperation.PAYMENT,  # 0 - 4
    OffsetOperation.REDEEM_PAYMENT,  # 4 - 0
]
# столбец "платежи авансом"
ADVANCE_PAYMENT_OFFSET_OPERATIONS = [
    OffsetOperation.PAYMENT_ADVANCE,  # 0 - 5
    OffsetOperation.REDEEM_ADVANCE_BY_PAYMENT,  # 5 - 0
    OffsetOperation.REVERSE_REASSIGN_REFUND_ADVANCE,  # 6 - 3
]
# столбец "возвраты"
REFUND_OFFSET_OPERATIONS = [
    OffsetOperation.REFUND,  # 1 - 4
    OffsetOperation.REFUND_ADVANCE,  # 1 - 6
    OffsetOperation.REVERSE_ADVANCE_BY_REFUND,  # 6 - 1
]
# столбец "корректировки"
CORRECTION_OFFSET_OPERATIONS = [
    OffsetOperation.REVERSE_PAYMENT,  # 4 - 2
    OffsetOperation.REASSIGN_PAYMENT,  # 2 - 4
    OffsetOperation.REASSIGN_PAYMENT_ADVANCE,  # 2 - 6
    OffsetOperation.REVERSE_REFUND,  # 4 - 3
    OffsetOperation.REASSIGN_REFUND,  # 3 - 4
    OffsetOperation.REASSIGN_REFUND_ADVANCE,  # 3 - 6
]
# столбец "зачёт аванса"
ADVANCE_REPAYMENT_OFFSET_OPERATIONS = [
    OffsetOperation.PAYMENT_ADVANCE_REPAYMENT,  # 5 - 4
    OffsetOperation.PAYMENT_ADVANCE_REPAYMENT_REDEEM,  # 4 - 5
    OffsetOperation.REFUND_ADVANCE_REPAYMENT,  # 6 - 4
]

ALL_OFFSET_OPERATIONS = (
    PAYMENT_OFFSET_OPERATIONS
    + REFUND_OFFSET_OPERATIONS
    + CORRECTION_OFFSET_OPERATIONS
    + ADVANCE_REPAYMENT_OFFSET_OPERATIONS
)


class Offset(ChangeBlockingMixin, BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Offsets',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            "_binds.pr",
            "accrual.id",
            "date",
            "refer.id",
            "refer.doc.provider",
            "refer.account.id",
            "refer.account.area.id",
            "refer.account.area.house.id",
            ("refer.id", "accrual.id", "accrual.month", "is_penalty"),
            'refer.doc.date',
            {
                "name": "turnovers_all",
                "fields": (
                    "_binds.pr",
                    "doc_date",
                    "op_debit",
                    "op_credit",
                ),
            },
            {
                "name": "turnovers_house",
                "fields": (
                    "refer.account.area.house.id",
                    "doc_date",
                    "op_debit",
                    "op_credit",
                ),
            },
        ],
    }

    idle = IntField(verbose_data="Остаток от распределения")
    total = IntField(verbose_data="Общая сумма долга")
    accrual = EmbeddedDocumentField(DenormalizedAccrual, required=True)
    services = EmbeddedDocumentListField(ServiceTypeAsEmbedded)
    advance_vendor = EmbeddedDocumentField(
        VendorEmbedded,
        verbose_name='Временно поставщик аванса'
    )
    date = DateTimeField(verbose_data="Дата операции")
    doc_date = DateTimeField(verbose_data="Дата операции по приходу")
    created = DateTimeField(
        required=True,
        default=datetime.now,
        db_field="created_at",
    )
    is_penalty = BooleanField(
        default=False,
        required=True,
        db_field="is_pennies",
    )
    penalty_days = IntField(min_value=0, required=True, db_field="pennies_days")

    offset_kind = ListField(StringField(), db_field='_type')
    op_debit = IntField(
        verbose_data="Код счёта бухгалтерской операции по дебету",
    )
    op_credit = IntField(
        verbose_data="Код счёта бухгалтерской операции по кредиту",
    )
    value_in_credit = BooleanField(verbose_data="Суммы для счёта кредита")

    refer = EmbeddedDocumentField(DenormalizedPaymentOrAccrual)
    is_self_repaid = BooleanField()
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    doc = DictField()

    def __str__(self):
        return self.to_json()

    def save(self, *args, **kwargs):
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        self.restrict_changes()
        super().save(*args, **kwargs)

    def _get_providers_binds(self):
        return [self.refer.doc['provider']]

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
            refer__doc__provider__nin=[p[0] for p in masters_houses] + [provider_id],
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id, full_result=True)
        pulled += res.modified_count
        # добавиться в свои документы
        res = cls.objects(
            refer__doc__provider=provider_id,
        ).update(add_to_set___binds__pr=provider_id, full_result=True)
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
                'refer.doc.provider': master_id,
                'refer.account.area.house._id': {'$nin': houses}
            },
        ).distinct(
            'refer.account.area.house._id',
        )

        if force:
            houses_allow = houses
        else:
            houses_allow = cls.objects(
                __raw__={
                    '_binds.pr': {'$ne': slave_id},
                    'refer.doc.provider': master_id,  # todo: Лишнее?
                    'refer.account.area.house._id': {'$in': houses}
                },
            ).distinct(
                'refer.account.area.house._id'
            )

        # удалиться из запрещённых домов
        for h in houses_disallow:
            res = cls.objects(__raw__={
                'refer.doc.provider': master_id,
                '_binds.pr': slave_id,
                'refer.account.area.house._id': h,
            }).update(
                pull___binds__pr=slave_id,
                full_result=True,
            )
            pulled += res.modified_count
        # добавиться в разрешённые дома
        for h in houses_allow:
            res = cls.objects(__raw__={
                'refer.doc.provider': master_id,
                'refer.account.area.house._id': h,
            }).update(
                add_to_set___binds__pr=slave_id,
                full_result=True,
            )
            pushed += res.modified_count
        return pushed, pulled

    @classmethod
    def block_documents(cls, offset_id):
        """ Блокировка платежных документов после прикрепления к выписке """

        offset = cls.objects(id=offset_id, lock__exists=False)
        if not offset:
            return
        offset.update(lock=True)
        # TODO Дополнить родительским документом

