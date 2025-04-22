from datetime import datetime

from mongoengine import Document, ObjectIdField, StringField, DateTimeField, \
    BooleanField, ListField, EmbeddedDocumentField, EmbeddedDocument, \
    EmbeddedDocumentListField, DynamicDocument

from processing.models.billing.account import Account
from processing.models.billing.embeddeds.address import Address
from processing.models.billing.provider.main import Provider
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from processing.models.billing.files import Files
from processing.models.choices import LEGAL_FORM_TYPE_CHOICES, \
    PRINT_RECEIPT_TYPE_CHOICES, PrintReceiptType, CALC_SOFTWARE_TYPE_CHOICES, \
    CalcSoftwareType
from processing.models.billing.crm.constants import ACTIVE_STATUSES


class EventType(object):
    INCOMING_CALL = 'incoming_call'
    OUT_COMING_CALL = 'out_coming_call'
    MEETING = 'meeting'
    INFORMATION = 'information'


EVENT_TYPE = (
    (EventType.INCOMING_CALL, 'Входящий звонок'),
    (EventType.OUT_COMING_CALL, 'Исходящий звонок'),
    (EventType.MEETING, 'Встреча'),
    (EventType.INFORMATION, 'Информация'),
)


class EventResult(object):
    GOOD = 'good'
    BAD = 'bad'
    UNKNOWN = 'unknown'


EVENT_RESULT = (
    (EventResult.GOOD, 'хорошо'),
    (EventResult.BAD, 'плохо'),
    (EventResult.UNKNOWN, 'непонятно'),
)


class CRMStatus(object):
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
    DEBTOR = 'debtor'
    ARCHIVE = 'archive'


CRM_STATUS_CHOICE = (
    ('new', 'Новый'),
    ('cold', 'Холодный'),
    ('work', 'В работе'),
    ('denied', 'Отказался'),
    ('wrong', 'Недействующая'),
    ('alien', 'Не наш клиент'),
    ('ban', 'Запрет'),
    ('client', 'Клиент'),
    ('prospective_client', 'Потенциальный'),
    ('partner', 'Партнер'),
    ('departure', 'выезд на адрес'),
    ('aftershock', 'дожимание'),
    ('sent', 'анкета отправлена'),
    ('contract', 'договор/оплата'),
    ('debtor', 'Отключен за долги'),
    ('archive', 'Архивный'),
)


class CRMRelation(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'CRMRelation',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            {
                'fields': ['observed', 'owner'],
                'unique': True,
            },
            ('owner', 'status'),
            {
                'name': 'fast_status',
                'fields': [
                    'observed',
                    'status',
                    'owner',
                ],
            },
            'status',
        ]
    }

    owner = ObjectIdField(required=True)
    observed = ObjectIdField(required=True)
    status = StringField(
        required=True,
        default=CRMStatus.NEW,
        choices=CRM_STATUS_CHOICE,
    )

    def save(self, *args, **kwargs):
        if self.owner == ZAO_OTDEL_PROVIDER_OBJECT_ID:
            self.denormalize_provider_crm_status()
            if self.id:
                self.set_client_access_in_actors()
        return super().save(*args, **kwargs)

    def denormalize_provider_crm_status(self):
        provider = Provider.objects(pk=self.observed).get()
        provider.crm_status = self.status
        provider.save()

    def set_client_access_in_actors(self):
        from app.auth.models.actors import Actor
        new_value = self.status in ACTIVE_STATUSES
        old_value = self.__class__.objects.get(id=self.id).status in ACTIVE_STATUSES
        if new_value is not old_value:
            Actor.objects(provider__id=self.observed).update(
                provider__client_access=new_value
            )


class ProviderEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True)
    str_name = StringField()
    address = EmbeddedDocumentField(Address)


class ClientEmbedded(EmbeddedDocument):
    owner = ObjectIdField()
    client_id = StringField()


class DocsEmbedded(EmbeddedDocument):
    document_type = StringField()
    document_state = StringField()
    document_name = StringField()
    period = DateTimeField()
    date = DateTimeField()
    file = EmbeddedDocumentField(Files)
    client_ids = EmbeddedDocumentListField(ClientEmbedded)


class IdFieldEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')


