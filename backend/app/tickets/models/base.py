from datetime import datetime

from bson import ObjectId
from mongoengine import StringField, ListField, EmbeddedDocumentField, \
    ObjectIdField, EmbeddedDocumentListField, DateTimeField, BooleanField, \
    Document, EmbeddedDocument, IntField

from processing.models.billing.base import FilesDeletionMixin
from app.personnel.models.denormalization.worker import WorkerDenormalized, \
    DepartmentEmbedded
from processing.models.billing.files import Files
from processing.models.billing.provider.main import ProviderCounter
from processing.models.choices import TicketType, TICKET_TYPE_CHOICES, \
    TICKET_STATUS_CHOICES, TicketStatus


class TicketTag(Document):
    meta = {
        'db_alias': 'legacy-db'
    }
    name = StringField()
    provider = ObjectIdField(required=False)
    description = StringField(required=False, null=True)


class Number(EmbeddedDocument):
    count = IntField(min_value=0)
    month = IntField(min_value=0)
    year = IntField(min_value=0)


class TicketMessageMixin:
    id = ObjectIdField(db_field="_id", default=ObjectId)
    body = StringField()
    files = EmbeddedDocumentListField(Files)
    author = ObjectIdField()
    position = StringField()
    created_at = DateTimeField(required=True, default=datetime.now)
    is_published = BooleanField(required=True, default=False)


class Spectator(EmbeddedDocument):
    allow = ListField(ObjectIdField())
    deny = ListField(ObjectIdField())


class Spectators(EmbeddedDocument):
    Account = EmbeddedDocumentField(Spectator)
    Position = EmbeddedDocumentField(Spectator)
    Department = EmbeddedDocumentField(Spectator)


class DenormalizedAccount(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    department = EmbeddedDocumentField(DepartmentEmbedded)
    _type = ListField(StringField())


class BasicTicket(FilesDeletionMixin):
    type = StringField(
        required=True,
        default=TicketType.STATEMENT,
        choices=TICKET_TYPE_CHOICES,
        verbose_name='Характер или тема тикета',
    )
    _type = ListField(StringField())
    number = EmbeddedDocumentField(Number, verbose_name='Номер тикета')
    status = StringField(
        required=True,
        choices=TICKET_STATUS_CHOICES,
        default=TicketStatus.NEW,
        verbose_name='Статус обращения',
    )
    parent = ObjectIdField(
        verbose_name='Ссылка на обращение-основание',
    )
    subject = StringField(verbose_name='Заголовок')
    request = ObjectIdField(
        verbose_name='Ссылка на заявку-основание',
    )
    executor = EmbeddedDocumentField(
        WorkerDenormalized,
        verbose_name='Исполнитель',
        default=WorkerDenormalized
    )
    spectators = EmbeddedDocumentField(Spectators, verbose_name='Наблюдатели')
    str_number = StringField(verbose_name='Собранный номер тикета')
    incoming_date = DateTimeField(
        verbose_name='Входящая дата для входящего номера',
    )
    incoming_number = StringField(verbose_name='Входящий номер тикета')
    created_by = EmbeddedDocumentField(
        DenormalizedAccount,
        required=True,
        verbose_name='Кем создан тикет',
    )
    tags = ListField(ObjectIdField())
    only_email_response = BooleanField(default=False)
    is_deleted = BooleanField()

    def _generate_number(self, provider_id=None):
        """ Генерация номера заявки """
        if not provider_id:
            provider_id = self.created_by.department.provider
        date = datetime.now()
        number_data = Number(year=date.year, month=date.month)
        number_data.count = ProviderCounter.get_next_number(
            year=date.year,
            provider_id=provider_id
        )
        self.number = number_data
        self.str_number = '{0.count}-{0.month}/{0.year}'.format(self.number)
