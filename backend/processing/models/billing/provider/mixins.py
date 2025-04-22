# -*- coding: utf-8 -*-
from mongoengine import (
    StringField, DictField, ListField, ReferenceField, EmbeddedDocumentField,
    DateTimeField, BooleanField, DynamicField, EmbeddedDocumentListField,
    ObjectIdField,
)

from processing.models.billing.business_type import BusinessType
from processing.models.billing.embeddeds.address import Address
from processing.models.billing.embeddeds.geo_point import GeoPoint
from processing.models.choices import (
    LEGAL_FORM_TYPE_CHOICES,
    CALC_SOFTWARE_TYPE_CHOICES,
    CalcSoftwareType,
    LegalFormType)
from processing.models.billing.provider.embeddeds import (
    BankContract,
    BankAccount,
    AutoSettings,
    ProviderSMSSettings,
)


class BankAndProviderMixin:
    # Общие поля
    legal_form = StringField(
        required=True,
        choices=LEGAL_FORM_TYPE_CHOICES,
        default=LegalFormType.none,
    )
    str_name = StringField()
    name = StringField(verbose_name="Название")
    business_types = ListField(
        ReferenceField(BusinessType),
        verbose_name="Список видов деятельности"
    )
    address = EmbeddedDocumentField(
        Address, verbose_name="почтовый и фактический адрес")

    postal_address = StringField(verbose_name="Почтовый адрес")
    postal_address_point = EmbeddedDocumentField(
        GeoPoint,
        verbose_name="координаты, физический адрес"
    )
    real_address = StringField(verbose_name="Фактический адрес")
    real_address_point = EmbeddedDocumentField(
        GeoPoint,
        verbose_name="координаты, физический адрес"
    )
    correspondence_address = StringField(
        verbose_name="Адрес для корреспонденции"
    )
    correspondence_address_point = EmbeddedDocumentField(
        GeoPoint,
        verbose_name="координаты, адрес для корреспонденции"
    )
    automation_settings = EmbeddedDocumentField(
        AutoSettings,
        verbose_name="координаты, адрес для корреспонденции",
    )
    # legacy - Denormalized(
    # CRMEvent, ['type', 'created_at', 'date', 'status', 'result'])
    crm_last_event = DictField(
        verbose_name="Последнее запланированное событие по организации"
    )  # TODO delete this field
    # legacy - Denormalized(
    # CRMAction, ['type', 'created_at', 'date', 'status', 'result'])
    crm_last_action = DictField(
        verbose_name="Последнее действие по организации"
    )  # TODO delete this field
    calc_software = StringField(
        choices=CALC_SOFTWARE_TYPE_CHOICES,
        default=CalcSoftwareType.OTHER,
        verbose_name="расчет"
    )
    # legacy - Optional(OwnerDiff, soft_default=OwnerDiff)
    owner_diff = DictField(
        required=False,
        verbose_name="Данные продажников для этой организации"
    )  # TODO delete this field
    # legacy - PublicImageFile
    from processing.models.billing.files import Files
    logo_image = EmbeddedDocumentField(Files)

    # реквизиты
    ogrn = StringField(verbose_name='ОГРН')
    inn = StringField(verbose_name='ИНН')
    okopf = StringField(verbose_name='ОКОПФ', null=True)
    okved = StringField(verbose_name='ОКВЕД', null=True)
    bank_accounts = ListField(EmbeddedDocumentField(BankAccount))

    # Остальные поля, индивидуальные для каждой модели
    accountant = DynamicField(verbose_name="глав. бух")
    chief = DynamicField(verbose_name="директор/председатель")
    import_statements_begin_date = DateTimeField()
    email = StringField()
    url = StringField(verbose_name='Базовый URL для жителей')
    url_managers = StringField(verbose_name='Базовый URL для сотрудников')

    postal_address_fias = DynamicField()
    crm_status = StringField(default='new')  # TODO delete this field
    okfs = DynamicField()
    banks_contracts = EmbeddedDocumentListField(
        BankContract
    )
    postal_address_house_bulk = DynamicField()
    phones = DynamicField()
    site = DynamicField()
    real_address_fias = DynamicField()
    real_address_flat = DynamicField()
    okpo = DynamicField()
    okdp = DynamicField()
    inherit_parent_rights = DynamicField()
    terminal = DynamicField()
    real_address_kladr_code = DynamicField()
    okato = DynamicField()
    postal_address_kladr_code = DynamicField()
    signs = DynamicField()  # TODO delete this field
    real_address_house_number = DynamicField()
    okonh = DynamicField()
    docs = DynamicField()  # TODO delete this field
    postal_address_flat = DynamicField()
    services = DynamicField()  # TODO delete this field
    kpp = DynamicField()
    managers = DynamicField()  # TODO delete this field
    postal_address_house_number = DynamicField()
    real_address_house_bulk = DynamicField()
    redmine = DynamicField()
    dossier = DynamicField()
    request_blank = ObjectIdField()
    debt_claim_template = DynamicField()
    debt_notice_template = DynamicField()
    automation = DynamicField()
    _redmine_14593 = DynamicField()
    email_settings = DictField()
    reform_id = DynamicField()
    banks = DynamicField()
    from_reform_db = DynamicField()
    prefix_barcode = StringField(
        default='',
        verbose_name="префикс штрих кода",
        null=True
    )
    secured_ip = DynamicField()
    ogrn_issue_date = DateTimeField()
    ogrn_issued_by = DynamicField()
    automation_token = DynamicField()
    automation_imsi = DynamicField()
    inn_issue_date = DateTimeField()
    inn_issued_by = StringField()
    client_ids = DynamicField()
    sber_online = BooleanField()
    sbis = BooleanField()  # TODO delete this field

    sms_settings = EmbeddedDocumentField(ProviderSMSSettings)

    settings_payments = DynamicField()
    online_cash = DynamicField()

