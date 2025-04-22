from datetime import datetime, timedelta

from mongoengine import Document, DateTimeField, ListField, ObjectIdField, \
    StringField


class EmailCachedIdDaily(Document):
    meta = {
        'db_alias': 'cache-db',
        'collection': 'email_cache',
    }

    date = DateTimeField(default=datetime.now)
    provider = ObjectIdField(required=True)
    url = StringField(required=True)

    @classmethod
    def del_old_record(cls, date=None):
        if not date:
            date = datetime.now() - timedelta(days=2)
        cls.objects(date__lte=date).delete()

    def save(self, *args, **kwargs):
        self.del_old_record()
        return super().save(*args, **kwargs)
