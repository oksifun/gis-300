from mongoengine import Document, ObjectIdField, IntField, \
    EmbeddedDocumentField, EmbeddedDocument, \
    EmbeddedDocumentListField, BooleanField

from app.payment.models.denormalization.embedded_docs import \
    DenormalizedVendorPaymentDoc
from app.payment.models.vendor_pay_doc import VendorPaymentDoc
from processing.models.billing.base import BindedModelMixin, ProviderBinds, \
    ChangeBlockingMixin


class VendorPaymentServiceEmbedded(EmbeddedDocument):
    service = ObjectIdField()
    value = IntField()


class VendorPayment(ChangeBlockingMixin, BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'VendorPayment',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'doc',
        ]
    }

    doc = EmbeddedDocumentField(DenormalizedVendorPaymentDoc, required=True)
    payment = ObjectIdField(required=True)
    offset = ObjectIdField()
    value = IntField(required=True)
    house = ObjectIdField()
    services = EmbeddedDocumentListField(VendorPaymentServiceEmbedded)
    has_receipt = BooleanField()
    is_deleted = BooleanField()

    _binds = EmbeddedDocumentField(ProviderBinds)

    def save(self, *args, **kwargs):
        self.check_change_permissions()
        self.generate_auto_fields()
        return super().save(*args, **kwargs)

    def generate_auto_fields(self):
        if not self.doc.owner:
            doc = VendorPaymentDoc.objects(pk=self.doc.id).get()
            self.doc = DenormalizedVendorPaymentDoc.from_ref(doc)
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())

    def _get_providers_binds(self):
        return [self.doc.owner, self.doc.recipient]

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            doc__owner__ne=provider_id,
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id)
        pushed = cls.objects(
            doc__owner=provider_id,
        ).update(add_to_set___binds__pr=provider_id)
        return pushed, pulled

    @classmethod
    def mark_as_fiscalized(cls, payment_id):
        query_set = cls.objects(pk=payment_id)
        return query_set.update(has_receipt=True)
