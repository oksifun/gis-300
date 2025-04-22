import datetime

from mongoengine import Document, ObjectIdField, DateTimeField, StringField


class VendorServiceApplyLog(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'vendor_service_apply',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'vendor',
        ],
    }
    vendor = ObjectIdField(verbose_name='Поставщик')
    created = DateTimeField(default=datetime.datetime.now)
    message = StringField()

    @classmethod
    def write_log(cls, vendor_id, message):
        log = cls(
            vendor=vendor_id,
            message=message,
        )
        log.save()
        return log
