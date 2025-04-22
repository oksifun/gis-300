from datetime import datetime
from decimal import Decimal

from bson import ObjectId
from dateutil.relativedelta import relativedelta
from mongoengine import (
    Document, EmbeddedDocumentField, EmbeddedDocument, ReferenceField,
    DateTimeField, IntField, StringField, BooleanField, ObjectIdField,
    DictField, ListField, FloatField, ValidationError,
)

from app.payment.core.utils import update_accrual_doc_payers_count
from app.payment.models.denormalization.embedded_docs import \
    DenormalizedPaymentDoc
from lib.helpfull_tools import DateHelpFulls as dhf
from processing.locks import acquire_accounts_task_locks, \
    release_accounts_task_locks
from processing.models.billing.account import Tenant
from processing.models.billing.base import BindedModelMixin, ProviderBinds, \
    RelationsProviderBindsProcessingMixin, ChangeBlockingMixin
from processing.models.billing.embeddeds.tenant import DenormalizedTenant
from processing.models.billing.files import Files
from processing.models.choices import *

TOTAL_CHANGES = [
    'totals.value',
    'totals.fee',
    'totals.count',
    'totals.count_fiscalized',
    'description',
    'settings',
]

SUM_BANK_FEE_CHANGES = ['sum_bank_fee',
                        'totals.value',
                        'totals.fee',
                        'totals.count',
                        'totals.count_fiscalized',
                        'description',
                        'settings',
                        ]

LOST_DOCS = {
    "LostDoc",
    "LostMemorialOrderDoc",
    "LostBankOrderDoc",
    "LostCollectionOrderDoc",
}

LOST_TYPES = {
    'LostDoc': 'ManualDoc',
    'LostBankOrderDoc': 'BankOrderDoc',
    'LostMemorialOrderDoc': 'MemorialOrderDoc',
    'LostCollectionOrderDoc': 'CollectionOrderDoc',
}


class PaymentDocTotalData(EmbeddedDocument):
    value = IntField(
        required=True,
        default=0,
        verbose_name='Общая сумма платежей',
    )
    fee = IntField(
        required=True,
        default=0,
        verbose_name='Сумма комиссии',
    )
    count = IntField(
        required=True,
        default=0,
        verbose_name='Общее количество платежей',
    )
    count_fiscalized = IntField(
        required=True,
        default=0,
        verbose_name='Количество фискализированных платежей',
    )


