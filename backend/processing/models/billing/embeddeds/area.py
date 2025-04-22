from mongoengine import EmbeddedDocument, ObjectIdField, IntField, \
    StringField, ListField, EmbeddedDocumentField, BooleanField

from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin
from processing.models.billing.embeddeds.house import DenormalizedHouse, \
    DenormalizedHouseFullAddress, DenormalizedHouseWithFias


class DenormalizedArea(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Area'

    id = ObjectIdField(db_field="_id")
    number = IntField()
    order = IntField()
    str_number = StringField()
    str_number_full = StringField()
    _type = ListField(StringField(), db_field='_type')
    house = EmbeddedDocumentField(
        DenormalizedHouse,
        verbose_name="Информация о квартире",
    )


class DenormalizedAreaIDsOnly(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Area'

    id = ObjectIdField(db_field='_id', required=True)
    _type = ListField(StringField(), db_field='_type')
    house = EmbeddedDocumentField(
        DenormalizedHouse,
        verbose_name="Информация о квартире",
    )


class DenormalizedAreaShortWithFias(DenormalizedEmbeddedMixin,
                                    EmbeddedDocument):
    DENORMALIZE_FROM = 'Area'

    id = ObjectIdField(db_field="_id")
    number = IntField()
    str_number = StringField()
    _type = ListField(StringField(), db_field='_type')
    house = EmbeddedDocumentField(
        DenormalizedHouseWithFias,
        verbose_name="Информация о квартире",
    )


class DenormalizedAreaFullAddress(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Area'

    id = ObjectIdField(db_field="_id")
    number = IntField()
    order = IntField()
    str_number = StringField()
    str_number_full = StringField()
    _type = ListField(StringField(), db_field='_type')
    house = EmbeddedDocumentField(
        DenormalizedHouseFullAddress,
        verbose_name="Информация о квартире",
    )
    is_shared = BooleanField()


class DenormalizedAreaWithFias(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Area'

    id = ObjectIdField(db_field="_id")
    number = IntField()
    order = IntField()
    str_number = StringField()
    str_number_full = StringField()
    _type = ListField(StringField(), db_field='_type')
    house = EmbeddedDocumentField(
        DenormalizedHouseWithFias,
        verbose_name="Информация о квартире",
    )
    is_shared = BooleanField()
