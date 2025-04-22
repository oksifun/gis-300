from mongoengine import EmbeddedDocument, ObjectIdField, StringField, ListField

from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin


class DenormalizedHouse(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'House'

    id = ObjectIdField(db_field="_id")


class DenormalizedHouseFullAddress(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'House'

    id = ObjectIdField(db_field="_id")
    address = StringField(verbose_name='Адрес дома')


class DenormalizedHouseWithFias(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'House'

    id = ObjectIdField(db_field="_id")
    address = StringField(verbose_name='Адрес дома')
    fias_addrobjs = ListField(
        StringField(),
        verbose_name='Родительские addrobj дома'
    )
