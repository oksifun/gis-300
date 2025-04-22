from datetime import datetime

from bson import ObjectId
from mongoengine import (BooleanField, DateTimeField, Document, DynamicField,
                         EmbeddedDocument, EmbeddedDocumentField,
                         EmbeddedDocumentListField,
                         ListField, ObjectIdField, ReferenceField, StringField)

from app.personnel.models.denormalization.worker import DepartmentEmbedded
from app.personnel.models.denormalization.caller import (
    AccountEmbeddedPosition,
    ProviderEmbedded)
from processing.models.billing.base import ForeignDenormalizeModelMixin
from processing.models.billing.business_type import BusinessType
from processing.models.billing.embeddeds.address import Address
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.files import Files
from processing.models.choices import (CalcSoftwareType,
                                       CALC_SOFTWARE_TYPE_CHOICES,
                                       LEGAL_FORM_TYPE_CHOICES,
                                       PrintReceiptType,
                                       PRINT_RECEIPT_TYPE_CHOICES,
                                       ProviderTicketRate,
                                       PROVIDER_TICKET_RATES_CHOICES,
                                       SUPPORT_TICKET_STATUS_CHOICES,
                                       SupportTicketStatus, TicketType,
                                       TICKET_TYPE_CHOICES)
from processing.models.billing.provider.embeddeds import (
    EmbeddedMajorWorker,
    AnsweringPersonEmbedded,
    SaleTaskAnsweringPersonEmbedded,
    ProviderCallEmbedded)
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from django.conf import settings as django_settings


class EventType:
    INCOMING_CALL = 'incoming_call'
    OUT_COMING_CALL = 'out_coming_call'
    MEETING = 'meeting'
    INFORMATION = 'information'
    EMAIL = 'email'


EVENT_TYPE = (
    (EventType.INCOMING_CALL, 'Входящий звонок'),
    (EventType.OUT_COMING_CALL, 'Исходящий звонок'),
    (EventType.MEETING, 'Встреча'),
    (EventType.INFORMATION, 'Информация'),
    (EventType.EMAIL, 'E-Mail')
)


class CRMEventType:
    ACTION = 'Action'
    TASK = 'Task'
    SUPPORT_TICKET = 'SupportTicket'


CRM_EVENT_TYPE = (
    (CRMEventType.ACTION, 'Совершенное действие'),
    (CRMEventType.TASK, 'Запланированное действие'),
    (CRMEventType.SUPPORT_TICKET, 'Тикет тех. поддержки')
)


class EventResult:
    GOOD = 'good'
    BAD = 'bad'
    UNKNOWN = 'unknown'


EVENT_RESULT = (
    (EventResult.GOOD, 'хорошо'),
    (EventResult.BAD, 'плохо'),
    (EventResult.UNKNOWN, 'непонятно'),
)


class CRMStatus:
    NEW = 'new'
    COLD = 'cold'
    WORK = 'work'
    DENIED = 'denied'
    WRONG = 'wrong'
    ALIEN = 'alien'
    BAN = 'ban'
    CLIENT = 'client'
    PROSPECTIVE_CLIENT = 'prospective_client'
    PARTNER = 'partner'
    DEPARTURE = 'departure'
    AFTERSHOCK = 'aftershock'
    SENT = 'sent'
    CONTRACT = 'contract'
    DEBTOR = 'debtor'
    ARCHIVE = 'archive'


