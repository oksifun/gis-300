from mongoengine import EmbeddedDocument, EmbeddedDocumentField, ObjectIdField
from .location import Location


class Address(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    real = EmbeddedDocumentField(Location)
    postal = EmbeddedDocumentField(Location)
    correspondence = EmbeddedDocumentField(Location)
