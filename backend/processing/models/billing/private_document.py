from mongoengine import Document
from mongoengine.fields import BooleanField, ObjectIdField, ListField, StringField, DateTimeField, ReferenceField

from processing.models.choices import PrivateDocumentsTypes, PRIVATE_DOCUMENTS_TYPE_CHOICES


class PrivateDocument(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'PrivateDocument',
    }

    id = ObjectIdField(db_field="_id", primary_key=True)
    _type = ListField(StringField())

    is_actual = BooleanField()
    issue_date = DateTimeField()
    account = ReferenceField('processing.models.billing.account.Account')
    number = StringField()
    issued_code = StringField()
    series = StringField()
    issued = StringField()
    is_deleted = BooleanField()
    currency = DateTimeField(verbose_name='Срок действия органичен')
    reason_replacement = StringField(verbose_name='Причина замены')
    date_replacement = DateTimeField()