class Payment(ChangeBlockingMixin, RelationsProviderBindsProcessingMixin,
              BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Payment',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.pr',
            'debt',
            'account.id',
            'account.area.id',
            'created_at',
            'doc.id',
            'doc.date',
            'doc.provider',
            ('doc.provider', 'doc.date'),
            ('doc.provider', 'date'),
            ('account.area.house.id', 'doc.provider'),
        ],
    }
    _OFFSETS_TASKS_START_FIELDS = {
        'value',
        'sector_code',
        'is_deleted',
        'date',
        'doc',
        'month',
    }
    auto_payment = BooleanField(
        default=False,
        verbose_name='Оплата совершена автоплатежом'
    )
    doc = EmbeddedDocumentField(
        DenormalizedPaymentDoc,
        required=True,
        verbose_name="Входит в платежное поручение"
    )
    date = DateTimeField(required=True, verbose_name="Дата оплаты")
    value = IntField(verbose_name="Сумма оплаты")

    month = DateTimeField(verbose_name="Месяц, за который производится оплата")

    account = EmbeddedDocumentField(
        DenormalizedTenant,
        verbose_name="Жилец-плательщик"
    )
    sector_code = StringField(
        required=True,
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        default=AccrualsSectorType.RENT,
        verbose_name="Направление оплаты"
    )
    by_card = BooleanField(
        required=True,
        default=False,
        verbose_name="оплата пластиковой картой"
    )
    is_deleted = BooleanField(
        required=False,
        default=False,
        verbose_name="Без истории"
    )
    created_at = DateTimeField(
        required=True,
        default=datetime.now,
        verbose_name="время создания"
    )
    has_receipt = BooleanField(verbose_name="Есть чек об оплате?")
    # Плохая строка из реестра,
    # жуткий костыль на фоне имеющихся WrongLinePayment
    string = StringField()
    has_wrong_lines = BooleanField(
        required=False,
        default=False,
        null=True,
        verbose_name="Наличие плохой строки"
    )
    wrong_line = ObjectIdField(
        required=False,
        null=True,
        verbose_name='Ссылка на плохую строку',
    )
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )
    refund_of = ObjectIdField(
        verbose_name='Ссылка на оплату, которую нужно сторнировать'
    )
    refunded_by = ObjectIdField(
        verbose_name='Ссылка на оплату, которая сторнировала текущий документ'
    )
    redeemed = IntField()

    # устаревшие поля (неиспользуемые)
    debt = ObjectIdField(verbose_name="Погашаемое начисление")

    @classmethod
    def create_refund_payment(cls, payment_ref, date=None, account=None):
        payment = cls.objects.get(id=payment_ref)
        if payment.refund_of:
            raise ValidationError('Can\'t refund a refund payment.')

        if payment.refunded_by:
            raise ValidationError('Refund already exists.')

        if account:
            if not Tenant.objects(id=account).as_pymongo().count():
                raise ValidationError('Invalid account.')

        refund_payment = cls.create_payment_from_payment(
            payment=payment,
            exclude_fields={'lock', 'date', 'value'}
        )

        refund_payment.date = date or payment.date
        refund_payment.value = -payment.value
        refund_payment.refund_of = payment.id
        if account:
            refund_payment.account.id = account
        refund_payment.save(ignore_pd_lock_validation=True)
        cls.objects(id=payment_ref).update(refunded_by=refund_payment.id)
        return refund_payment

    @classmethod
    def create_payment_from_payment(cls, payment, exclude_fields=None):
        new_payment = cls()
        exclude_fields = set(exclude_fields) if exclude_fields else set()
        exclude_fields.update(['id'])
        for field in payment:
            if field not in exclude_fields:
                setattr(new_payment, field, getattr(payment, field))
        return new_payment

    def delete(self, **write_concern):
        self.check_change_permissions()
        if not self.is_deleted:
            self.is_deleted = True
            if self.has_wrong_lines:
                self.return_wrong_line()
                print(**write_concern)
                super().delete(**write_concern)
            else:
                self.save()
            self._check_lost_doc()

    def return_wrong_line(self):
        if not self.wrong_line:
            return
        wrong_line = WrongLinePayment.objects(
            id=self.wrong_line
        ).get()
        wrong_line.is_parsed = False
        wrong_line.save()
        return True

    def save(self, *args, **kwargs):

        self.check_change_permissions()
        doc = kwargs.get('payment_doc')
        if not doc:
            doc = PaymentDoc.objects(pk=self.doc.id).get()

        if not kwargs.get('ignore_pd_lock_validation'):
            if doc.lock and not self.add_wrong_line_payment():
                raise ValidationError('Document is locked')

        if self._created:
            self._denormalize_doc(doc)

        if not kwargs.get('account_attached'):
            if self._created or self._is_key_dirty('account'):
                self._denormalize_account()

        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())

        self.restrict_changes()
        need_recalc = (
                not self._created
                and {'value', 'has_receipt', 'is_deleted'}
                - set(self._changed_fields)
        )
        need_increment = self._created and not need_recalc
        self.parsed_wrong_line()
        self._normalize_month()
        super().save(*args, **kwargs)
        if self.account:
            self.update_payers_count()
        if not kwargs.get('omit_total_update'):
            self.update_doc_totals(doc, need_recalc, need_increment)

    def parsed_wrong_line(self):
        if self._created and self.wrong_line:
            self.has_wrong_lines = True
            wrong_line = WrongLinePayment.objects(id=self.wrong_line).first()
            if not wrong_line:
                raise ValidationError('Такой плохой строки не существует')
            wrong_line.is_parsed = True
            wrong_line.save()

    def add_wrong_line_payment(self):
        wrong_line = WrongLinePayment.objects(
            doc__id=self.doc.id,
            is_parsed__ne=True,
        ).as_pymongo().only('id').first()
        if wrong_line and self._created or not self.lock:
            return True

    def _normalize_month(self):
        if self._created or self._is_key_dirty('month'):
            self.month = dhf.begin_of_month(self.month)

    def _denormalize_doc(self, doc):
        for field in DenormalizedPaymentDoc._fields_ordered:
            attr = (
                getattr(getattr(doc, field), 'id')
                if field == 'bank' and getattr(doc, field)
                else getattr(doc, field)
            )
            setattr(self.doc, field, attr)

    def _denormalize_account(self):
        if self.account:
            tenant = Tenant.objects(pk=self.account.id).get()
            self.account = DenormalizedTenant.from_ref(tenant)

    def update_payers_count(self):
        return update_accrual_doc_payers_count(self)

    def update_doc_totals(self, doc, need_recalc, need_increment):
        if need_recalc:
            doc.calculate_totals()
            doc.save()
        if need_increment:
            set_dict = {
                'inc__totals__value': self.value,
                'inc__totals__count': 1,
            }
            if doc.bank_fee:
                set_dict['inc__totals__fee'] = round(
                    self.value * doc.bank_fee / 100,
                )
            PaymentDoc.objects(
                pk=doc.pk,
            ).update(
                **set_dict,
            )

    @classmethod
    def mark_as_fiscalized(cls, payment_id):
        query_set = cls.objects(pk=payment_id)
        query_set.update(has_receipt=True)
        doc = query_set.as_pymongo().only('doc.id').get()
        receipts = cls.objects(
            doc__id=doc['doc']['_id'],
            has_receipt=True,
            is_deleted__ne=True,
        ).count()
        PaymentDoc.objects(
            pk=doc['doc']['_id'],
        ).update(
            totals__count_fiscalized=receipts,
        )

    def update(self, *args, **kwargs):
        self.check_change_permissions()
        super().update(**kwargs)

    def _check_lost_doc(self):
        if self.account and self.account.id:
            return
        other_payments = Payment.objects(
            doc__id=self.doc.id,
            pk__ne=self.pk,
            is_deleted__ne=True,
        ).as_pymongo().first()
        if other_payments:
            return
        doc = PaymentDoc.objects(pk=self.doc.id).get()
        doc.delete()


