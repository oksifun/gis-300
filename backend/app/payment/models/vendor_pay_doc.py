from random import random

from mongoengine import Document, ObjectIdField, StringField, DateTimeField, \
    IntField, EmbeddedDocumentField

from app.legal_entity.models.legal_entity import LegalEntity
from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_provider_bind import \
    LegalEntityProviderBind
from app.payment.models.choices import VENDOR_PAYMENT_DOC_STATUSES_CHOICES_ALL
from lib.dates import start_of_day
from processing.models.billing.base import BindedModelMixin, ProviderBinds
from processing.models.billing.embeddeds.legal_entity import \
    DenormalizedLegalEntity, DenormalizedLegalEntityDetails
from processing.models.billing.provider.main import Provider


class VendorPaymentDoc(BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'VendorPaymentDoc',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            {
                'fields': [
                    '_binds.pr',
                    '-date',
                ],
            },
            ('code', 'recipient', '-date'),
        ]
    }

    owner = ObjectIdField(required=True)
    vendor = EmbeddedDocumentField(DenormalizedLegalEntity, required=True)
    recipient = ObjectIdField(required=False)

    contract = ObjectIdField(required=True)
    bank_account = StringField(required=True)
    source_date = DateTimeField(required=True)

    value = IntField(required=True)
    state = StringField(
        required=True,
        choices=VENDOR_PAYMENT_DOC_STATUSES_CHOICES_ALL,
        default='new',
    )
    date = DateTimeField(required=True)
    description = StringField()
    code = StringField()

    _binds = EmbeddedDocumentField(ProviderBinds)

    def save(self, *args, **kwargs):
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        if self._created:
            contract = self.get_contract_data()
            self.source_date = start_of_day(self.source_date)
            self.code = self.generate_code()
            self.description = self.generate_description(contract)
            self._denormalize_vendor(contract)
            provider = Provider.objects(
                inn=self.vendor.entity_details.inn,
            ).only(
                'id',
            ).as_pymongo().first()
            if provider:
                self.recipient = provider['_id']
        return super().save(*args, **kwargs)

    def get_contract_data(self):
        return LegalEntityContract.objects(
            pk=self.contract,
        ).only(
            'entity',
            'number',
            'date',
            'name',
        ).as_pymongo().get()

    @staticmethod
    def generate_code():
        return str(
            int(random() * 1000000)
            + (round(random() * 8) + 1) * 10000000
        )

    def generate_description(self, contract):
        return (
            f'Перечисление по '
            f'Договору {contract["number"]} '
            f'от {contract["date"].strftime("%d.%m.%Y")} '
            f'за {self.source_date.strftime("%d.%m.%Y")}, '
            f'код {self.code}'
        )

    def _denormalize_vendor(self, contract):
        vendor = LegalEntity.objects(
            pk=contract['entity'],
        ).only(
            'current_details',
        ).as_pymongo().get()
        entity_bind = LegalEntityProviderBind.objects(
            entity=contract['entity'],
            provider=self.owner,
        ).only(
            'id',
        ).as_pymongo().first()
        self.vendor = DenormalizedLegalEntity(
            id=entity_bind['_id'] if entity_bind else None,
            entity=contract['entity'],
            entity_details=DenormalizedLegalEntityDetails(
                short_name=vendor['current_details']['current_name'],
                inn=vendor['current_details']['current_inn'],
            ),
        )

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