class WorkerDenormalized(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    last_name = StringField()
    first_name = StringField()
    patronymic_name = StringField()
    position_code = ObjectIdField()


class AccountEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True)
    short_name = StringField()
    str_name = StringField()
    department = EmbeddedDocumentField(IdFieldEmbedded)
    _type = ListField(StringField())
    provider = EmbeddedDocumentField(IdFieldEmbedded)


class CRMBase(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'CRMBase',
    }

    provider = EmbeddedDocumentField(
        ProviderEmbedded,
        verbose_name='провайдер, на которого было запланировано действие'
    )

class ActionsAndEventsEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    type = StringField(choices=EVENT_TYPE)  # Тип события
    status = StringField(choices=CRM_STATUS_CHOICE)  # Статус события
    result = StringField(choices=EVENT_RESULT)  # Результат события
    account = EmbeddedDocumentField(
        AccountEmbedded,
        verbose_name='аккаунт работника внесшего запись о событии'
    )

    created_at = DateTimeField(default=datetime.now)  # время создания
    comment = StringField()  # Комментарий
    contact_persons = ListField(
        ObjectIdField(),
        verbose_name='работники для встречи/события'
    )
    is_summary = BooleanField()
    summary_date = DateTimeField()
    date = DateTimeField()
    _type = ListField(StringField())
    arc_type = StringField()  # Архивный Тип события

    def save(self, *args, **kwargs):
        # self.denormalize_account()  todo
        super().save(*args, **kwargs)

    def denormalize_account(self):
        if self.account and self.account.id:
            account = Account.objects(id=self.account.id).as_pymongo().get()
            self.account.str_name = account['str_name']
            self.account.short_name = account['short_name']

            self.account._type = [account['_type'][-1]]
            if account.get('department', {}).get('_id'):
                self.account.department = IdFieldEmbedded(
                    id=account['department']['_id']
                )
            if account.get('provider', {}).get('_id'):
                self.account.provider = IdFieldEmbedded(
                    id=account['provider']['_id']
                )


class ProviderDenormalized(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True)
    legal_form = StringField(required=True, choices=LEGAL_FORM_TYPE_CHOICES)
    str_name = StringField()
    ogrn = StringField(verbose_name='ОГРН')
    inn = StringField(verbose_name='ИНН')
    fias = ListField(
        StringField(),
        verbose_name='ФИАС-коды адресов',
    )
    workers = EmbeddedDocumentListField(WorkerDenormalized)
    emails = ListField(StringField())
    phones = ListField(StringField())
    business_types = ListField(ObjectIdField())
    managers = ListField(
        ObjectIdField(),
        verbose_name='Кто работает с организацией',
    )
    crm_last_action = EmbeddedDocumentField(
        ActionsAndEventsEmbedded,
        verbose_name="Последнее действие по организации"
    )
    crm_last_event = EmbeddedDocumentField(
        ActionsAndEventsEmbedded,
        verbose_name="Последнее запланированное событие по организации"
    )
    receipt_type = StringField(
        choices=PRINT_RECEIPT_TYPE_CHOICES,
        default=PrintReceiptType.UNKNOWN,
        verbose_name="печать квитанций"
    )
    calc_software = StringField(
        choices=CALC_SOFTWARE_TYPE_CHOICES,
        default=CalcSoftwareType.OTHER,
        verbose_name="расчет"
    )
    docs = EmbeddedDocumentListField(
        DocsEmbedded,
        verbose_name='Какие-то документы'
    )
    terminal = ListField(StringField())
    services = ListField(StringField())
    signs = ListField(StringField())


class CRMBase(DynamicDocument):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'CRMBase',
    }


class CRM(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'CRM',
    }
    owner = ObjectIdField(required=True)
    status = StringField(
        required=True,
        default=CRMStatus.PROSPECTIVE_CLIENT,
        choices=CRM_STATUS_CHOICE
    )
    provider = EmbeddedDocumentField(
        ProviderDenormalized,
        verbose_name='провайдер, на которого было запланировано действие'
    )
    # Вложенный список действий (Action & Event)
    actions = EmbeddedDocumentListField(
        ActionsAndEventsEmbedded,
        verbose_name='Вложенный список действий (Action & Event)'
    )

    def save(self, *args, **kwargs):
        # self.denormalize_provider()  todo
        super().save(*args, **kwargs)

    def denormalize_provider(self):
        if self.provider and self.provider.id:
            provider = Provider.objects(id=self.provider.id).get()
            self.provider.str_name = provider['str_name']
            self.provider.address = provider['address']
