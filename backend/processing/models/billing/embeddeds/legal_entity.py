from mongoengine import EmbeddedDocument, ObjectIdField, EmbeddedDocumentField, \
    StringField

from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin


class DenormalizedLegalEntityDetails(EmbeddedDocument):
    short_name = StringField()
    inn = StringField()


class DenormalizedLegalEntity(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'LegalEntityProviderBind'

    id = ObjectIdField(db_field="_id")
    entity = ObjectIdField(
        required=True,
        verbose_name='Организация'
    )
    entity_details = EmbeddedDocumentField(
        DenormalizedLegalEntityDetails,
        required=True,
        verbose_name='Реквизиты',
    )
