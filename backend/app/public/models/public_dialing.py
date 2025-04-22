from mongoengine import Document, StringField, DateTimeField


class PublicPayCall(Document):
    """Дозвон до жителя с публичного QR"""
    meta = {
        'db_alias': 'cache-db',
        'collection': 'public_qr_calls',
    }
    guest_number = StringField(max_length=11,
                               verbose_name='Номер телефона плательщика')
    call_date = DateTimeField(verbose_name='Дата исходящего звонка')
    task_id = StringField(verbose_name='Id задачи celery')