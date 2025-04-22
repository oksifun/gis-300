from mongoengine import Document, ReferenceField, DateTimeField, StringField, \
    ObjectIdField
import datetime


class AccountTaskLock(Document):
    meta = {
        "db_alias": "queue-db",
        'allow_inheritance': True
    }

    # "Текущая задача"
    task = StringField(required=True)
    uuid = StringField()

    # аккаунт "Жителя"
    account = ObjectIdField(unique=True, required=True)
    created = DateTimeField(required=True, default=datetime.datetime.now)

    def __eq__(self, other):
        if not isinstance(other, AccountTaskLock):
            raise TypeError('AccountTaskLock instance is comparable only '
                            'to the same')

        return self.task == other.task and self.account == other.account

    def release(self):
        self.delete()


class ProcessingLock(Document):
    meta = {
        "db_alias": "queue-db"
    }


class SendSberbankRegistryLock(Document):
    meta = {
        "db_alias": "queue-db"
    }
