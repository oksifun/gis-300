# -*- coding: utf-8 -*-
from datetime import datetime

from mongoengine import (
    StringField, EmbeddedDocument, ListField, ReferenceField,
    EmbeddedDocumentField, DateTimeField, BooleanField, ObjectIdField,
    DynamicField, EmbeddedDocumentListField, FloatField, URLField,
)

from app.personnel.models.denormalization.caller import (
    AccountEmbeddedPosition, ProviderEmbedded)
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.choices import (
    PROCESSING_TYPES_CHOICES,
    PROCESSING_SOURCES_CHOICES,
)


class ProviderCallEmbedded(EmbeddedDocument):
    """Вызываемый/Звонящий провайдер, записанный в истории вызовов."""
    id = ObjectIdField(db_field="_id")
    str_name = StringField(verbose_name="Название компании")
    phone_number = StringField(
        verbose_name="Номер телефона",
    )

    @property
    def get_provider_id(self):
        return str(self.id)


class AnsweringPersonEmbedded(EmbeddedDocument):
    """Человек, отвечающий на вызов в дозвоне."""
    id = ObjectIdField(db_field="_id")
    name = StringField(verbose_name="ФИО сотрудника")
    position = StringField(verbose_name='Должность сотрудника')
    phone_number = StringField(verbose_name="Номер телефона")
    provider = EmbeddedDocumentField(ProviderEmbedded)


class SaleTaskAnsweringPersonEmbedded(EmbeddedDocument):
    """Отвечающие на звонок организация или человек в дозвоне."""
    provider = EmbeddedDocumentField(ProviderCallEmbedded)
    person = EmbeddedDocumentField(AnsweringPersonEmbedded)

    @property
    def phone_number(self):
        """Номер, на который будет отправлен звонок."""
        answering = self.provider or self.person
        return answering.phone_number


class SettingsPayments(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    and_string = ListField(
        StringField(),
        db_field='and',
        verbose_name="все слова для поиска"
    )
    not_string = ListField(
        StringField(),
        db_field='not',
        verbose_name="исключающие слова"
    )

    # legacy - String. why?
    doc = StringField(verbose_name="ссылка на тип документа")

    email = ListField(
        StringField(),
        verbose_name="список email для рассылки запросов реестров"
    )
    inns = ListField(StringField(), verbose_name="список inn для поиска")


class ProcessingServiceEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    type = StringField(choices=PROCESSING_TYPES_CHOICES, default=None)
    code = StringField(null=True)
    source = StringField(choices=PROCESSING_SOURCES_CHOICES)


class ProviderProcessingEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    is_active = BooleanField(default=True)
    # удалить
    service = DynamicField()


class BankAccount(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    bic = ReferenceField(
        'processing.models.billing.provider.BankProvider',
        required=True,
        verbose_name='Ссылка на банк'
    )

    name = StringField(verbose_name='Название счета')
    number = StringField(verbose_name='Номер счета')
    service_codes = ListField(StringField(), verbose_name='Код услуги')
    contract_number = StringField(
        required=True,
        default='',
        verbose_name='Номер договора'
    )
    processing_service = StringField()

    processing_services = EmbeddedDocumentListField(
        ProcessingServiceEmbedded,
        verbose_name='Описания процессингов'
    )

    date_from = DateTimeField()  # Optional(Date),  # дата открытия
    active_till = DateTimeField()


class BankContract(EmbeddedDocument):
    """
    Договоры с банками
    """
    id = ObjectIdField(db_field="_id")
    bank = ReferenceField(
        'processing.models.billing.provider.BankProvider',
        required=True,
        verbose_name='Ссылка на банк',
    )
    name = StringField(verbose_name='Имя договора')
    number = StringField(verbose_name='Номер договора')
    date = DateTimeField(verbose_name='Дата договора')
    bank_fee = FloatField(verbose_name='Комиссия банка по договору')


class EmbeddedSalesProviderStatus(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", required=True)
    status = StringField(required=True)


class EmbeddedMajorWorker(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", required=True)
    email = StringField(null=True)
    last_name = StringField(null=True)
    first_name = StringField(null=True)
    patronymic_name = StringField(null=True)
    str_name = StringField(null=True)
    short_name = StringField(null=True)
    phones = EmbeddedDocumentListField(
        DenormalizedPhone,
        verbose_name="Список телефонов"
    )
    position = EmbeddedDocumentField(AccountEmbeddedPosition)
    _type = ListField(StringField())


class CashOnlineEmbedded(EmbeddedDocument):
    preference = ObjectIdField(verbose_name='Настройки и информация о кассах')
    active = BooleanField(default=False, verbose_name='Подключена касса')


class ProviderSMSSettings(EmbeddedDocument):
    """
    Настройки СМС-информирования
    """
    SMSProvider = (
        ('none', 'нет'),
        ('iqsms', 'iqsms'),
        ('stream', 'stream-telecom'),
    )

    provider = StringField(choices=SMSProvider, default='none')
    user = StringField(verbose_name='логин')
    password = StringField(verbose_name='пароль')
    sender_name = StringField(verbose_name='имя отправителя')


class AutoSettings(EmbeddedDocument):
    """
    Автоматический сбор показаний с приборов учета
    """
    auto_daily = BooleanField(verbose_name='суточные')
    auto_hourly = BooleanField(verbose_name='часовые')
    auto_total = BooleanField(verbose_name='тотальные')


class MailingEmbedded(EmbeddedDocument):
    slip = BooleanField(default=False)
    notify = BooleanField(default=False)
    docs = BooleanField(default=True)


class EmbeddedTelephonySettings(EmbeddedDocument):
    token = StringField(
        verbose_name="Токен для доступа к API",
        required=False,
        null=True,
    )
    url = URLField(
        verbose_name="Урл для доступа к телефонии",
        required=False,
        null=True,
    )
    start_sync_datetime = DateTimeField(
        verbose_name="Дата активации синхронизации",
        default=datetime.now,
        required=False,
        null=True,
    )
    last_full_sync_datetime = DateTimeField(
        verbose_name="Дата последней полной синхронизации",
        default=datetime.now,
        required=False,
        null=True,
    )
    hostname = StringField(
        verbose_name='Адрес домена, с которого забираются звонки',
        required=False,
        null=True,
    )


class BicEmbedded(EmbeddedDocument):
    id = ObjectIdField(
        db_field='_id',
        required=True,
        verbose_name='Ссылка на полный BIC документ'
    )
    # Бывш. NEWNUM
    BIC = StringField()
    # Бывш. NAMEP
    NameP = StringField()
    DateIn = DateTimeField()
    # Бывш. KSNP
    Account = StringField()


class ProviderRelationsEmbedded(EmbeddedDocument):
    provider = ObjectIdField(verbose_name='Подконтрольная организации')
    houses = ListField(
        ObjectIdField(),
        verbose_name='Список разрешенныз домов'
    )


class ActorProviderEmbedded(EmbeddedDocument):
    """Организация пользователя"""
    id = ObjectIdField(required=True, db_field='_id')
    str_name = StringField(verbose_name='Наименование')
    inn = StringField(verbose_name='ИНН')
    client_access = BooleanField()
    business_types = ListField()
    gis_online_changes = BooleanField()
    url = StringField()
    online_cash = DynamicField()
    phones = EmbeddedDocumentListField(DenormalizedPhone,
                                       verbose_name="Список телефонов")
