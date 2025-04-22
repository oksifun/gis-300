from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from bson import ObjectId
from mongoengine import Document, ReferenceField, DateTimeField, StringField, \
    ObjectIdField, EmbeddedDocument, ListField, BooleanField, IntField, \
    EmbeddedDocumentField, DictField, EmbeddedDocumentListField

from processing.models.billing.base import FilesDeletionMixin
from processing.models.billing.files import Files
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES, \
    AccrualsSectorType
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID, EIS24_PROVIDER_OBJECT_ID, \
    KOTOLUP_PROVIDER_OBJECT_ID, SEMENCOVA_PROVIDER_OBJECT_ID


class OwnAgreementDuration(object):
    PROLONG = 'prolong'
    NOTIFICATION_MONTHS = 'notification_months'
    NOTIFICATION_DAYS = 'notification_days'


AFTER_DURATION_ACTION = (
    (OwnAgreementDuration.PROLONG, 'Автоматическая пролонгация'),
    (OwnAgreementDuration.NOTIFICATION_MONTHS, 'уведомление (месяцы)'),
    (OwnAgreementDuration.NOTIFICATION_DAYS, 'уведомление (дни)'),
)


class OwnAgreementServiceObject(object):
    SQUARE_METER = 'square_meter'
    ACCOUNT = 'account'
    PARKING_SPACE = 'parking_space'
    ORGANIZATION = 'organization'


AGREEMENT_SERVICE_OBJECTS = (
    (OwnAgreementServiceObject.SQUARE_METER, 'с кв.м'),
    (OwnAgreementServiceObject.ACCOUNT, 'с л/с'),
    (OwnAgreementServiceObject.ORGANIZATION, 'с организации'),
)


class OwnContractState(object):
    SENT_FOR_APPROVAL = 'sent_for_approval'
    SIGNED_BY_US = 'signed_by_us_in_the_office'
    GIVEN_FOR_SIGN = 'given_to_the_customer_for_signature'
    MAILED = 'mailed'
    SIGNED_BY_CLIENT_CLIENT = 'signed_by_the_client_the_client'
    SIGNED_BY_CLIENT_OFFICE = 'signed_by_the_client_in_the_office'
    CANCELLED = 'cancelled'


OWN_CONTRACT_STATES = (
    (OwnContractState.SENT_FOR_APPROVAL, 'Отправлен на согласование'),
    (OwnContractState.SIGNED_BY_US, 'Подписан нами, в офисе'),
    (OwnContractState.GIVEN_FOR_SIGN, 'Отдан клиенту на подпись'),
    (OwnContractState.MAILED, 'Отправлен по почте'),
    (OwnContractState.SIGNED_BY_CLIENT_CLIENT, 'Подписан клиентом, у клиента'),
    (OwnContractState.SIGNED_BY_CLIENT_OFFICE, 'Подписан клиентом, в офисе'),
    (OwnContractState.CANCELLED, 'Аннулирован'),
)


class ContractSelectTypes(object):
    SERVICE = 'service'
    ADVANCE = 'advance'
    PENALTIES = 'penalties'


CONTRACT_SELECT_TYPES = (
    (ContractSelectTypes.SERVICE, 'Услуга'),
    (ContractSelectTypes.ADVANCE, 'Аванс'),
    (ContractSelectTypes.PENALTIES, 'Пени'),
)


class ContractOwners(object):
    ZAO_OTDEL = ZAO_OTDEL_PROVIDER_OBJECT_ID
    EIS24 = EIS24_PROVIDER_OBJECT_ID
    IP_KOTOLUP = KOTOLUP_PROVIDER_OBJECT_ID
    IP_SEMENCOVA = SEMENCOVA_PROVIDER_OBJECT_ID


CONTRACT_OWNERS = (
    (ContractOwners.ZAO_OTDEL, 'ЗАО "Отдел"'),
    (ContractOwners.EIS24, 'ООО ЕИС ЖКХ'),
    (ContractOwners.IP_KOTOLUP, 'ИП Котолуп В.В.'),
    (ContractOwners.IP_SEMENCOVA, 'ИП Семенцова О.В.'),
)


class OwnAgreementService(EmbeddedDocument):
    service = ReferenceField(
        'processing.models.billing.services_handbook.OwnServiceHandbook',
        verbose_name='Ссылка на справочник услуг',
    )
    price = IntField(required=True)
    obj = StringField(
        required=True,
        choices=AGREEMENT_SERVICE_OBJECTS,
        verbose_name='Объект применения цены',
    )
    sector = StringField(
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        default=AccrualsSectorType.RENT,
        verbose_name='Направление начислений',
    )
    date_from = DateTimeField(required=True, verbose_name='Дата начала')
    date_till = DateTimeField(
        null=True,
        verbose_name='Дата окончания',
    )
    house = ReferenceField(
        'app.house.models.house.House',
        null=True,
        verbose_name='Дом',
    )
    living_areas = BooleanField(
        null=True,
        verbose_name='Включая квартиры',
    )
    not_living_areas = BooleanField(
        null=True,
        verbose_name='Включая нежилые помещения',
    )
    parking_areas = BooleanField(
        null=True,
        verbose_name='Включая машиноместа паркинга',
    )
    consider_developer = BooleanField(
        default=False,
        verbose_name='Учитывать ли ЛС застройщика '
                     'при выставлении документов в 1С'
    )


class ContractFiles(EmbeddedDocument):
    original = EmbeddedDocumentListField(
        Files,
        max_length=30,
        default=[],
        verbose_name='Оригинал .doc'
    )
    scan = EmbeddedDocumentListField(
        Files,
        max_length=30,
        default=[],
        verbose_name='Скан .pdf'
    )


