from bson import ObjectId
from mongoengine import EmbeddedDocument, ObjectIdField, StringField, \
    EmbeddedDocumentField, ListField

from app.personnel.models.choices import SYSTEM_DEPARTMENTS_CHOICES
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin


class SystemDepartmentEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True, default=ObjectId)
    code = StringField(
        choices=SYSTEM_DEPARTMENTS_CHOICES,
        verbose_name='Код системного отдела',
        null=True,
    )


class DepartmentEmbedded(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Department'

    id = ObjectIdField(db_field="_id")
    name = StringField()
    provider = ObjectIdField()
    system_department = EmbeddedDocumentField(SystemDepartmentEmbedded)


class WorkerPositionDenormalized(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Position'

    id = ObjectIdField(db_field="_id")
    name = StringField()
    code = StringField(null=True)


class WorkerDenormalized(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Worker'

    id = ObjectIdField(db_field="_id")
    short_name = StringField()
    department = EmbeddedDocumentField(DepartmentEmbedded)
    position = EmbeddedDocumentField(WorkerPositionDenormalized)
    _type = ListField(StringField())
