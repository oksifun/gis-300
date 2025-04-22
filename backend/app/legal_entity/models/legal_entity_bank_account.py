from mongoengine import Document, DateTimeField, StringField, ReferenceField


class LegalEntityBankAccount(Document):
    """
    Расчётные счета юр.лиц
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityBankAccount',
    }
    entity = ReferenceField(
        'processing.models.billing.legal_entity.LegalEntity',
        required=True,
        verbose_name="Организация"
    )
    bank = ReferenceField(
        'processing.models.billing.provider.Provider',
        required=True,
        verbose_name='Ссылка на банк'
    )
    number = StringField(required=True, verbose_name='Номер счета')
    date_from = DateTimeField(verbose_name='Дата открытия')
    active_till = DateTimeField(verbose_name='Активен по')
    created = DateTimeField()
    closed = DateTimeField()
