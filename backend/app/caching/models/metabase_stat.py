from mongoengine import Document
from mongoengine.fields import DateTimeField, IntField


class NonSberRegistersStat(Document):

    meta = {
        'db_alias': 'cache-db',
        'collection': 'non_sber_registers_stat',
    }

    month = DateTimeField()
    cnt = IntField()  # количество организаций без реестров Сбер
