from mongoengine import Document, StringField


class OffsetLog(Document):
    meta = {
        "db_alias": "queue-db"
    }
    text = StringField()
