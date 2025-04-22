import datetime

from mongoengine import ReferenceField, EmbeddedDocument, EmbeddedDocumentField, \
    StringField, ObjectIdField, \
    DynamicDocument, Document, DateTimeField, DynamicField, \
    EmbeddedDocumentListField


class DummySession(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # legacy - Ref('Account')
    account = ReferenceField('processing.models.billing.account.Account')

    # legacy - Ref('Provider')
    provider = ReferenceField('processing.models.billing.provider.Provider')


class BaseLogRecord(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    master_session = EmbeddedDocumentField(DummySession)
    slave_session = EmbeddedDocumentField(DummySession)
    client_ip = StringField()


class History(DynamicDocument):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'History'
    }

    ref_model = StringField(required=True)
    ref_id = ObjectIdField(required=True)


class LogDbf(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LogDbf'
    }

    provider = ReferenceField('processing.models.billing.provider.Provider')
    created_at = DateTimeField()
    file_out = DynamicField()
    file_in = DynamicField()


class UnsubscribeReason(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'UnsubscribeReason',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'tenant',
        ],
    }
    tenant = ObjectIdField(required=True)
    reason = StringField(required=True)
    email = StringField(required=True)
    _type = StringField(required=True)
    created = DateTimeField(default=datetime.datetime.now)


class PublicPaySource(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'PublicPaySource',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'tenant',
            'source',
        ],
    }
    tenant = ObjectIdField(required=True)
    source = StringField(required=True)
    email = StringField()
    created = DateTimeField(default=datetime.datetime.now)


class LogField(EmbeddedDocument):
    log = StringField()
    upd = DateTimeField(default=datetime.datetime.now)
    error = StringField()


class AutoPaymentLog(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'AutoPaymentLog',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'tenant',
        ],
    }
    tenant = ObjectIdField(required=True)
    logs = EmbeddedDocumentListField(LogField)
    created = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def write_log(cls, tenant_id, message, error=None):
        log = LogField(
            log=message,
            error=error,
        )
        updated = cls._push_log(tenant_id, log)
        if not updated:
            cls(
                tenant=tenant_id,
                logs=[],
            ).save()
            cls._push_log(tenant_id, log)

    @classmethod
    def _push_log(cls, tenant_id, log_field_value):
        return cls.objects(
            tenant=tenant_id,
        ).update(
            push__logs=log_field_value,
        )
