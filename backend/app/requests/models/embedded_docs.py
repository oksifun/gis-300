import datetime
import datetime as dt

from mongoengine import EmbeddedDocument, ObjectIdField, DateTimeField, \
    EmbeddedDocumentListField, StringField

from app.requests.models.choices import REQUEST_STATUS_CHOICES, RequestStatus


class EmbeddedStatusChange(EmbeddedDocument):
    status = StringField(
        choices=REQUEST_STATUS_CHOICES,
        verbose_name='Статус',
        default=RequestStatus.ACCEPTED,
    )
    changed_at = DateTimeField(
        verbose_name='Дата установки статуса',
        default=datetime.datetime.now,
    )


class PersonInChargeEmbedded(EmbeddedDocument):
    id = ObjectIdField(
        required=True,
        verbose_name='ObjectId ответственного лица',
    )
    informed = DateTimeField(
        null=True,
        default=None,
        verbose_name='Дата ознакомления/None',
    )


class ControlMessageEmbedded(EmbeddedDocument):
    created_by = ObjectIdField(
        required=True,
        verbose_name='Сотрудник, контролирующий заявку',
    )
    created_at = DateTimeField(
        required=True,
        default=dt.datetime.now,
        verbose_name='Время создания сообщения',
    )
    message = StringField(required=True)


class EmbeddedMonitoring(EmbeddedDocument):
    messages = EmbeddedDocumentListField(
        ControlMessageEmbedded,
        verbose_name='Сообщения от контролирующих лиц',
        default=[],
    )
    persons_in_charge = EmbeddedDocumentListField(
        PersonInChargeEmbedded,
        verbose_name='Ответственные за заявку лица',
        default=[],
    )
