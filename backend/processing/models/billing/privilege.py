from mongoengine import Document, IntField, StringField, ListField


class Privilege(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Privilege',
    }

    _type = ListField(StringField())
    title = StringField()
    system_code = StringField()
    moscow_code = IntField()
    kod_kat = StringField()
