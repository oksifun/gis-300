from mongoengine import Document, ObjectIdField


class SberAutoPayAccount(Document):
    meta = {
        "db_alias": "queue-db",
        'collection': 'sber_autopay_accounts',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'account',
            'provider',
        ],
    }
    account = ObjectIdField()
    provider = ObjectIdField()
