from mongoengine import Document, ReferenceField, StringField, \
    EmbeddedDocument, EmbeddedDocumentListField, IntField, ListField, \
    ObjectIdField, BooleanField

from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES


class MoscowGCJSHouseData(EmbeddedDocument):
    house = ReferenceField(
        'app.house.models.house.House',
        required=True,
    )
    district_code = IntField(required=True)
    street_code = IntField(required=True)
    street_code_BTI = IntField(required=True)
    house_code_BTI = IntField(null=True)
    housing_fund = IntField(null=True)
    living_type = IntField(null=True)


class MoscowGCJSHouses(EmbeddedDocument):
    house = ObjectIdField()


class MoscowGCJSExportSettings(EmbeddedDocument):
    houses = ListField(ObjectIdField())
    contract_number = StringField(null=True)
    sectors = ListField(StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES))
    export_type = StringField()
    intercom_export = BooleanField(
        default=False,
        verbose_name='Выгружать ли информацию о домофонах'
    )


class MoscowGCJSProviderData(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'MoscowGCJSProviderData'
    }
    provider = ReferenceField(
        'processing.models.billing.provider.Provider', required=True)
    provider_code = IntField()
    houses_codes = EmbeddedDocumentListField(
        MoscowGCJSHouseData, verbose_name='Настройки домов')
    package_export = EmbeddedDocumentListField(
        MoscowGCJSExportSettings,
        verbose_name='Настройки экспорта'
    )


