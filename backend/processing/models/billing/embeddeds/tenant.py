from mongoengine import EmbeddedDocument, ObjectIdField, StringField, \
    ListField, BooleanField, EmbeddedDocumentField

from processing.models.billing.embeddeds.area import DenormalizedArea, \
    DenormalizedAreaFullAddress, DenormalizedAreaIDsOnly
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin


class DenormalizedTenant(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Tenant'

    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField(), db_field='_type')
    area = EmbeddedDocumentField(
        DenormalizedArea,
        verbose_name="Информация о квартире",
    )
    is_developer = BooleanField()
    do_not_accrual = BooleanField()


class DenormalizedTenantWithName(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Tenant'

    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField(), db_field='_type')
    area = EmbeddedDocumentField(
        DenormalizedAreaIDsOnly,
        verbose_name="Информация о квартире"
    )
    is_developer = BooleanField(null=True)
    do_not_accrual = BooleanField()
    str_name = StringField(verbose_name='Строка имени')


class DenormalizedTenantFullAddress(DenormalizedEmbeddedMixin,
                                    EmbeddedDocument):
    DENORMALIZE_FROM = 'Tenant'

    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField(), db_field='_type')
    area = EmbeddedDocumentField(
        DenormalizedAreaFullAddress,
        verbose_name="Информация о квартире",
    )
    is_developer = BooleanField()