class DenormalizedSettings(EmbeddedDocument):
    recalculation_period = DateTimeField(
        null=True,
    )


class PaymentDoc(ChangeBlockingMixin, Document, BindedModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'PaymentDoc',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('_binds.pr', '-date'),
            'bank_statement',
            ('bank_number', '-date'),
            'file.id',
            ('provider', 'settings.recalculation_period')
        ],
    }
    # Поле для подсчета суммы комиссий в разборе банковской выписки
    pd_sum_bank_fee = 0

    provider = ReferenceField(
        'processing.models.billing.provider.Provider',
        verbose_name="Организация-владелец "
                     "(для системных ПП это поле отсутствует)"
    )
    bank_fee = FloatField(vervbose_name="Комиссия банка")
    date = DateTimeField(vervbose_name="Дата документа", required=True)
    registry_number = StringField(vervbose_name="Номер документа оплаты")
    bank = ReferenceField(
        'processing.models.billing.provider.BankProvider',
        null=True,
        verbose_name="ссылка на банк",
    )
    bank_number = StringField(
        null=True,
        verbose_name="Расчетный счет, на который поступила оплата",
    )
    description = StringField(
        null=True,
        verbose_name="Текстовое описание документа"
    )
    bank_statement = ObjectIdField(
        null=True,
        verbose_name='Ссылка на выписку банка',
    )

    totals = EmbeddedDocumentField(
        PaymentDocTotalData,
        default=PaymentDocTotalData
    )

    file = EmbeddedDocumentField(Files)

    # Вложенные
    _type = ListField(StringField(), required=True)
    settings = EmbeddedDocumentField(
        DenormalizedSettings,
        null=True,
    )
    has_wrong_lines = BooleanField()
    bank_compared = BooleanField(
        required=True,
        default=False,
        verbose_name='Сверено ли с выпиской банка',
    )
    compared_at = DateTimeField(verbose_name='Время сверки с выпиской')
    fiscalization_at = DateTimeField(verbose_name='Время запуска фискализации')
    sum_bank_fee = IntField(verbose_name='sum_bank_fee')
    parent = StringField(
        choices=PAYMENT_DOC_PARENTS_CHOICES,
        verbose_name='Место создания документа'
    )
    device = IntField(
        verbose_name='Номер кассы которая будет использоваться для фискализации'
    )

    is_deleted = BooleanField()

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    def __init__(self, *args, **values):
        super().__init__(*args, **values)
        self._device = self.device
        self._primal_type = [*self._type]

    @property
    def total_value_with_bank_fee(self):
        return round(self.totals.value * (100 - Decimal(self.bank_fee)) / 100)

    def save(self, *args, **kwargs):
        self.check_change_permissions()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        self.restrict_changes()
        self.denormalize()
        # Поставим сверку выписке
        self.set_compared_state()
        self.validate_device()
        if not self.parent:
            self.parent = 'Manual'
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.check_change_permissions()
        if not self.is_deleted:
            bank_statement = self.bank_statement
            self.is_deleted = True
            self.fiscalization_at = None
            self.compared_at = None
            self.bank_compared = False
            self.bank_statement = None
            self._delete_payments()
            self.save()

    def check_change_permissions(self):
        """
        Проверяет, не изменились ли калие-либо поля, кроме 'description' и
        'settings'
        Если 'description' и/или 'settings' изменены, то разрешает вводить
        изменения в фискализированный документ
        """
        if set(self._get_changed_fields()).difference(TOTAL_CHANGES):
            if not set(self._get_changed_fields()).difference(
                    SUM_BANK_FEE_CHANGES):
                sum_bank_fee = PaymentDoc.objects(id=self.id).first()[
                    'sum_bank_fee']
                if sum_bank_fee is None and self.sum_bank_fee == 0:
                    return
            super().check_change_permissions()

        return

    def set_compared_state(self):
        """Установка в банковскую выписку, что она сверена"""
        if self._created and self.bank_statement:
            self.bank_compared = True
            if not self.compared_at:
                self.compared_at = datetime.now()

    def calculate_totals(self, payments=None, commercials=None):
        """
        Денормализация поля totals. Расчёт суммарных данных документа оплат
        """
        if self.totals is None:
            self.totals = PaymentDocTotalData()
        if payments is None:
            payments = self._get_payments_for_sum()
        self.totals.value = (
                sum(p['value'] for p in payments)
                + sum(p['value'] for p in commercials)
                + self._get_wrong_lines_sum()
        )
        if self.sum_bank_fee:
            self.totals.fee = self.totals.value - self.sum_bank_fee
        elif self.bank_fee:
            self.totals.fee = round(self.totals.value * self.bank_fee / 100)
        else:
            self.totals.fee = 0
        self.totals.count = len(payments) + len(commercials)
        self.totals.count_fiscalized = 0
        if payments:
            if isinstance(payments[0], dict):
                self.totals.count_fiscalized = len(
                    [
                        pay.get('has_receipt')
                        for pay in payments
                        if pay.get('has_receipt')
                    ],
                )
            else:
                self.totals.count_fiscalized = len(
                    [
                        True
                        for pay in payments
                        if pay.has_receipt
                    ],
                )
        if commercials:
            if isinstance(commercials[0], dict):
                self.totals.count_fiscalized += len(
                    [
                        pay.get('has_receipt')
                        for pay in commercials
                        if pay.get('has_receipt')
                    ],
                )
            else:
                self.totals.count_fiscalized += len(
                    [
                        True
                        for pay in commercials
                        if pay.has_receipt
                    ],
                )

    def _get_wrong_lines_sum(self):
        query = dict(doc__id=self.id, is_parsed=False)
        return WrongLinePayment.objects(**query).sum('value')

    def _get_payments_for_sum(self):
        return list(
            Payment.objects(
                doc__id=self.id,
                is_deleted__ne=True,
            ).only(
                'value',
                'has_receipt',
            ).as_pymongo()
        )

    def denormalize(self):
        if self._created or 'date' in self._changed_fields:
            self.date = self.date.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            if not self._created:
                Payment.objects(doc__id=self.pk).update(doc__date=self.date)
        if self._created or 'bank_statement' in self._changed_fields:
            self.bank_compared = self.bank_statement is not None
        if (
                not self._created
                and {'bank_fee', 'sum_bank_fee'} & set(self._changed_fields)
        ):
            self.calculate_totals()

    def _delete_payments(self):
        Payment.objects(
            doc__id=self.id,
            is_deleted__ne=True,
        ).update(
            is_deleted=True,
        )

    def _get_providers_binds(self):
        return [
            self.provider
            if isinstance(self.provider, ObjectId)
            else self.provider.id
        ]

    @classmethod
    def lock_document(cls, pd_id, lock_bsd=True, force=False):
        """ Блокировка платежных документов после прикрепления к выписке """
        from app.offsets.models.offset import Offset
        from processing.models.billing.accrual import Accrual
        accounts = Payment.objects(doc__id=pd_id).distinct('account.id')
        if not accounts:
            raise ValidationError('Нельзя фискализировать пустой документ')
        locks = acquire_accounts_task_locks(
            f'PaymentDoc.lock_document.{pd_id}',
            accounts,
        )
        try:
            if force:
                pd = cls.objects(id=pd_id, is_deleted__ne=True)
            else:
                pd = cls.objects(
                    id=pd_id,
                    bank_compared=True,
                    has_wrong_lines__ne=True,
                    is_deleted__ne=True,
                )
            pd = pd.only('id', 'bank_statement').first()
            if not pd:
                return False
            pd.update(lock=True)
            # Блокировка его оплат
            payments = Payment.objects(doc__id=pd_id)
            payments.update(lock=True)
            # Блокировка Offset
            query = dict(
                __raw__={
                    'refer._id': {
                        '$in': [
                            x['_id']
                            for x in payments.only('id').as_pymongo()
                        ],
                    },
                },
            )
            offsets = Offset.objects(**query)
            offsets.update(lock=True)
            # Блокировка начислений
            accruals = [
                z['accrual']['_id']
                for z in offsets.only('accrual.id').as_pymongo()
                if z.get('accrual') and z['accrual'].get('_id')
            ]
            Accrual.objects(id__in=accruals).update(lock=True)
            return True
        finally:
            if locks:
                release_accounts_task_locks(locks)

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            provider__ne=provider_id,
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id)
        pushed = cls.objects(
            provider=provider_id,
        ).update(add_to_set___binds__pr=provider_id)
        return pushed, pulled

    def validate_device(self):
        """
        Поле не должно быть удалено, если есть хотя бы одна оплата и не должно
        быть сохранено, если это не приходной кассовый ордер
        """
        if 'CashReceiptDoc' not in self._type:
            delattr(self, 'device')
            return

        if self._device and self._device != self.device:
            raise ValidationError('Yoy have no power to change a device.')