class DurationEmbedded(EmbeddedDocument):
    date = DateTimeField(
        required=True,
        verbose_name='Дата окончания'
    )
    actual_date = DateTimeField(verbose_name='Фактическая дата')
    action = StringField(
        choices=AFTER_DURATION_ACTION,
        verbose_name='Действие по окончанию'
    )
    quantity = IntField(
        null=True,
        verbose_name='Количество дней/месяцев за которое требуется уведомление'
    )

    @property
    def left(self) -> timedelta:
        """Осталось до прекращения действия договора"""
        return self.date - datetime.now()  # required

    @property
    def is_expired(self) -> bool:
        """Срок действия договора истек?"""
        return self.left.days < 1

    @property
    def notification(self) -> bool:
        """Предупреждение о прекращении договора?"""
        if self.quantity is None:
            return False

        if self.action == OwnAgreementDuration.NOTIFICATION_DAYS:
            delta = relativedelta(days=self.quantity)
        elif self.action == OwnAgreementDuration.NOTIFICATION_MONTHS:
            delta = relativedelta(months=self.quantity)
        else:  # OwnAgreementDuration.PROLONG
            return False

        return datetime.now() + delta >= self.date


class OwnAgreement(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True)
    number = StringField(required=True, verbose_name='Номер соглашения')
    date = DateTimeField(required=True, verbose_name='Дата соглашения')
    services = ListField(
        EmbeddedDocumentField(OwnAgreementService),
        default=[],
        verbose_name='Услуги',
    )
    file = EmbeddedDocumentField(
        ContractFiles,
        verbose_name='Оригинал и скан документа',
        default=ContractFiles()
    )
    state = StringField(null=True, choices=OWN_CONTRACT_STATES)
    lock_state = StringField(
        choices=(
            'blocked',
            'edit'
        ),
        verbose_name='Заблокирован ли документ'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.id:
            self.id = ObjectId()


class BalanceEmbedded(EmbeddedDocument):
    value = IntField(
        verbose_name='Сальдо',
        default=0
    )
    updated = DateTimeField(
        verbose_name='Дата последнего обновления',
        default=datetime.now
    )
    debtor_date = DateTimeField(
        verbose_name='Активация счетчика',
        null=True
    )


class ArchiveDocuments(EmbeddedDocument):
    uuid = ObjectIdField(
        null=True,
        verbose_name='file_id в GridFS'
    )
    state = StringField(
        choices=(
            'failed',
            'ready',
            'wip',
        ),
        verbose_name='Состояние работы с документом'
    )
    description = StringField(
        null=True,
        verbose_name='Описание ошибок возникающих при '
                     'обновлении комплекта документов'
    )
    updated = DateTimeField(
        default=datetime.now,
        verbose_name='Дата последнего обновления'
    )
    params = DictField(verbose_name='JSON, который ушел в запросе к 1С')


class DocumentStackEmbedded(EmbeddedDocument):
    act = EmbeddedDocumentField(
        ArchiveDocuments,
        verbose_name='Акт сверки'
    )
    bill = EmbeddedDocumentField(
        ArchiveDocuments,
        verbose_name='Архивного счета и акта выполненных работ'
    )


class OwnContract(FilesDeletionMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'OwnContract',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'client',
            ('owner', 'client'),
        ],
    }

    created = DateTimeField(
        default=datetime.now,
        verbose_name='Дата создания документа'
    )
    owner = ObjectIdField(
        required=True,
        verbose_name='Ссылка на организацию-владельца',
    )
    client = ObjectIdField(
        required=True,
        verbose_name='Ссылка на организацию-клиента',
    )
    number = StringField(required=True, verbose_name='Номер договора')
    date = DateTimeField(required=True, verbose_name='Дата договора')
    file = EmbeddedDocumentField(
        ContractFiles,
        verbose_name='Оригинал и скан документа'
    )
    state = StringField(null=True, choices=OWN_CONTRACT_STATES)
    agreements = ListField(
        EmbeddedDocumentField(OwnAgreement),
        verbose_name='Соглашения к договору'
    )
    duration = EmbeddedDocumentField(
        DurationEmbedded,
        required=True,
        verbose_name='Срок действия'
    )
    balance = EmbeddedDocumentField(
        BalanceEmbedded,
        default=BalanceEmbedded(),
        verbose_name='Сальдо'
    )
    is_deleted = BooleanField(default=False)
    doc_stack = EmbeddedDocumentField(
        DocumentStackEmbedded,
        verbose_name='Комплект запрашиваемых документов'
    )

    def save(self, *arg, **kwargs):
        self.set_balances_dates()
        self.set_actual_date()
        self.set_doc_stack_dates()
        super().save(*arg, **kwargs)

    def set_actual_date(self):
        if self._created:
            self.duration.actual_date = self.duration.date
        # Если изменили дату в существующем документе
        elif 'date' in self.duration._changed_fields:
            self.duration.actual_date = self.duration.date

    def set_balances_dates(self):
        # Нет смысла в проверке, если нет баланса
        if self.balance:
            if self.balance._created or 'value' in self.balance._changed_fields:
                self.balance.updated = datetime.now()

    def set_doc_stack_dates(self):
        # Добавление даты в акт при обновлении
        if self.doc_stack:
            if (
                    self.doc_stack.act
                    and 'uuid' in self.doc_stack.act._changed_fields
            ):
                self.doc_stack.act.updated = datetime.now()

            # Добавление даты в счет и др. архивные документы при обновлении
            if (
                    self.doc_stack.bill
                    and 'uuid' in self.doc_stack.bill._changed_fields
            ):
                self.doc_stack.bill.updated = datetime.now()
