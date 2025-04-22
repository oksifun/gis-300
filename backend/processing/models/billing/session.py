from datetime import datetime
from dateutil.relativedelta import relativedelta

from mongoengine import Document, BooleanField, DateTimeField, ListField, ReferenceField, DictField, StringField, \
    DynamicField
from mongoengine.base.fields import ObjectIdField
from mongoengine.document import EmbeddedDocument
from mongoengine.fields import EmbeddedDocumentField


class SlaveSession(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'HistorySession'
    }
    account = ReferenceField('procession.models.Account')
    provider = ReferenceField('procession.models.Provider')
    created_at = DateTimeField()


class SessionEmbeddedAccount(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField())
    is_super = BooleanField()
    provider = ReferenceField('procession.models.Provider')
    is_autoapi = BooleanField()


class EmbeddedSlaveSession(EmbeddedDocument):
    id = StringField(db_field="_id", primary_key=True)

    account = ObjectIdField()
    provider = ObjectIdField()
    created_at = DateTimeField()
    is_active = BooleanField()


DEFAULT_TOKEN_LIFETIME: int = 4 * 60 * 60  # в секундах


class Session(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Session'
    }

    id = StringField(db_field="_id", primary_key=True)

    is_active = BooleanField(required=True, default=True)
    created_at = DateTimeField(required=True, default=datetime.now)

    # legacy - HistoryField(SlaveSession, history_collection='HistorySession')
    # slave = ListField(ReferenceField('processing.models.billing.slave_session.SlaveSession'))
    slave = EmbeddedDocumentField(EmbeddedSlaveSession)
    slave_history = ListField(DynamicField())
    account = EmbeddedDocumentField(SessionEmbeddedAccount)
    is_auto = BooleanField(required=False, default=False, verbose_name="является генерируемой авто-сессией")
    remote_ip = StringField()
    screen_sizes = ListField(StringField())

    @property
    def days_created(self) -> int:
        """Создана дней назад?"""
        delta = self.created_at - datetime.now()
        return delta.days

    def has_expired(self, lifetime: int = DEFAULT_TOKEN_LIFETIME) -> bool:
        """Просроченная сессия?"""
        if datetime.now() > self.created_at + relativedelta(seconds=lifetime):
            if self.is_active:  # просроченная сессия активна?
                self.is_active = False  # деактивируем сессию
                self.save()  # cls.objects(id=self.id).update(is_active=False)
            return True

        return False