class WrongLinePayment(Document):
    """
    Запись об ошибке при попытке разбора строки оплаты реестра
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ErrorLog'
    }

    _type = ListField(StringField(), required=True)
    string = StringField(required=True)
    doc = EmbeddedDocumentField(
        DenormalizedPaymentDoc,
        required=True,
        verbose_name='Документ оплаты'
    )
    is_parsed = BooleanField(required=True)
    date = DateTimeField()
    value = FloatField()
    month = DateTimeField()
    number = StringField()
    account = ObjectIdField()
    name = StringField()
    address = StringField()

    def save(self, *args, **kwargs):
        after_save_decrement = (
            True
            if self.is_parsed and 'is_parsed' in self._changed_fields
            else False
        )
        after_save_increment = self._created and not self.is_parsed
        result = super().save(*args, **kwargs)
        if after_save_decrement:
            self.decrement_wrong_value()
        if after_save_increment:
            self.increment_wrong_value()
        return result

    def decrement_wrong_value(self):
        """
        Убирает из totals документа оплат сумму, которая туда попала,
        когда строка была еще не разобрана
        """
        pd = PaymentDoc.objects(pk=self.doc.id).get()
        updater = dict(dec__totals__value=self.value)
        if pd.has_wrong_lines:
            wrong_lines = self.__class__.objects(
                doc__id=pd.id,
                is_parsed=False
            ).count()
            if not wrong_lines:
                updater.update(set__has_wrong_lines=False)

        pd.update(**updater)

    def increment_wrong_value(self):
        """
        Добавляет в totals документа оплат сумму неправильной строки
        """
        PaymentDoc.objects(pk=self.doc.id).update(inc__totals__value=self.value)


class WrongLineReadings(Document):
    """
    Запись об ошибке при попытке разбора строки показаний счётчиков реестра
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ErrorLog'
    }

    _type = ListField(StringField(), required=True)
    area = DictField()
    wrong_line = StringField()
    registry_number = StringField()
    date_reg = DateTimeField()
    date_doc = DateTimeField()
    date = DateTimeField()
    month = DateTimeField()
    meters = ListField(DictField())
    errors = ListField(StringField())
