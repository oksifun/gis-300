import datetime

from mongoengine import Document, ObjectIdField, StringField, DateTimeField


class CipcaLog(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'cipca',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'task',
        ],
    }
    task = ObjectIdField(required=True)
    log = StringField()
    error = StringField()
    created = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def write_log(cls, task_id, message, error=None):
        log = cls(
            task=task_id,
            log=message,
        )
        if error:
            log.error = error
        log.save()
