import datetime

from mongoengine import Document, ObjectIdField, StringField, IntField, \
    DateTimeField, EmbeddedDocumentField, BooleanField

from app.payment.models.vendor_pay import VendorPayment
from app.payment.models.vendor_pay_doc import VendorPaymentDoc
from app.bankstatements.models.bankstatement_doc import BankStatementDoc
from processing.models.billing.base import BindedModelMixin, ProviderBinds, \
    ChangeBlockingMixin


class VendorReceiptDoc(ChangeBlockingMixin, BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'VendorReceiptDoc',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            {
                'fields': [
                    '_binds.pr',
                    '-date',
                ],
            },
        ]
    }

    owner = ObjectIdField(required=True)
    remitter = ObjectIdField(required=True)
    remitter_doc = ObjectIdField(required=True)

    bank_number = StringField()
    bank = ObjectIdField()
    value = IntField(required=True)
    source_value = IntField(required=True)
    count = IntField(required=True)
    date = DateTimeField(required=True, default=datetime.datetime.now)
    description = StringField()
    number = StringField()
    bank_statement = ObjectIdField()
    compared_at = DateTimeField()
    fiscalization_at = DateTimeField()

    _binds = EmbeddedDocumentField(ProviderBinds)

    def save(self, *args, **kwargs):
        self.check_change_permissions()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        if not self.value or not self.count:
            self.receive_remitter_doc_data()
        return super().save(*args, **kwargs)

    def receive_remitter_doc_data(self):
        doc = VendorPaymentDoc.objects(pk=self.remitter_doc).get()
        self.value = doc.value
        self.count = VendorPayment.objects(doc__id=self.remitter_doc).count()

    @classmethod
    def create_by_vendor_payment_doc(cls, doc, save=True):
        receipt_doc = cls(
            owner=doc.recipient,
            remitter=doc.owner,
            remitter_doc=doc.id,
            value=doc.value,
            source_value=doc.value,
            description=doc.description,
        )
        receipt_doc.count = VendorPayment.objects(
            doc__id=doc.id,
        ).count()
        if save:
            receipt_doc.save()
        return receipt_doc

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            owner__ne=provider_id,
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id)
        pushed = cls.objects(
            owner=provider_id,
        ).update(add_to_set___binds__pr=provider_id)
        return pushed, pulled

    @classmethod
    def lock_document(cls, doc_id):
        doc = cls.objects(pk=doc_id).first()
        if not doc:
            return
        cls.objects(pk=doc_id).update(lock=True)
        # Блокировка BSD
        BankStatementDoc.objects(id=doc.bank_statement).update(lock=True)
        # Блокировка его оплат
        payments = VendorPayment.objects(doc__id=doc.remitter_doc)
        payments.update(lock=True)
