from mongoengine import Document, DateTimeField, StringField, ReferenceField

from processing.models.choices import LEGAL_FORM_TYPE_CHOICES


class LegalEntityDetails(Document):
    """
    Реквизиты юр.лиц
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityDetails',
    }
    entity = ReferenceField(
        'processing.models.billing.legal_entity.LegalEntity',
        required=True,
        verbose_name="Организация"
    )
    date_from = DateTimeField(required=True, verbose_name='Начиная с')
    full_name = StringField(required=True, verbose_name='Полное наименование')
    short_name = StringField(required=True, verbose_name='Краткое наименование')
    legal_form = StringField(required=True, choices=LEGAL_FORM_TYPE_CHOICES)
    inn = StringField(verbose_name='ИНН')
    created = DateTimeField()
    closed = DateTimeField()
