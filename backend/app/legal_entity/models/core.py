from mongoengine import DateTimeField, StringField, ObjectIdField, ListField, \
    EmbeddedDocument

from processing.models.choices import LEGAL_FORM_TYPE_CHOICES


class LegalEntityBankAccountEmbedded(EmbeddedDocument):
    """
    Расчётные счета юр.лиц
    """

    bank = ObjectIdField(required=False, verbose_name='Банк')
    bic = StringField(required=True, verbose_name='БИК')
    number = StringField(required=True, verbose_name='Номер счета')
    corr_number = StringField(default="")
    date_from = DateTimeField(verbose_name='Дата открытия')
    active_till = DateTimeField(verbose_name='Активен по')

    created = DateTimeField()
    closed = DateTimeField()


class LegalEntityDetailsEmbedded(EmbeddedDocument):
    """
    Реквизиты юр.лиц
    """
    date_from = DateTimeField(required=True, verbose_name='Начиная с')
    full_name = StringField(required=True, verbose_name='Полное наименование')
    short_name = StringField(required=True, verbose_name='Краткое наименование')
    legal_form = StringField(required=True, choices=LEGAL_FORM_TYPE_CHOICES)
    inn = StringField(required=True, verbose_name='ИНН')

    created = DateTimeField()
    closed = DateTimeField()


class ProviderBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    REQUIRED_BINDS = ('pr',)
