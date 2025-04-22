from datetime import datetime

from mongoengine import Document, StringField, DateTimeField, ObjectIdField, \
    BooleanField, EmbeddedDocument, BinaryField, \
    ListField, EmbeddedDocumentListField


class AttachmentEmbedded(EmbeddedDocument):
    name = StringField(verbose_name='Имя файла вместе с расширением')
    bytes = BinaryField(verbose_name='Байты самого вложения')
    type = StringField(verbose_name='Например text/application')
    subtype = StringField(verbose_name='Например plain/pdf')


class Mail(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'mail',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('task', 'status'),
            ('addresses', 'datetime'),
            'datetime',
        ],
    }
    _from = StringField(db_field='from', required=True)
    to = StringField(required=True)
    subject = StringField()
    body = StringField()
    datetime = DateTimeField(default=datetime.now)
    status = StringField(choices=('new', 'sent', 'error'), default='new')
    raw = StringField()
    provider = ObjectIdField()
    background = BooleanField(default=False)
    attachments = EmbeddedDocumentListField(AttachmentEmbedded)
    addresses = ListField(StringField(regex=r'[\w.-]+@[\w.-]+\.?[\w]+?'))
    task = ObjectIdField(verbose_name='Ссылка на задачу')
    delivery = ObjectIdField(verbose_name='Ссылка на рассылку', required=False)
    remove_after_send = BooleanField(default=False)
