from mongoengine import Document, EmbeddedDocument, IntField, ObjectIdField, \
    EmbeddedDocumentField, DateTimeField, EmbeddedDocumentListField, StringField

from processing.models.billing.base import ChangeBlockingMixin, \
    BindedModelMixin, ProviderBinds, RelationsProviderBindsProcessingMixin
from processing.models.billing.embeddeds.tenant import DenormalizedTenant
from processing.models.billing.embeddeds.vendor import VendorEmbedded
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES


class ReversalServiceEmbedded(EmbeddedDocument):
    value = IntField(required=True)
    parent_value = IntField(required=True)
    service_type = ObjectIdField(required=True)
    vendor = EmbeddedDocumentField(
        VendorEmbedded,
        verbose_name='Поставщик услуги',
    )


class Reversal(ChangeBlockingMixin,
               RelationsProviderBindsProcessingMixin,
               BindedModelMixin,
               Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Reversal',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            "_binds.pr",
            "date",
            "owner",
            "parent",
            'account.id',
            "account.area.id",
            "account.area.house.id",
            ("account.id", "date"),
        ],
    }
    owner = ObjectIdField(required=True)
    account = EmbeddedDocumentField(DenormalizedTenant)
    date = DateTimeField(required=True)
    services = EmbeddedDocumentListField(ReversalServiceEmbedded)
    value = IntField(required=True)
    redeemed = IntField()
    sector_code = StringField(
        required=True,
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        verbose_name='Направление начислений',
    )

    # может быть создан документом Accrual
    parent = ObjectIdField(required=True, verbose_name='Документ-создатель')

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    def save(self, *args, **kwargs):
        if not kwargs.get('ignore_lock'):
            self.check_change_permissions()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        self.restrict_changes()
        self.value = sum(s.value for s in self.services)
        super().save(*args, **kwargs)
