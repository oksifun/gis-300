from mongoengine import EmbeddedDocument, ObjectIdField, StringField, ListField, \
    DateTimeField, ReferenceField

from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin


class DenormalizedVendorPaymentDoc(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'VendorPaymentDoc'

    id = ObjectIdField(db_field="_id")
    state = StringField()
    owner = ObjectIdField()
    recipient = ObjectIdField()


class DenormalizedPaymentDoc(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'PaymentDoc'

    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField())
    date = DateTimeField(vervbose_name="Дата документа")
    provider = ReferenceField(
        'processing.models.billing.provider.Provider',
        verbose_name='Организация-владелец',
    )
    bank = ObjectIdField(
        required=False,
        null=True,
        verbose_name="Ссылка на банк",
    )
