from mongoengine import EmbeddedDocument, ObjectIdField


class VendorEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    contract = ObjectIdField(null=True, verbose_name='ID договора')