CRM_STATUS_CHOICE = (
    (CRMStatus.NEW, 'Новый'),
    (CRMStatus.COLD, 'Холодный'),
    (CRMStatus.WORK, 'В работе'),
    (CRMStatus.DENIED, 'Отказался'),
    (CRMStatus.WRONG, 'Недействующая'),
    (CRMStatus.ALIEN, 'Не наш клиент'),
    (CRMStatus.BAN, 'Запрет'),
    (CRMStatus.CLIENT, 'Клиент'),
    (CRMStatus.PROSPECTIVE_CLIENT, 'Потенциальный'),
    (CRMStatus.PARTNER, 'Партнер'),
    (CRMStatus.DEPARTURE, 'Выезд на адрес'),
    (CRMStatus.AFTERSHOCK, 'Дожимание'),
    (CRMStatus.SENT, 'Анкета отправлена'),
    (CRMStatus.CONTRACT, 'Договор/оплата'),
    (CRMStatus.DEBTOR, 'Должник'),
    (CRMStatus.ARCHIVE, 'Архивный'),
)

CAN_TENANT_ACCESS_STATUS = (CRMStatus.CLIENT, CRMStatus.DEBTOR)


class ProviderDenormalized(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Provider'

    id = ObjectIdField(db_field="_id", required=True)
    legal_form = StringField(choices=LEGAL_FORM_TYPE_CHOICES)
    name = StringField()
    str_name = StringField()
    ogrn = StringField(verbose_name='ОГРН')
    inn = StringField(verbose_name='ИНН')
    address = EmbeddedDocumentField(Address)
    email = StringField()
    phones = EmbeddedDocumentListField(DenormalizedPhone)
    business_types = ListField(
        ReferenceField(BusinessType),
        verbose_name="Список видов деятельности"
    )
    receipt_type = StringField(
        choices=PRINT_RECEIPT_TYPE_CHOICES,
        default=PrintReceiptType.UNKNOWN,
        null=True,
        verbose_name="печать квитанций"
    )
    calc_software = StringField(
        choices=CALC_SOFTWARE_TYPE_CHOICES,
        default=CalcSoftwareType.OTHER,
        null=True,
        verbose_name="расчет"
    )  # программа по расчету
    terminal = ListField(StringField())
    chief = EmbeddedDocumentField(EmbeddedMajorWorker)
    accountant = EmbeddedDocumentField(EmbeddedMajorWorker)
    redmine = DynamicField()
    okato = DynamicField()
    kpp = DynamicField()
    site = DynamicField()


class ProviderShortDenormalized(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Provider'

    id = ObjectIdField(db_field="_id", required=True)
    legal_form = StringField(choices=LEGAL_FORM_TYPE_CHOICES)
    address = EmbeddedDocumentField(Address)
    business_types = ListField(ReferenceField(BusinessType))
    receipt_type = StringField()
    calc_software = StringField()


class IdFieldEmbedded(DenormalizedEmbeddedMixin, EmbeddedDocument):
    id = ObjectIdField(required=True, db_field='_id')


class AccountDenormalized(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Worker'

    id = ObjectIdField(required=True, db_field='_id')
    short_name = StringField()
    str_name = StringField()
    department = EmbeddedDocumentField(IdFieldEmbedded)
    _type = ListField(StringField())
    provider = EmbeddedDocumentField(IdFieldEmbedded)


class EventEmbedded(EmbeddedDocument):
    id = ObjectIdField(required=True, db_field='_id')
    result = StringField(choices=EVENT_RESULT)
    status = StringField(
        required=True,
        default=CRMStatus.NEW,
        choices=CRM_STATUS_CHOICE,
    )
    account = EmbeddedDocumentField(
        AccountDenormalized,
        verbose_name='аккаунт работника внесшего запись о событии',
    )
    date = DateTimeField()
    event_type = StringField()
    created = DateTimeField(default=datetime.now, verbose_name='Время создания')
    comment = StringField(verbose_name='Комментарий', required=False, null=True)
    contact_persons = ListField(
        ObjectIdField(),
        default=[],
        verbose_name='работники для встречи/события',
    )
    _type = ListField(child=StringField(choices=CRM_EVENT_TYPE),
                      required=True)


class CRM(ForeignDenormalizeModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'CRM',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider.id', 'owner'),
            ('owner', 'status'),
            {
                'name': 'provider_crm_status',
                'fields': [
                    'provider.id',
                    'owner',
                    'status',
                ],
            },
        ],
    }

    owner = ObjectIdField(required=True)
    status = StringField(
        required=True,
        default=CRMStatus.NEW,
        choices=CRM_STATUS_CHOICE
    )
    provider = EmbeddedDocumentField(
        ProviderDenormalized,
        verbose_name='провайдер, на которого было запланировано действие'
    )
    managers = ListField(
        ObjectIdField(),
        verbose_name='Кто работает с организацией',
    )
    sbis = BooleanField(default=False)  # Документооборот
    services = ListField(StringField())
    signs = ListField(StringField())
    ticket_rate = StringField(
        choices=PROVIDER_TICKET_RATES_CHOICES,
        default=ProviderTicketRate.LOW,
        verbose_name="Кол-во обращений от организации"
    )
    last_task = EmbeddedDocumentField(EventEmbedded)
    last_action = EmbeddedDocumentField(EventEmbedded)

    _FOREIGN_DENORMALIZE_FIELDS = [
        'provider',
        'managers',
        'owner',
        'status',
    ]

    def save(self, *args, **kwargs):
        """Если изменение статуса в CRM происходит от лица 'ЗАО Отдел',
            то поле crm_status в Provider меняется автоматически"""
        denormalize_fields = self._get_fields_for_foreign_denormalize()

        is_status_triggered = self._is_triggers(['status'])
        result = super().save(*args, **kwargs)

        if denormalize_fields:
            self._foreign_denormalize(denormalize_fields)

        if is_status_triggered and self.owner == ZAO_OTDEL_PROVIDER_OBJECT_ID:
            from processing.models.billing.provider.main import Provider
            provider = Provider.objects(id=self.provider.id).first()
            provider.update(crm_status=self.status)
            self.update_actors_access()

        return result

    def update_status(self, status: str) -> str:
        """Обновить статус клиента"""
        if self.status != status:
            self.status = status
            self.save()  # обновляет Provider.crm_status

        return self.status

    def update_provider_status(self):
        from processing.models.billing.provider.main import Provider
        Provider.objects(
            id=self.provider.id
        ).update_one(
            crm_status=self.status
        )

    def update_actors_access(self):
        from app.auth.models.actors import Actor

        Actor.objects(
            provider__id=self.provider.id
        ).update(
            provider__client_access=self.status in CAN_TENANT_ACCESS_STATUS
        )

    @classmethod
    def get_or_create(cls, provider, owner_id=None):
        if not owner_id:
            owner_id = ZAO_OTDEL_PROVIDER_OBJECT_ID
        obj = cls.objects(
            owner=owner_id,
            provider__id=provider.id,
        ).first()
        if not obj:
            obj = cls(
                owner=owner_id,
                provider=ProviderDenormalized.from_ref(provider),
            )
            obj.save()
        return obj

    def update_provider_info(self, provider):
        self.provider = ProviderDenormalized.from_ref(provider)
        self.save()

    @property
    def provider_phones(self):
        """Возвращает телефонные номера провайдера для дозвона."""
        phone_types = ['work', 'mobile']
        provider_phones = list(
            ''.join(('8', phone.str_number)) for phone in self.provider.phones
            if phone.phone_type in phone_types)
        providers = list(ProviderCallEmbedded(id=self.id,
                                              str_name=self.provider.str_name,
                                              phone_number=phone)
                         for phone in provider_phones)
        return list(
            SaleTaskAnsweringPersonEmbedded(provider=provider)
            for provider in providers)

    @property
    def accountant_phones(self):
        """Возвращает информацию о бухгалтере для дозвона."""
        if not self.provider.accountant:
            return []
        provider = ProviderEmbedded(
            id=self.id,
            str_name=self.provider.str_name,
        )
        accountant_phones = list(''.join(('8',
                                          phone.code or '812',
                                          phone.number
                                          ))
                                 for phone in self.provider.accountant.phones
                                 if phone.number)
        persons = list(AnsweringPersonEmbedded(
            id=getattr(self.provider.accountant, '_id', None),
            name=self.provider.accountant.str_name,
            position=getattr(self.provider.accountant.position,
                             'name', 'Бухгалтер'),
            phone_number=phone,
            provider=provider,
        ) for phone in accountant_phones)
        return list(
            SaleTaskAnsweringPersonEmbedded(person=person)
            for person in persons)

    @property
    def chief_phones(self):
        """Возвращает информацию о руководителе для дозвона."""
        if not self.provider.chief:
            return []
        provider = ProviderEmbedded(
            id=self.id,
            str_name=self.provider.str_name,
        )
        chief_phones = list(''.join(('8',
                                     phone.code or '812',
                                     phone.number
                                     ))
                            for phone in self.provider.chief.phones
                            if phone.number)
        persons = list(AnsweringPersonEmbedded(
            id=getattr(self.provider.chief, '_id', None),
            name=self.provider.chief.str_name,
            position=getattr(self.provider.chief.position,
                             'name', 'Руководитель'),
            phone_number=phone,
            provider=provider,
        ) for phone in chief_phones)
        return list(
            SaleTaskAnsweringPersonEmbedded(person=person)
            for person in persons)

    def call_task_phones(self, person_types=None):
        """Возвращает информацию для дозвона."""

        result = []
        if person_types is None or 'chief' in person_types:
            result.extend(self.chief_phones)
        if person_types is None or 'provider' in person_types:
            result.extend(self.provider_phones)
        if person_types is None or 'accountant' in person_types:
            result.extend(self.accountant_phones)

        return result

    @classmethod
    def of(cls, provider, owner_id: ObjectId = None,
            status: str = None) -> 'CRM':
        """Взаимоотношения организаций"""
        from processing.models.billing.provider.main import Provider

        if isinstance(provider, ObjectId):
            provider = Provider.objects(id=provider).first()

        assert isinstance(provider, Provider), \
            f"Взаимоотношения с {provider} не установлены"

        if owner_id is None:  # клиентские отношения?
            owner_id = ZAO_OTDEL_PROVIDER_OBJECT_ID

        crm: CRM = cls.objects(
            provider__id=provider.id, owner=owner_id  # индекс
        ).first()  # или None
        if crm is None:
            crm = cls(
                # WARN денормализация провайдера в save только при _created
                provider=ProviderDenormalized.from_ref(provider),
                owner=owner_id, status=CRMStatus.PROSPECTIVE_CLIENT,  # не NEW
            )  # сохраняется при определении статуса

            if status is None:  # статус не определен?
                status = CRMStatus.NEW  # по умолчанию
            elif status == crm.status:  # совпадает с новым?
                crm.status = CRMStatus.NEW  # провоцируем сохранение

        if status and crm.status != status:  # статус изменился?
            crm.status = status
            crm.save()  # обновляет Provider.crm_status

        return crm

    @property
    def is_client(self) -> bool:
        """Является (бывшим) клиентом Системы?"""
        CLIENT_STATUSES = {
            # TODO CONTRACT?
            CRMStatus.CLIENT,
            CRMStatus.ARCHIVE,
        }
        return self.status in CLIENT_STATUSES

    @property
    def is_denied(self) -> bool:
        """Доступ к Системе ограничен?"""
        DENIED_STATUSES = {
            CRMStatus.DEBTOR,
            CRMStatus.DENIED,
            CRMStatus.WRONG,
            CRMStatus.BAN,
        }
        return self.status in DENIED_STATUSES


class TicketAuthorEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    str_name = StringField()
    department = EmbeddedDocumentField(DepartmentEmbedded)
    position = EmbeddedDocumentField(AccountEmbeddedPosition)
    _type = ListField(StringField())


class InitialEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    body = StringField()
    files = EmbeddedDocumentListField(Files)
    author = ObjectIdField()
    position = StringField()
    created_at = DateTimeField(required=True, default=datetime.now)
    is_published = BooleanField(required=True, default=False)


class TicketEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", required=True)
    initial = EmbeddedDocumentField(InitialEmbedded)
    str_number = StringField(verbose_name='Собранный номер тикета')
    author = EmbeddedDocumentField(TicketAuthorEmbedded)
    subject = StringField(verbose_name='Заголовок')
    type = StringField(
        required=True,
        default=TicketType.STATEMENT,
        choices=TICKET_TYPE_CHOICES,
        verbose_name='Характер или тема тикета',
    )
    _type = ListField(StringField())
    status = StringField(
        required=True,
        choices=SUPPORT_TICKET_STATUS_CHOICES,
        default=SupportTicketStatus.NEW,
        verbose_name='Статус тикета',
    )
    comment = EmbeddedDocumentField(InitialEmbedded)


class CRMDenormalized(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'CRM'

    id = ObjectIdField(db_field="_id")
    provider = EmbeddedDocumentField(ProviderShortDenormalized)
    owner = ObjectIdField()
    status = StringField()
    managers = ListField(ObjectIdField())


class CRMEvent(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'CRMEvent',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'crm.owner',
            'crm.id',
        ],
    }
    event_type = StringField(choices=EVENT_TYPE, verbose_name='Тип события')
    result = StringField(choices=EVENT_RESULT, verbose_name='Результат события')
    _type = ListField(child=StringField(choices=CRM_EVENT_TYPE),
                      required=True)
    account = EmbeddedDocumentField(
        AccountDenormalized,
        verbose_name='аккаунт работника внесшего запись о событии'
    )
    created = DateTimeField(
        default=datetime.now,
        verbose_name='Время создания',
    )
    comment = StringField(verbose_name='Комментарий', required=False, null=True)
    contact_persons = ListField(
        ObjectIdField(),
        default=[],
        verbose_name='работники для встречи/события',
    )
    is_summary = BooleanField(default=False)
    summary_date = DateTimeField(null=True)
    date = DateTimeField()
    status = StringField(
        required=True,
        default=CRMStatus.NEW,
        choices=CRM_STATUS_CHOICE
    )  # статус организации на момент создания события
    crm = EmbeddedDocumentField(
        CRMDenormalized,
        required=True,
    )
    # если событие было создано на основе тикета в тех. поддержку
    ticket = EmbeddedDocumentField(TicketEmbedded, required=False)

    @classmethod
    def get_last_event(cls, crm_id, event_type):
        return cls.objects(
            crm__id=crm_id,
            _type=event_type,
        ).order_by('-date').first()

    def save(self, *args, **kwargs):
        if self._created:
            self._denormalize_fields()
        super().save(*args, **kwargs)
        crm = CRM.objects(pk=self.crm.id).get()
        event_type = self._type
        last_event = self.get_last_event(crm.id, event_type)
        if (
                (last_event and last_event.created < self.created)
                or not last_event
        ):
            event = EventEmbedded(
                id=self.id,
                result=self.result,
                status=self.status,
                account=self.account,
                date=self.date,
                event_type=self.event_type,
                created=self.created,
                comment=self.comment,
                contact_persons=self.contact_persons,
                _type=self._type,
            )
            if self._type == ['Task']:
                crm.last_task = event
            elif self._type == ['Action']:
                crm.last_action = event
            crm.save()
        self.reload()
        return self

    def _denormalize_fields(self):
        self._denormalize_crm()
        self._denormalize_account()

    def _denormalize_crm(self):
        crm = CRM.objects(pk=self.crm.id).get()
        self.crm = CRMDenormalized.from_ref(crm)

    def _denormalize_account(self):
        from app.personnel.models.personnel import Worker
        account = Worker.objects(pk=self.account.id).get()
        self.account = AccountDenormalized.from_ref(account)
