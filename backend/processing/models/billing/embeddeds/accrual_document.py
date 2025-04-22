from mongoengine import EmbeddedDocument, ObjectIdField, DateTimeField, StringField, ReferenceField

from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin
from processing.models.choices import *


class DenormalizedAccrualDocument(DenormalizedEmbeddedMixin, EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    date = DateTimeField()
    status = StringField(
        required=True,
        choices=ACCRUAL_DOCUMENT_STATUS_CHOICES,
        default=AccrualDocumentStatus.WORK_IN_PROGRESS,
        verbose_name="Статус документа",
    )
    provider = ObjectIdField(
        verbose_name="Организация-владелец документа",
    )
    pay_till = DateTimeField(verbose_name="Оплатить до")
