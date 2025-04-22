from datetime import datetime

from mongoengine import Document, StringField, DateTimeField, FloatField, \
    IntField


class GatewayBalance(Document):

    meta = {
        'db_alias': 'logs-db',
        'collection': 'GatewayBalance'
    }

    phone = StringField()
    balance = StringField()
    balance_number = FloatField()
    operator = StringField()
    gateway = IntField()
    gateway_state = StringField()
    created = DateTimeField(default=datetime.now)
