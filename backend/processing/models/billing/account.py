import re
from datetime import datetime
from fractions import Fraction
from random import randint
from uuid import uuid4

import mongoengine
from dateutil.relativedelta import relativedelta

from app.auth.models.embeddeds import AccountEmbedded

from bson import ObjectId
from mongoengine import Document, StringField, EmbeddedDocument, \
    EmbeddedDocumentListField, EmbeddedDocumentField, BooleanField, \
    DateTimeField, ListField, EmailField, IntField, ObjectIdField, \
    ReferenceField, DictField, FloatField, DynamicEmbeddedDocument, \
    DynamicField, ValidationError, Q, queryset_manager, QuerySet

import settings
from app.caching.models.denormalization import DenormalizationTask

from lib.helpfull_tools import get_mail_templates

from app.area.models.area import Area
from processing.models.billing.base import HouseGroupBinds, BindsPermissions, \
    BindedModelMixin, FilesDeletionMixin
from processing.models.billing.common_methods import get_area_house_groups
from processing.models.billing.embeddeds.location import Location
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.embeddeds.area import DenormalizedAreaWithFias
from processing.models.billing.embeddeds.account import TelegramChatId
from processing.models.billing.fias import Fias
from processing.models.billing.files import Files
from processing.models.billing.provider.main import Provider
from processing.models.billing.session import Session
from processing.models.choices import *
from processing.models.billing.embeddeds.account import TenantCallEmbedded

import logging

from processing.models.mixins import WithPhonesMixin

# LOGGER
logger = logging.getLogger('c300')


class PlaceOrigin(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    fias = EmbeddedDocumentField(Location)
    custom_str = StringField(
        null=True,
        verbose_name="Откуда прибыл",
    )
    is_custom = BooleanField(
        required=True,
        default=False,
        verbose_name="Адрес проставлен вручную"
    )


class CoefReason(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    number = StringField(verbose_name="Номер документа")
    datetime = DateTimeField(verbose_name="Дата оформления договора")
    comment = StringField(verbose_name="Пояснения")


class Coef(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    coef = ObjectIdField(
        required=True,
        verbose_name="Ссылка на документ коэффициента",
    )
    period = DateTimeField(verbose_name="Период")
    value = FloatField(verobose_name="Значение")
    reason = EmbeddedDocumentField(CoefReason)


class FamilyRole(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # legacy - Ref(FamilyRoleCatalogue)
    role = ObjectIdField(
        required=True,
        verbose_name="роль жителя"
    )
    # legacy - Ref('Tenant')
    related_to = ObjectIdField(
        required=True,
        verbose_name="совместно проживающие, к которым применена роль",
    )


class FamilyRelations(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", default=ObjectId)
    # legacy - Ref('Tenant')
    householder = ObjectIdField(
        verbose_name="Ответственный, с которым проживает житель",
    )
    relations = EmbeddedDocumentListField(FamilyRole)


class TenantStatus(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    is_temporary = BooleanField(
        required=False,
        default=False,
        verbose_name="Временная регистрация, проживание")


class DateMixin:
    id = ObjectIdField(db_field="_id")
    date_from = DateTimeField(null=True)
    date_till = DateTimeField(null=True)

    @property
    def is_actual(self) -> bool:
        """Актуальная запись?"""
        now = datetime.now()
        return self.date_from is not None and self.date_from < now \
            and (self.date_till is None or self.date_till > now)


class PeriodScheduleField(EmbeddedDocument, DateMixin):
    value = EmbeddedDocumentField(TenantStatus)


class AccountingEmbedded(EmbeddedDocument, DateMixin):
    pass


class PropertyShareDocEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', null=True)
    file = EmbeddedDocumentField(Files, null=True)


class PropertyShareHistoryEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    op = StringField()
    tenant = ObjectIdField(null=True)
    comment = StringField(null=True)
    date = DateTimeField(null=True)
    doc = EmbeddedDocumentField(PropertyShareDocEmbedded, null=True)
    value = ListField(IntField(), null=True)
    right_number = StringField(
        null=True,
        verbose_name='Номер записи о регистрации'
    )


class PropertyCertificateEmbedded(EmbeddedDocument):
    """
    Детали сертификата о праве собственности
    """
    series = StringField(null=True, verbose_name='Серия')
    number = StringField(null=True, verbose_name='Номер')
    issued_at = DateTimeField(null=True, verbose_name='Дата выдачи')
    encumbrance = StringField(
        null=True,
        verbose_name='Существующие ограничения(обременения) права',
    )
    arbitrary_number = StringField(
        null=True,
        verbose_name='Кадастровый (или условный) номер',
    )
    supporting_documents = StringField(
        null=True,
        verbose_name='Документы-основания',
    )
    registration_number = StringField(
        null=True,
        verbose_name='Запись регистрации №',
    )
    registration_date = DateTimeField(
        null=True,
        verbose_name='Дата регистрации',
    )
    warrant = EmbeddedDocumentField(
        Files,
        verbose_name='Свидетельство о праве собственности',
    )


class TenantContract(EmbeddedDocument):
    """
    Запись договора
    """
    document_type = StringField(
        choises=TENANT_CONTRACT_TYPE_CHOICES,
        default=TenantContractType.MANAGEMENT,
        db_field='type',
        required=True,
    )
    file = EmbeddedDocumentField(Files)
    date = DateTimeField(verbose_name='Дата договора')
    number = StringField(verbose_name='Номер договора')
    subscriber_code = StringField(
        null=True,
        verbose_name='Внутренний код абонента'
    )


class OwnerShipEmbedded(EmbeddedDocument):
    certificate = EmbeddedDocumentField(PropertyCertificateEmbedded)
    _type = StringField(
        db_field='type',
        default='private',
        required=True,
    )
    inherit_saldo = BooleanField()
    is_owner = BooleanField()
    started_at = DateTimeField()
    verified_with_rosreestr = BooleanField(
        null=True, verbose_name='Сверено с росреестром'
    )
    right_number = StringField(
        null=True,
        verbose_name='Номер записи о регистрации'
    )
    property_share = ListField(IntField())
    contracts = EmbeddedDocumentListField(TenantContract)
    property_share_history = EmbeddedDocumentListField(
        PropertyShareHistoryEmbedded
    )

    @classmethod
    def get_proper_share(cls, property_share: list) -> list:
        """Корректное значение доли владения"""
        if not isinstance(property_share, list):
            property_share = [0, 1]
        elif len(property_share) < 2:  # [2]
            property_share = [1, property_share[0]]
        elif len(property_share) > 2:
            property_share = property_share[0: 2]
        elif property_share[0] == 0 and property_share[1] != 1:  # [0, 2]
            property_share[1] = 1

        return property_share

    @property
    def proper_share(self) -> list:
        """Корректное значение доли владения"""
        return self.get_proper_share(self.property_share)

    def create_share_history(self,
            started_at: datetime = None, owner_id: ObjectId = None):
        """Создать запись в истории владения"""
        history = PropertyShareHistoryEmbedded(
            # doc=None,  # : PropertyShareDocEmbedded
            id=ObjectId(),  # нет значения по умолчанию
            tenant=owner_id,  # новый собственник?
            op='total',  # 'inc' / 'red'
            comment=None,  # 'sale_contract' / 'qualification'
            value=self.property_share,  # начальное значение
            date=started_at,  # дата изменения доли владения
        )

        assert isinstance(self.property_share_history, list)  # по умолчанию
        self.property_share_history.append(history)

        return history


class Statuses(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", required=True, default=ObjectId)
    living = EmbeddedDocumentListField(
        PeriodScheduleField,
        default=[],
        verbose_name="Статусы проживания"
    )
    ownership = EmbeddedDocumentField(
        OwnerShipEmbedded,
        verbose_name="Информация о собственности"
    )
    # legacy - PeriodScheduleField(TenantStatus)
    registration = EmbeddedDocumentListField(
        PeriodScheduleField,
        default=[],
        verbose_name="Статусы регистрации")

    # legacy - HistoryField(Accounting)
    accounting = EmbeddedDocumentField(
        AccountingEmbedded,
        verbose_name="Учет лицевого счета"
    )

    @classmethod
    def is_active(cls, date_from: datetime, date_till: datetime) -> bool:
        """Действующий период?"""
        now = datetime.now()

        return date_from is not None and date_from < now \
            and (date_till is None or date_till > now)

    @property
    def is_living(self) -> bool:
        """Проживает?"""
        return self.living and any(
            Statuses.is_active(liv.date_from, liv.date_till)
            # liv.value - содержит лишь признак "временности"
            for liv in self.living  # : list
            if isinstance(liv, PeriodScheduleField)
        )

    @property
    def is_owning(self) -> bool:
        """Владелец?"""
        return isinstance(self.ownership, OwnerShipEmbedded) and (
            self.ownership.started_at is not None
            and self.ownership.property_share
            and self.ownership.property_share[0] > 0
        )

    @property
    def is_registered(self) -> bool:
        """Зарегистрирован?"""
        return self.registration and any(
            Statuses.is_active(reg.date_from, reg.date_till)
            # reg.value - содержит лишь признак "временности"
            for reg in self.registration  # : list
            if isinstance(reg, PeriodScheduleField)
        )

    @property
    def is_accounting(self) -> bool:
        """
        Ведется (бухгалтерский) учет?

        Прекращение учета означает закрытие ЛС.
        """
        return isinstance(self.accounting, AccountingEmbedded) \
            and Statuses.is_active(
                self.accounting.date_from, self.accounting.date_till
            )


class SaldoQueueTask(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # legacy - AccrualsSectorType
    sector_code = StringField(
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        default=AccrualsSectorType.RENT)
    date = DateTimeField()


class Tasks(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # legacy - Optional([SaldoQueueTask], soft_default=[])
    saldo = EmbeddedDocumentListField(
        SaldoQueueTask,
        default=[],
        verbose_name="список задач для перерасчета сальдо")


class Settings(DynamicEmbeddedDocument):
    pass


class RentingContract(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # alias - Required(RENTING_CONTRACT_TYPE)
    renting_contract_type = StringField(
        db_field='type',
        choices=RENTING_CONTRACT_TYPE_CHOICES,
        required=False,
        null=True,
        verbose_name="Тип договора найма")

    date = DateTimeField(
        null=True, verbose_name="Дата начала договора найма")


class PrivilegeBind(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # legacy - [Ref('Tenant')]
    accounts = ListField(
        ReferenceField('processing.models.billing.account.Account'),
        verbose_name="ЛС, на которые распространяются льготы, включая текущий "
                     "(пустой список — для всех членов семьи)")

    # legacy - Required(Ref('Privilege'))
    privilege = ObjectIdField(
        # 'processing.models.billing.privilege.Privilege',
        required=True,
        verbose_name="ссылка на льготу из справочника")
    date_from = DateTimeField(verbose_name="дата начала действия льготы")
    date_till = DateTimeField(verbose_name="дата окончания действия льготы")
    is_individual = BooleanField(
        required=True,
        default=True,
        verbose_name="получается жителем самостоятельно")
    family_size = IntField(required=False,
                           verbose_name="численность семьи")


class PrivilegesInfo(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    kodpol = StringField(verbose_name="код получателя")

    # legacy - Ref('PrivateTenant')
    patron = ReferenceField(
        'processing.models.billing.account.Account',
        verbose_name="содержатель иждевенца")


class Military(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    is_reserved = BooleanField(
        required=True,
        default=True,
        verbose_name="обязан ли")
    is_registered = BooleanField(
        required=True,
        default=False,
        verbose_name="на учете")
    description = StringField(
        db_field="discription",
        null=True,
        verbose_name="отметки военкомата",
    )


class BillSendingEmbedded(EmbeddedDocument):
    mailing_type = StringField(verbose_name='Вид отправки (notify или slip)')
    sector = StringField(verbose_name='Название направления')
    sent = DateTimeField(verbose_name='Время рассылки')
    token = ObjectIdField(verbose_name='Токен/id файла')
    alive_till = DateTimeField(verbose_name='Срок действия токена')
    doc = ObjectIdField(
        verbose_name='Документ начисления, по которому выставлялась квитанция '
                     'последний раз'
    )


class BillSendingMixin:
    """
    Хранение состояний связанных с рассылкой квитанций на оплату (счетов)
    TODO: Удалить после релиза #347561, так как перенесено в другое место
    """
    b_settings = EmbeddedDocumentListField(BillSendingEmbedded)

    def find_bill_settings(self, sector, mailing_type):
        """
        Значения после отправки постоянно обновляются, поэтому для каждого
        направления может существовать не более одного состояния "отправлено".
        """
        for bill_setting in self.b_settings:
            if bill_setting.sector == sector:
                if bill_setting.mailing_type == mailing_type:
                    return bill_setting
                # Проверка легаси документов без вида отправки
                elif bill_setting.mailing_type is None:
                    return bill_setting
        return None

    def mark_bill_as_sent(self, sector, doc_id, mailing_type, file_id):
        """
        Проставляет статус "отправлено" для документа у жителя.
        Может быть либо "slip" либо "notify".
        """
        alive_till = datetime.now() + relativedelta(days=30)
        setting = self.find_bill_settings(sector, mailing_type)
        if setting:
            setting.sent = datetime.now()
            setting.doc = doc_id
            setting.mailing_type = mailing_type
            setting.token = file_id
            setting.alive_till = alive_till
        else:
            bill_sending_embedded = BillSendingEmbedded(
                sector=sector,
                sent=datetime.now(),
                doc=doc_id,
                mailing_type=mailing_type,
                token=file_id,
                alive_till=alive_till,
            )
            self.b_settings.append(bill_sending_embedded)

        getattr(self, 'save')()


class EmailsManipulatorMixin:
    # TODO Это непотребство создано для того, чтобы работала активация
    #  и прочая нотификация юзера до тех пор, пока не будет задеплоен
    #  логин на Actor'ах. После этого этот миксин должен быть уничтожен
    SALT_SIZE = 10
    (
        # BLOCK_TEMPLATE,  # Оповещение о блокировке регистрации
        # RECOVERY_TEMPLATE,  # Восстановление пароля
        ACTIVATION_TEMPLATE,  # Начало активации аккаунта и подтверждение почты
        PASSWORD_TEMPLATE,  # Предоставление пароля для входа в область
        NEW_PASSWORD_TEMPLATE,
        DEACTIVATION_TEMPLATE,  # Приостановление доступа
        # UNBLOCK_TEMPLATE,  # Разблокировка регистрации

    ) = get_mail_templates([
        # 'on_activation_blocking.html',
        # 'password_reset.html',
        'activate.html',
        'password.html',
        'password_new.html',
        'on_deactivate.html',
        # 'on_unblocking.html'
    ])

    @property
    def is_blocked(self):
        """
        Свойство, определяющее заблокирована активация пользователя или нет.
        Значение с которым сравнивается activation_step складывается
        из исходного значения для 2го шага(2)
        и максимального количества попыток (сейчас 3),
        """
        return (getattr(self, 'activation_step', 0) or 0) >= 5

    @property
    def can_login(self):
        from utils.crm_utils import provider_can_access

        provider_id = self._get_provider_id()
        return (
                self.has_access
                and self.activation_code is None
                and self.activation_step is None
                and provider_can_access(provider_id)
        )

    @classmethod
    def compare_password_with_hash(cls, password, password_hash_with_salt):
        """
        Функция для сравнения хеш + соль с паролем.
        Тип password_hash_with_salt должен быть bytes.
        Возвращает True если пароли равны или False если пароли не равны
        """
        import binascii

        salt = password_hash_with_salt[-cls.SALT_SIZE * 2:]
        ph = cls.password_hash(password, binascii.a2b_hex(salt))

        if ph != password_hash_with_salt:
            return False

        return True

    @classmethod
    def password_hash(cls, password, salt_for_password=None):
        """
        Функция для создания хеша от пароля с добавлением соли.
        Тип salt_for_password должен быть bytes.
        На выходе получается хеш + соль. Размер соли на выходе SALT_SIZE * 2
        """
        import os
        import sha3
        password_hash = sha3.keccak_256()

        if salt_for_password is None:
            salt = os.urandom(cls.SALT_SIZE)
        else:
            if not isinstance(salt_for_password, bytes):
                raise Exception('Type of salt_for_password must be bytes')
            salt = salt_for_password

        password_hash.update(password.encode() + salt)
        import binascii
        return password_hash.hexdigest() + binascii.hexlify(salt).decode()

    @staticmethod
    def generate_new_password():
        from uuid import uuid4

        return uuid4().hex[:8]

    def check_can_login(self):
        return all((
            self.can_login,
            self.password
        ))

    def reset_password(self, code):
        """Восстановление пароля"""
        self.check_can_login()

        if code != self.password_reset_code:
            raise ValidationError('Неверный код')

        password = self.generate_new_password()
        self.password = self.password_hash(password)
        self.password_reset_code = None
        self.save()
        self.send_password_mail(password)

    def send_activation_mail(self):
        """
        Отправка письма с со ссылкой на активацию и подтверждение квартиры
        """

        provider = Provider.objects(
            id=self._get_provider_id()
        ).as_pymongo().only('id', 'name').first()
        from app.messages.core.email.extended_mail import AccessMail
        mail = AccessMail(
            provider_id=provider['_id'],
            addresses=self.email,
            subject='Подтверждение e-mail',
            body=self.ACTIVATION_TEMPLATE.render(
                dict(
                    account=self,
                    base_url=self._get_base_url(),
                    title='Подтверждение эл. адреса почты',
                    provider_name=provider['name']
                )
            )
        )
        mail.send()

    def send_password_mail(self, password):
        """
        Отправка письма со сгенерированным паролем для входа
        после регистрации
        """
        logger.debug('send_password_mail starts')
        from app.messages.core.email.extended_mail import AccessMail
        mail = AccessMail(
            provider_id=self._get_provider_id(),
            addresses=self.email,
            subject='Новый пароль',
            body=self.PASSWORD_TEMPLATE.render(
                {
                    'is_tenant': "Tenant" in self._type,
                    'login': self.email if "Tenant" in self._type else self.number,
                    'account': self,
                    'password': password,
                    'base_url': self._get_base_url(),
                    'title': 'Новый пароль',
                }

            )
        )
        mail.send()

    def send_new_password_mail(self, password):
        """
        Отправка письма со сгенерированным паролем для входа
        после повторного предоставления доступа
        """
        logger.debug('send_new_password_mail starts')
        from app.messages.core.email.extended_mail import AccessMail
        mail = AccessMail(
            provider_id=self._get_provider_id(),
            addresses=self.email,
            subject='Новый пароль',
            body=self.NEW_PASSWORD_TEMPLATE.render(
                dict(
                    account=self,
                    password=password,
                    base_url=self._get_base_url(),
                    title='Новый пароль'
                )
            )
        )
        mail.send()

    def send_password_reset_mail(self):
        """Отправка письма с паролем восстановления"""

        if not self.check_can_login():
            raise ValidationError('Нет доступа!')
        self.password_reset_code = self.generate_new_password()
        self.save()
        from app.messages.core.email.extended_mail import AccessMail
        mail = AccessMail(
            addresses=self.email,
            subject='Восстановление пароля',
            body=self.RECOVERY_TEMPLATE.render(
                dict(
                    account=self,
                    title='Восстановление пароля',
                    base_url=self._get_base_url()
                )
            )
        )
        mail.send()

    def send_activation_blocked_mail(self):
        """
        Действия при попытке зарегистрировать/активировать пользователя
        с превышением попыток ввода номера квартиры.
        Отправка уведомляющего письма.
        """
        # удаляем код активации и отправляем письмо только один раз

        if self.activation_code:
            self.activation_code = None
            self.has_access = False
            self.save()
            if self.email:
                from app.messages.core.email.extended_mail import AccessMail
                mail = AccessMail(
                    addresses=self.email,
                    subject='Активация ЛК заблокирована',
                    body=self.BLOCK_TEMPLATE.render(dict(account=self))
                )
                mail.send()

        raise ValidationError(
            'Превышено количество попыток активации. '
            'Лицевой счёт заблокирован, обратитесь в вашу '
            'управляющую организацию для разблокировки'
        )

    def send_deactivation_mail(self):
        """Отправка письма, уведомляющая о приостановлении доступа в кабинет"""

        if self.email:
            from app.messages.core.email.extended_mail import AccessMail
            mail = AccessMail(
                provider_id=self._get_provider_id(),
                addresses=self.email,
                subject='Приостановление доступа в систему',
                body=self.DEACTIVATION_TEMPLATE.render(
                    dict(account=self, title='Доступ приостановлен!')
                )
            )
            mail.send()

    def send_registration_unlock_mail(self):
        """Отправка письма о разблокировке регистарции"""

        if self.email:
            from app.messages.core.email.extended_mail import AccessMail
            mail = AccessMail(
                addresses=self.email,
                subject='Регистрация ЛК разблокирована',
                body=self.UNBLOCK_TEMPLATE.render(
                    dict(
                        account=self,
                        title='Регистрация ЛК разблокирована'
                    )
                )
            )
            mail.send()

    def access_trigger(self):
        """Рассылка сообщений при смене прав доступа в систему"""
        logger.debug('access_trigger starts')
        if self._created or 'has_access' not in self._changed_fields:
            return

        actor = self.get_actor()
        if self.has_access:
            logger.debug('has_access -> True')
            self.get_access_date = datetime.now()
            actor.has_access = False
            actor.get_access_date = datetime.now()
            actor.activation_code = self.activation_code = self.generate_new_password()
            actor.activation_step = None
            actor.password = None
            actor.owner.email = self.email
            username = self.email if "Tenant" in self._type else self.number
            logger.debug('username: %s, type: %s', username, self._type)
            actor.username = username
            logger.debug(f'actor.owner.owner_type == "Tenant": '
                         f'{actor.owner.owner_type == "Tenant"}')
            ignore_mirroring = actor.owner.owner_type == 'Tenant'
            actor.save(ignore_mirroring=ignore_mirroring)
            if self.email:
                actor.send_activation_mail()
        else:
            logger.debug('has_access -> False')
            Session.objects(account__id=self.id).update(is_active=False)
            if actor.has_access:
                actor.update(has_access=False)
            actor.activation_code = self.activation_code = None
            if self.email:
                actor.send_deactivation_mail()

    def _get_provider_id(self):
        from app.house.models.house import House
        if "Tenant" in self._type:
            return House.find_bound_provider(self.area.house.id)
        if "Worker" in self._type:
            return self.department['provider']  # откуда тут dict???

    def _get_base_url(self):
        """Получение базовой URL"""
        from processing.models.billing.provider.main import Provider

        provider_id = self._get_provider_id()
        try:
            provider = Provider.objects.get(id=provider_id)
        except mongoengine.DoesNotExist as dne:
            logger.error('Не найден провайдер по id %s: %s', provider_id, dne)
            raise
        return provider.get_url()


class AssessmentEmbedded(EmbeddedDocument):
    up = IntField(verbose_name="Положительные оценки", default=0)
    down = IntField(verbose_name="Отрицательные оценки", default=0)


class RecurrentPaymentEmbedded(EmbeddedDocument):
    id = ObjectIdField(required=True, default=ObjectId, db_field="_id")
    recurrent = BooleanField(default=False, verbose_name="сущесвует ли rid")
    sector = StringField(verbose_name='Название направления')
    fast = BooleanField(verbose_name='Активирован ли режим быстрого платежа')
    auto = BooleanField(verbose_name='Активирован ли режим автоплатежа')
    upd = DateTimeField(verbose_name='Когда настройка была обновлена')
    card = StringField(verbose_name='Номер карты')
    paid = DateTimeField(verbose_name='Дата совершения платежа')
    _type = StringField(verbose_name='Эквайринг',
                        choices=PROCESSING_TYPES_CHOICES)


class Account(FilesDeletionMixin, Document, BindedModelMixin,
              BillSendingMixin, EmailsManipulatorMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Account',
        'index_background': True,
        'auto_create_index': False,
        'strict': False,
        'indexes': [
            'phones.add',
            'phones.str_number',
        ],
    }

    _type = ListField(StringField(required=True))
    monitoring_enabled = BooleanField(default=False)

    inn = StringField(verbose_name="ИНН")

    # legacy - HistoryField(Email)
    email = StringField(verbose_name="Пользовательский эл. адрес")

    # 'avatar': NId(Model)
    avatar = ObjectIdField(verbose_name="Пользовательское изображение")

    # legacy -Required(All(NMatch(r'\d{0,13}$'),
    # Any(None, lambda number: number.zfill(13))), default=None)
    number = StringField(
        required=True,
        regex='\d{0,13}',
        verbose_name="Номер ЛС")

    # legacy - [Phone]
    phones = EmbeddedDocumentListField(DenormalizedPhone,
                                       verbose_name="Список телефонов")
    comment = StringField(verbose_name="Примечания")
    settings = EmbeddedDocumentField(Settings, required=True)
    str_name = StringField(verbose_name="Строка имени")
    # legacy - Denormalized('Provider', ['str_name', 'business_types',
    # 'crm_code', 'secured_ip']),
    # provider = EmbeddedDocumentField(DenormalizedProvider())
    # provider = DictField(verbose_name="Организация")
    provider = DynamicField(verbose_name="Организация")
    email_notify = BooleanField(verbose_name='Получать уведомления по почте?')
    email_slip = BooleanField(verbose_name='Получать квитанции по почте?')
    has_access = BooleanField(
        null=True,
        default=False,
        verbose_name="Имеет доступ в систему")
    get_access_date = DateTimeField(
        verbose_name="Дата получения доступа в систему"
    )
    created_at = DateTimeField(verbose_name="Дата регистрации в системе")
    old_numbers = ListField(
        StringField(),
        verbose_name="Список старых номеров ЛС, "
                     "унаследованных от прошлых версий системы"
    )
    additional_email = EmailField(verbose_name="Дополнительный email-адрес")

    password = StringField(verbose_name="Пароль")

    activation_code = StringField()
    activation_step = IntField()
    activation_tries = IntField(
        required=False,
        default=0,
        verbose_name="Количество попыток активации")
    password_reset_code = StringField()

    # legacy - Model.Id
    user = ObjectIdField(verbose_name="Старый user_id")
    news_count = IntField(
        required=True,
        default=0,
        verbose_name="кол-во прочитанных новостей")
    delivery_disabled = BooleanField(
        null=True,
        default=False,
        verbose_name="отказ от рассылки")

    # legacy - Required(Denormalized(Area, ['house', 'number', 'str_number',
    # 'str_number_full', 'order', 'is_shared'])),  # Информация о квартире
    area = EmbeddedDocumentField(
        DenormalizedAreaWithFias,
        verbose_name="Информация о квартире")

    # legacy - HistoryField([Ref('Room')])
    # rooms = ReferenceField('processing.models.billing.log.History',
    # verbose_name="Проживает в комнатах")
    rooms = ListField(ObjectIdField())

    # legacy - [Coef]
    coefs = EmbeddedDocumentListField(Coef, verbose_name="Коэффициенты")
    family = EmbeddedDocumentField(FamilyRelations)

    # legacy - Required(Statuses, default=Statuses)
    statuses = EmbeddedDocumentField(Statuses, verbose_name="Статусы жильца")

    # legacy - [Ref('Tenant')]
    finance_legacy = ListField(
        ReferenceField('processing.models.billing.account.Account'),
        verbose_name="наследование фин. истории; "
                     "айди жителя, от которого наследуется"
    )

    # legacy - Statuses.Ownership.Contract.ContractFile -
    # is subclass of ImageField
    # cabinet_petition = StringField(verbose_name="Заявление на
    # подключение ЛК собственника.")
    cabinet_petition = DynamicField()

    # legacy - HistoryField(Optional(Boolean, soft_default=False))
    is_responsible = BooleanField(verbose_name="Является ли ответственным")

    is_coop_member = BooleanField(
        required=False,
        default=False,
        verbose_name="Член ТСЖ/ЖСК")

    # legacy - HistoryField(Computed())
    is_super = BooleanField(default=False)

    # legacy - HistoryField(Required(Int, default=0))
    rating = IntField(verbose_name="Рейтинг жителя")
    assessment = EmbeddedDocumentField(
        AssessmentEmbedded,
        verbose_name="Рейтинг жителя",
    )

    # tasks = EmbeddedDocumentField(Tasks, required=False,
    # verbose_name="Задачи на пересчет данных жителя")
    tasks = DictField(
        required=False,
        verbose_name="Задачи на пересчет данных жителя")

    # PrivateTenant block
    sex = StringField(choices=GENDER_TYPE_CHOICES, verbose_name="Пол")
    snils = StringField(verbose_name="СНИЛС")

    photo = EmbeddedDocumentField(
        Files,
        verbose_name="Фотография работника (для карточки в системе)"
    )
    short_name = StringField()
    birth_date = DateTimeField(verbose_name="Дата рождения")
    first_name = StringField(verbose_name="Имя")
    last_name = StringField(verbose_name="Фамилия")
    patronymic_name = StringField(verbose_name="Отчество")

    # legacy - RentingContract
    renting = EmbeddedDocumentField(
        RentingContract,
        verbose_name="Договор найма")

    # legacy - [PrivilegeBind]
    privileges = EmbeddedDocumentListField(
        PrivilegeBind,
        verbose_name="список льгот, закрепленных за жителем")
    citizenship = StringField(verbose_name="Гражданство")

    is_privileged = BooleanField(null=True, default=False)
    # just shut up and take this field
    is_priviledged = BooleanField(required=True, default=False)

    privileges_info = EmbeddedDocumentField(PrivilegesInfo)
    last_name_upper = StringField()
    short_name_upper = StringField()
    nationality = StringField(
        choices=NATIONALITY_CHOICES,
        default=Nationality.RUSSIAN,
        verbose_name="национальность")
    military = EmbeddedDocumentField(
        Military,
        verbose_name="воинская обязанность")
    place_birth = StringField(verbose_name="Место рождения")
    place_birth_fias = StringField(
        null=True,
        verbose_name="ФИАС места рождения",
    )
    place_origin = EmbeddedDocumentField(PlaceOrigin)
    p_settings = EmbeddedDocumentListField(RecurrentPaymentEmbedded)

    # TODO: unknown source
    modified_at = DateTimeField()

    # TODO: unknown source
    task = DictField()

    # TODO: unknown source
    identity_card = DictField()

    # TODO: unknown source
    update_offsets_at = DateTimeField()

    # TODO: unknown source
    update_sectors = DictField()

    # TODO: unknown source
    update_saldo = DynamicField()

    name = StringField()
    legal_form = StringField()  # required=True, default=None
    kpp = StringField()
    ogrn = StringField()

    # ReferenceField('processing.models.billing.account.Account')
    director = DynamicField()

    # ReferenceField('processing.models.billing.account.Account')
    accountant = DynamicField()

    is_developer = BooleanField()
    do_not_accrual = BooleanField()

    entity = ObjectIdField()
    entity_contract = ObjectIdField()

    position_code = StringField()

    # TODO: unknown source
    update_offsets_sectors = DynamicField()

    # TODO: unknown source
    offsets = DynamicField()

    is_deleted = BooleanField()

    _jira = DynamicField()
    _redmine = DynamicField()

    doc_copies = DynamicField()

    department = DynamicField()
    control_info = DynamicField()
    employee_id = IntField()
    position = DynamicField()
    is_invalid = BooleanField()
    timer = DynamicField()

    house = DynamicField()
    _be967_fixed = DynamicField()
    is_autoapi = DynamicField()

    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к организации и группе домов (P,HG и D)'
    )
    _binds_permissions = EmbeddedDocumentField(
        BindsPermissions,
        verbose_name='Привязки к организации и группе домов (P,HG и D)'
    )

    ####
    # GIS
    ####

    gis_uid = StringField(verbose_name='Единый лицевой счет')
    hcs_uid = StringField(verbose_name='Идентификатор ЖКУ')

    # дата принятия в члены ТСЖ/ЖСК
    coop_member_date_from = DateTimeField()  # Optional(Date)

    # ссылка на жителя, соответствующего сотруднику
    tenants = ListField(  # [Optional(Ref(Account))]
        ReferenceField('processing.models.billing.account.Account')
    )

    # история избрания на должность
    election_history = DynamicField()

    def is_anonymous(self):
        """Django compatibility"""
        return False

    def delete(self, **write_concern):
        self.is_deleted = True
        self.save()

    # TODO Нужно сделать корректное сохранение полей, использующих HistoryField
    def save(self, *args, **kwargs):
        if 'Tenant' in self._type:
            raise TypeError('Use Tenant')
        self.restrict_changes()
        self.access_trigger()
        super().save(*args, **kwargs)
        # todo Проверка прав
        # from processing.accounting.accounts_delta import add_account_to_sync
        # add_account_to_sync(**kwargs)
        return self

    @staticmethod
    def generate_password(length=8):
        return uuid4().hex[:length]

    @classmethod
    def get_property_share_by_dict(cls, property_share_history, date_on):
        for p in property_share_history:
            if p['value'][0] == 0 and p['value'][1] == 0:
                p['value'][1] = 1
        total = sum([
            (-1 if x['op'] == 'red' else 1) * Fraction(*x['value'])
            for x in property_share_history if
            x['value'] and (x.get('date') or date_on) <= date_on
        ])
        return [total.numerator, total.denominator]


class ResponsibleTenantGracePeriod(EmbeddedDocument):
    reason = StringField(
        required=True,
        choices=REASON_RESPONSIBLE_TENANT_GRACE_PERIOD,
        verbose_name='Причина предоставления льготного периода. ',
    )
    grace_doc = EmbeddedDocumentField(
        Files,
        null=True,
        blank=True,
        verbose_name="Документ подтверждающий предоставление льготного периода."
    )

    date_from = DateTimeField(
        required=True,
        verbose_name='Дата начала льготного периода.'
    )
    date_till = DateTimeField(
        required=True,
        verbose_name='Дата конца льготного периода.'
    )


class EmbeddedPosition(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    last_name = StringField()
    first_name = StringField()
    patronymic_name = StringField()
    phones = EmbeddedDocumentListField(
        DenormalizedPhone
    )
    email = StringField()
    position_code = StringField(choices=('ch1', 'ch2', 'ch3', 'acc1'))


class TenantSettingsSberAutoPaySector(EmbeddedDocument):
    sector = StringField(choises=ACCRUAL_SECTOR_TYPE_CHOICES)
    state = StringField()


class AccountSettingsEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    agreements_dates = DictField()
    agreements = DictField()
    bill_email_notice = BooleanField()
    limited_access = BooleanField()
    receipt_delivery_address = DynamicField()
    sber_auto_pay = EmbeddedDocumentListField(TenantSettingsSberAutoPaySector)


class Tenant(
    FilesDeletionMixin,
    BindedModelMixin,
    BillSendingMixin,
    EmailsManipulatorMixin,
    WithPhonesMixin,
    Document,
):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Account',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
            'telegram_chats.chat_id',
            'disable_paper_bills',
        ],
    }

    # системные поля
    _type = ListField(StringField(required=True))
    is_deleted = BooleanField()
    is_super = BooleanField(default=False)

    # общие поля Account
    inn = StringField(
        null=True,
        verbose_name="ИНН",
    )
    email = StringField(verbose_name="Пользовательский эл. адрес")
    avatar = ObjectIdField(verbose_name="Пользовательское изображение")
    number = StringField(
        null=True,
        regex=r'\d{0,13}',
        verbose_name="Номер ЛС",
    )
    comment = StringField(verbose_name="Примечания", null=True)
    str_name = StringField(verbose_name="Строка имени")
    has_access = BooleanField(
        required=True,
        default=False,
        verbose_name="Имеет доступ в систему",
    )
    get_access_date = DateTimeField(
        verbose_name="Дата получения доступа в систему",
    )
    created_at = DateTimeField(verbose_name="Дата регистрации в системе")
    old_numbers = ListField(
        StringField(),
        verbose_name="Список старых номеров ЛС, "
                     "унаследованных от прошлых версий системы"
    )
    additional_email = EmailField(verbose_name="Дополнительный email-адрес")
    password = StringField(
        verbose_name="Пароль"
    )
    activation_code = StringField()
    activation_step = IntField()
    activation_tries = IntField(
        required=False,
        default=0,
        verbose_name="Количество попыток активации"
    )
    password_reset_code = StringField()
    user = ObjectIdField(verbose_name="Старый user_id")
    news_count = IntField(
        required=True,
        default=0,
        verbose_name="кол-во прочитанных новостей"
    )
    delivery_disabled = BooleanField(
        required=True,
        default=False,
        verbose_name="отказ от рассылки"
    )
    snils = StringField(verbose_name="СНИЛС", null=True)

    # поля жителя или собственника помещения в доме
    area = EmbeddedDocumentField(
        DenormalizedAreaWithFias,
        verbose_name='Информация о помещении'
    )
    rooms = ListField(
        ObjectIdField(),
        verbose_name='Список комнат квартиры, к которой имеет отношение'
    )
    coefs = EmbeddedDocumentListField(
        Coef,
        verbose_name='Значения квартирных коэффициентов',
    )
    family = EmbeddedDocumentField(FamilyRelations, verbose_name='Семья')
    statuses = EmbeddedDocumentField(
        Statuses,
        default=Statuses(),
        verbose_name='Статусы жильца'
    )
    finance_legacy = ListField(
        ReferenceField('processing.models.billing.account.Account'),
        verbose_name="наследование фин. истории; "
                     "айди жителя, от которого наследуется"
    )
    cabinet_petition = EmbeddedDocumentField(
        Files,
        null=True
    )
    is_coop_member = BooleanField(
        required=False,
        default=False,
        verbose_name="Член ТСЖ/ЖСК"
    )
    coop_member_date_from = DateTimeField(
        verbose_name='Дата принятия в члены ТСЖ/ЖСК')
    rating = IntField(verbose_name="Рейтинг жителя")
    assessment = EmbeddedDocumentField(
        AssessmentEmbedded,
        verbose_name="Рейтинг жителя",
    )

    gis_uid = StringField(verbose_name='Единый лицевой счет')
    hcs_uid = StringField(verbose_name='Идентификатор ЖКУ')
    settings = EmbeddedDocumentField(AccountSettingsEmbedded)
    # поля человеческого существа
    sex = StringField(choices=GENDER_TYPE_CHOICES, verbose_name="Пол")
    photo = EmbeddedDocumentField(
        Files,
        verbose_name="Фотография работника (для карточки в системе)"
    )
    short_name = StringField()
    birth_date = DateTimeField(verbose_name="Дата рождения")
    first_name = StringField(verbose_name="Имя", null=True)
    last_name = StringField(verbose_name="Фамилия", null=True)
    patronymic_name = StringField(verbose_name="Отчество", null=True)

    # поля жителя-человека
    renting = EmbeddedDocumentField(
        RentingContract,
        verbose_name='Договор найма'
    )
    citizenship = StringField(verbose_name="Гражданство")
    is_privileged = BooleanField(
        required=True,
        default=False,
    )
    privileges = EmbeddedDocumentListField(
        PrivilegeBind,
        verbose_name='Список льгот, закрепленных за жителем'
    )
    privileges_info = EmbeddedDocumentField(PrivilegesInfo)
    last_name_upper = StringField()
    short_name_upper = StringField()
    nationality = StringField(
        choices=NATIONALITY_CHOICES,
        default=Nationality.RUSSIAN,
        verbose_name='Национальность'
    )
    military = EmbeddedDocumentField(
        Military,
        verbose_name='Воинская обязанность'
    )
    place_birth = StringField(
        null=True,
        verbose_name="Место рождения",
    )
    place_birth_fias = StringField(
        null=True,
        verbose_name="ФИАС места рождения",
    )
    place_origin = EmbeddedDocumentField(PlaceOrigin)

    # поля юр.лица - собственника помещения
    name = StringField(verbose_name='Наименование', null=True)
    legal_form = StringField(
        null=True,
        verbose_name='Правовая форма',
    )
    kpp = StringField(
        null=True,
        verbose_name='КПП',
    )
    ogrn = StringField(
        null=True,
        verbose_name='ОГРН',
    )
    director = EmbeddedDocumentField(
        EmbeddedPosition,
        verbose_name='Информация о директоре'
    )
    accountant = EmbeddedDocumentField(
        EmbeddedPosition,
        verbose_name='Информация о бухгалтере'
    )
    is_developer = BooleanField(
        null=True,
        verbose_name='Является застройщиком в текущем доме'
    )
    do_not_accrual = BooleanField(
        null=True,
        verbose_name='Начисления не проводятся'
    )
    entity = ObjectIdField(verbose_name='Ссылка на справочник организаций')
    entity_contract = ObjectIdField(verbose_name='Ссылка на договор управления')
    email_notify = BooleanField(verbose_name='Получать уведомления по почте?')
    email_slip = BooleanField(verbose_name='Получать квитанции по почте?')
    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к организации и группе домов (P,HG и D)'
    )
    grace_period = EmbeddedDocumentListField(
        ResponsibleTenantGracePeriod,
        verbose_name='Льготный период у ответственного жильца для пеней.',
    )
    telegram_chats = EmbeddedDocumentListField(TelegramChatId)
    archived_emails = ListField(StringField())
    p_settings = EmbeddedDocumentListField(RecurrentPaymentEmbedded)

    # поля-ошибки
    provider = DynamicField()
    is_responsible = BooleanField()
    tasks = DictField()
    offsets = DynamicField()
    update_offsets_sectors = DynamicField()
    update_saldo = DynamicField()
    update_sectors = DictField()
    update_offsets_at = DateTimeField()
    task = DictField()
    modified_at = DateTimeField()
    # TODO: удалить после релиза безбумажников 3
    disable_paper_bills = BooleanField(required=False, default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        householder = getattr(
            getattr(self, 'family', None), 'householder', None
        )
        self._is_family_householder = self.pk == householder
        self._area__id = getattr(getattr(self, 'area', None), 'id', None)

    def add_number(self, number: str or int):
        """Добавить другой (системы) номер ЛС"""
        if isinstance(number, int):
            number = str(number)

        if not isinstance(number, str):  # некорректный тип?
            pass  # не сохраняем номер
        elif not isinstance(self.old_numbers, list):
            self.old_numbers = [number]
        elif number not in self.old_numbers:
            self.old_numbers.append(number)

    def get_actor(self):
        from app.auth.models.actors import Actor
        return Actor.get_or_create_actor_from_account(self)

    AUTH_FIELDS = {
        'has_access',
        'password',
        'activation_code',
        'active',
        'activation_step',
        'activation_tries',
        'password_reset_code',
        'archived_emails',
    }

    def mirror_limited_access(self):
        from app.auth.models.actors import Actor
        actor_access = Actor.objects(
            owner__id=self.id,
        ).only(
            'owner.id',
            'limited_access',
            'username',
            'provider.id',
        ).as_pymongo().first()
        if not actor_access:
            return
        if self.settings.limited_access == actor_access.get('limited_access'):
            return
        actors_query = Actor.objects(
            id=actor_access['_id'],
        )
        actors_query.update(
            limited_access=self.settings.limited_access,
        )
        actors = list(actors_query.as_pymongo())
        houses = {a['owner']['house']['_id'] for a in actors}
        for house in houses:
            self._run_cabinet_denormalization_task(
                actor_access['provider']['_id'],
                house,
            )
        tenants = [
            a['owner']['_id'] for a in actors
            if a['owner']['_id'] != self.id
        ]
        if tenants:
            Tenant.objects(
                id__in=tenants,
            ).update(
                settings__limited_access=self.settings.limited_access,
            )

    @property
    def _id(self):
        return self.id

    @staticmethod
    def _run_cabinet_denormalization_task(provider_id, house_id):
        task = DenormalizationTask(
            model_name='RoboActor',
            field_name='permissions',
            obj_id=provider_id,
            func_name='denormalize_provider_permission_to_cabinets',
            kwargs={
                'house_id': house_id,
                'provider_id': provider_id,
            },
        )
        task.save()
        from app.caching.tasks.denormalization import \
            denormalize_provider_permission_to_cabinets
        denormalize_provider_permission_to_cabinets.delay(
            provider_id,
            house_id,
            task_id=task.id,
        )
        return task

    def mirroring_to_actors(self, updated_data=None):
        """
        Дублирует изменения полей Actor.AUTH_FIELDS.
        Временное решения совместимости двух бекендов.
        После полного перехода на auth v4 может быть безопасно удалено.
        """
        changed_data = {
            k: getattr(self, k)
            for k in getattr(self, '_changed_fields', [])
        }
        updated_data = updated_data or changed_data
        if not updated_data:
            return
        changed_values = {
            k: v for k, v in updated_data.items()
            if k in self.AUTH_FIELDS
        }
        if not changed_values:
            return
        from app.auth.models.actors import Actor
        if updated_data.get('has_access') is False:
            Actor.objects(owner__id=self.id).delete()
            return
        elif updated_data.get('has_access') is True:
            changed_values.pop('has_access', None)
        if 'email' in updated_data:
            Actor.objects(owner__id=self.id).delete()
        if changed_values and self.email:
            actor = Actor.get_or_create_actor_from_account(self)
            Actor.objects(username=actor.username).update(**changed_values)

    def activate_tenant_actor(self, email):
        """Восстанавление ЛКЖ сотрудником."""
        from app.auth.models.actors import Actor

        actor = Actor.get_or_create_actor_from_account(self)
        actor.activate_tenant_actor(email)

    @queryset_manager
    def objects(doc_cls, queryset):
        return queryset.filter(_type__in=['Tenant'])

    @property
    def is_anonymous(self):
        """Django compatibility"""
        return False

    @property
    def full_address(self):
        return f'{self.area.house.address}, {self.area.str_number_full}'

    @property
    def name_secured(self):
        if 'PrivateTenant' in self._type:
            return '{} {}'.format(
                self.first_name,
                self.patronymic_name,
            ).strip()
        elif 'LegalTenant' in self._type:
            return self.str_name
        return ''

    @property
    def is_family_householder(self):
        return self._is_family_householder

    @property
    def responsibility(self) -> QuerySet:
        """Ответственность жильца"""
        from processing.models.billing.responsibility import Responsibility

        return Responsibility.objects(account__id=self.id)

    _EXPORT_CHANGES_FIELDS = [
        'number',
        'area', 'family', 'statuses',
        'first_name', 'last_name', 'patronymic_name',
        'sex', 'birth_date',
        'snils', 'inn', 'email', 'phones',
        'citizenship', 'nationality',
        'name', 'kpp', 'ogrn',  # ЮЛ
    ]  # TODO пополнить список подлежащих выгрузке полей

    def check_statuses(self,
            is_accounting: bool = False, is_owning: bool = False,
            is_registered: bool = False, is_living: bool = False,
            is_responsible: bool = False) -> bool:
        """
        Проверка состояния (лицевого счета) жителя

        :param is_accounting: ведется учет (не закрыт)?
        :param is_owning: владелец помещения?
        :param is_registered: зарегистрирован?
        :param is_living: проживает?
        :param is_responsible: ответственный квартиросъемщик / плательщик?

        :returns: без аргументов функции = True
        """
        return isinstance(self.statuses, Statuses) and (
            (not is_accounting or self.statuses.is_accounting)
            and
            (not is_owning or self.statuses.is_owning)
            and
            (not is_registered or self.statuses.is_registered)
            and
            (not is_living or self.statuses.is_living)
            and
            (not is_responsible or self.responsibility.filter(__raw__={
                'date_from': {'$ne': None}, 'date_till': None,
            }).first() is not None)
        )

    @property
    def must_export_changes(self) -> bool:
        """
        Подлежит выгрузке в ГИС ЖКХ?

        ВНИМАНИЕ! Теряет актуальность после save.
        """
        return (
            not self.is_deleted
            and self._is_triggers(self._EXPORT_CHANGES_FIELDS)  # или _created
            # and self.check_statuses(is_accounting=True)  # не закрыт?
        )

    @classmethod
    def get_area_householder(cls, area_id: ObjectId) -> ObjectId or None:
        """Идентификатор собственника / главы семьи помещения"""
        return next(iter(tenant['_id'] for tenant in Tenant.objects(__raw__={
            'area._id': area_id,  # TODO aggregate family.householder = id
            'family': {'$exists': True}, 'family.householder': {'$ne': None},
            'is_deleted': {'$ne': True},
        }).only('id', 'family.householder').as_pymongo()
            if tenant['family']['householder'] == tenant['_id']), None)

    def set_householder(self, tenant_id: ObjectId = None):

        if tenant_id is None:
            assert self.id, "Данные жителя не (корректно) сохранены"
            tenant_id = self.id

        self.family.householder = tenant_id  # обновляем экземпляр

        assert self.area, "Отсутствуют данные помещения жителя"

        Tenant.objects(__raw__={  # включая себя
            'area._id': self.area.id,
            'family': {'$exists': True},
            'family.householder': {'$ne': tenant_id},
            'is_deleted': {'$ne': True},
        }).update(__raw__={'$set': {
            'family.householder': tenant_id,
        }})  # в обход save

    @classmethod
    def with_chat_id(cls, chat_id: int):
        """Возвращает всех жителей с привязанным chat_id."""
        return cls.objects(telegram_chats__chat_id=chat_id)

    @classmethod
    def recipients_channels(cls, tenant_ids=None, house_id=None):
        match = {'is_deleted': {'$ne': True}}
        if tenant_ids:
            match.update({'_id': {'$in': tenant_ids}})
        elif house_id:
            match.update({'area.house._id': house_id})

        telegram_condition = {
            '$cond': {
                'if': {
                    '$gt': [{'$size': {'$ifNull': ['$telegram_chats', []]}}, 0]
                },
                'then': True,
                'else': False,
            }
        }
        email_condition = {
            '$cond': {
                'if': {'$gt': [{'$strLenCP': {'$ifNull': ['$email', '']}}, 0]},
                'then': True,
                'else': False,
            }
        }
        disabled_path = '$notifications.paper_bills.disabled'
        disabled_condition = {'$ifNull': [disabled_path, False]}
        anyway_path = '$notifications.paper_bills.print_anyway'
        anyway_condition = {'$ifNull': [anyway_path, False]}

        pipeline = [
            {
                '$match': match,
            },

            {
                '$lookup': {
                    'from': 'Notifications',
                    'localField': '_id',
                    'foreignField': 'tenant_id',
                    'as': 'notifications',
                }
            },

            {
                '$unwind': {
                    'path': '$notifications',
                    'preserveNullAndEmptyArrays': True,
                }
            },

            {
                '$project': {
                    '_id': 1,
                    'telegram': telegram_condition,
                    'email': email_condition,
                    'disabled_paper': disabled_condition,
                    'print_anyway': anyway_condition,
                    'mobile_app': {'$literal': False},
                }
            },

            {
                '$group': {
                    '_id': '$_id',
                    'telegram': {'$first': '$telegram'},
                    'email': {'$first': '$email'},
                    'disabled_paper': {'$first': '$disabled_paper'},
                    'print_anyway': {'$first': '$print_anyway'},
                    'mobile_app': {'$first': '$mobile_app'},
                }
            },
        ]
        tenants = tuple(cls.objects.aggregate(*pipeline))

        from app.auth.models.actors import Actor

        actors_with_fcm = Actor.objects(
            owner__id__in=tuple(tenant['_id'] for tenant in tenants),
            cloud_messaging__fcm_token__exists=True,
        ).only(
            'owner.id',
            'cloud_messaging.fcm_token',
        ).as_pymongo()
        for fcm_actor in actors_with_fcm:
            for tenant in tenants:
                if fcm_actor['owner']['_id'] == tenant['_id']:
                    tenant['mobile_app'] = bool(fcm_actor['cloud_messaging'])
        return tenants

    @classmethod
    def unlink_chat_id(cls, chat_id: int):
        """Отвязывает chat_id от всех жителей и возвращает адреса."""
        tenants = cls.with_chat_id(chat_id)
        tenants.update(pull__telegram_chats__chat_id=chat_id)
        return [tenant.full_address for tenant in tenants]

    def check_phone_numbers(self, phone_number):
        """Записан ли телефонный номер на этого жителя."""
        str_numbers = [number.str_number for number in self.phones]
        return phone_number in str_numbers

    def add_telegram_chat_id(self, phone_number: str, chat_id: int):
        """Добавляет chat_id для конкретного инстанса."""
        if not self.check_phone_numbers(phone_number):
            return
        chat = TelegramChatId(chat_id=chat_id, phone_number=phone_number)
        self.update(add_to_set__telegram_chats=chat)
        self.save()

    def as_phone_talker(self, phone_number: str) -> dict:
        """Возвращает словарь для звонящего/отвечающего жителя на вызов."""
        try:
            address = " ".join((
                self.area.house.address,
                self.area.str_number_full,
            ))
        except (KeyError, AttributeError):
            address = None
        return TenantCallEmbedded(
            id=self.id,
            name=self.str_name,
            address=address,
            phone_number=phone_number,
        ).to_mongo()

    @classmethod
    def update_gis_data(cls, tenant_id: ObjectId,
            unified_number: str, service_id: str):
        """Обновить ЕЛС и ИЖКУ лицевого счета"""
        assert unified_number in service_id

        cls.objects(id=tenant_id).update_one(
            set__gis_uid=unified_number,  # ЕЛС
            set__hcs_uid=service_id,  # ИЖКУ
            upsert=False  # не создавать новые документы
        )

    _FOREIGN_DENORMALIZE_FIELDS = [
        '_type',
        'area',
        'is_developer',
        'do_not_accrual',
        'str_name'
    ]
    _ACTOR_DENORMALIZE_FIELDS = [
        'area',
        'str_name',
        'number',
        'email',
    ]

    def save(self, *args, **kwargs):
        self.validate_no_access_user()
        self.validate_fields()
        self.validate()
        self.restrict_changes()
        self.unchangeable_params(kwargs.get('ignore_email_validation', False))
        self.denormalize_creation()
        self.denormalize_by_statuses(*args, **kwargs)
        self.check_area_move()
        self.check_developer_sign()
        self.denormalize_name_by_type()
        self.denormalize_binds_and_number()
        self.denormalize_family_roles(kwargs.get('ignore_family', False))
        self.check_householder_sign_change()
        self.access_trigger()
        self.denormalize_roommate()
        if self._created or kwargs.get('ignore_denormalizing'):
            denormalize_fields = []
            actor_denormalize = []
        else:
            denormalize_fields = self._is_triggers(
                self._FOREIGN_DENORMALIZE_FIELDS,
            )
            actor_denormalize = \
                self._is_triggers(self._ACTOR_DENORMALIZE_FIELDS)
        self.check_contacts_for_doubles()
        if self._created:
            changed = {}
        else:
            changed = {k: getattr(self, k) for k in self._changed_fields}

        settings_access = self._is_triggers(['settings'])
        must_export_changes = self.must_export_changes  # до save!
        result = super().save(*args, **kwargs)
        if denormalize_fields:
            from app.caching.tasks.denormalization import \
                foreign_denormalize_data
            for field in denormalize_fields:
                foreign_denormalize_data.delay(
                    model_from=Tenant,
                    field_name=field,
                    object_id=self.pk,
                )
        if 'LegalTenant' in self._type:
            self.denormalize_legal_entity()
        if actor_denormalize:
            self.denormalize_actor_owner()
        self.mirroring_to_actors(changed)  # changed до save
        if settings_access:
            self.mirror_limited_access()

        if not kwargs.get('ignore_scheduling') and must_export_changes:
            from app.gis.models.gis_queued import GisQueued
            if not self.statuses.is_accounting:  # ЛС закрыт?
                GisQueued.put(self, weeks=4)  # откладываем выгрузку изменений
            else:
                GisQueued.put(self)

        return result

    def denormalize_actor_owner(self):
        from app.auth.models.actors import Actor
        actor = Actor.objects(owner__id=self.id).first()
        if not actor:
            return
        from app.house.models.house import House
        house = House.objects(pk=self.area.house.id).get()
        tenant_embedded = AccountEmbedded.from_tenant(
            tenant=self,
            business_types=Actor.get_house_business_types(house),
        )
        Actor.objects(
            pk=actor.pk,
        ).update(
            owner=tenant_embedded,
        )

    def check_contacts_for_doubles(self):
        if self.archived_emails and self.email in self.archived_emails:
            self.archived_emails.remove(self.email)
        actual_phones = [
            str(ph)
            for ph in self.phones
            if ph.not_actual is not True
        ]
        ix = 0
        while ix < len(self.phones):
            if (
                    self.phones[ix].not_actual
                    and str(self.phones[ix]) in actual_phones
            ):
                self.phones.pop(ix)
            else:
                ix += 1

    def delete(self, signal_kwargs=None, **write_concern):
        if not self.is_deleted:
            if self.is_family_householder:
                self._break_family_ties()
            self._check_finance_documents_existence()
            self._check_tickets_existence()
            self.is_deleted = True
            self.save()

            self.responsibility.delete()

    def unchangeable_params(self, ignore_email_validation=False):
        if ignore_email_validation:
            return
        if self._created or not self._is_key_dirty('email'):
            return
        if self.has_access:
            raise ValidationError("Cannot change login")
        from app.auth.models.actors import Actor
        actor = Actor.objects(
            owner__id=self.id,
            has_access=True
        ).only(
            'has_access',
        ).as_pymongo().first()
        if actor:
            raise ValidationError("Cannot change login")

    def validate_fields(self):
        email = self.email.lower()
        if email not in [None, '']:
            if not re.match(r'[\w.-]+@[\w.-]+\.?[\w]+?', email):
                raise ValidationError('Неверный формат email.')

    def validate_no_access_user(self):
        if not self.has_access:
            del self.p_settings
            try:
                self.validate_fields()
            except:
                self.email = ''

    @property
    def udo_provider(self):
        """
        Возвращает none или провайдера управляющей компании, привязанной к помещению
        """
        from app.house.models.house import House
        from processing.models.billing.provider.main import Provider
        house = House.objects(pk=self.area.house.id).first()
        udo_provider_pk = house.get_provider_by_business_type("udo")
        if udo_provider_pk:
            provider = Provider.objects.get(pk=udo_provider_pk)
            return provider

    def denormalize_legal_entity(self):
        self._create_or_update_legal_entity()

    def _create_or_update_legal_entity(self):
        if not self.inn and self.entity:
            self.entity = None
            self.entity_contract = None
            legal_entity = None
        else:
            from app.legal_entity.models.legal_entity_contract import \
                LegalEntityContract
            from app.legal_entity.models.legal_entity_provider_bind import \
                LegalEntityProviderBind
            legal_entity = self.try_create_legal_entity()
            if legal_entity.id != self.entity:
                provider = self.udo_provider
                contract = \
                    LegalEntityContract.get_or_create(legal_entity, provider)
                Tenant.objects(pk=self.id).update_one(__raw__={'$set': {
                    'entity': legal_entity.id,
                    'entity_contract': contract.id if contract else None,
                }})
                LegalEntityProviderBind.get_or_create(legal_entity, provider)
        return legal_entity

    def try_create_legal_entity(self):
        from app.legal_entity.models.legal_entity import LegalEntity
        return LegalEntity.get_or_create(self)

    def check_developer_sign(self):
        if self._is_key_dirty('is_developer') and self.is_developer:
            # Сделали застройщиком
            self._type = ['LegalTenant', 'Tenant']
            house = self._get_house()
            dev = house.get('developer')
            if not dev:
                raise ValidationError('К дому не привязан застройщик.')

            self.name = dev['name']
            self.legal_form = dev['legal_form']

    def denormalize_by_statuses(self, *args, **kwargs):
        if self._is_key_dirty('statuses'):
            self.perform_property_share(*args, **kwargs)
            self.perform_started_at(*args, **kwargs)

    def denormalize_binds_and_number(self):
        from app.house.models.house import House
        if not self.number:
            house = House.objects(id=self.area.house.id).first()
            region_code = ''
            if house:
                guid = house.fias_addrobjs
                fias = Fias.objects(
                    AOGUID__in=guid
                ).as_pymongo().first()
                if fias:
                    region_code = fias.get('REGIONCODE', '')
            if region_code is None:
                region_code = house.kladr[:2]
            self.number = generate_unique_account_number(region_code)
        if not self._binds:
            self._binds = HouseGroupBinds(hg=self._get_house_binds())

    def denormalize_roommate(self):
        if self._is_key_dirty('family.householder'):
            Tenant.objects(
                id__ne=self.id,
                area__id=self.area.id,
                family__householder=self.id
            ).update(
                family__householder=self.family.householder
            )

    def denormalize_name_by_type(self):
        if 'PrivateTenant' in self._type:
            self.last_name = self.last_name or ''
            self.str_name = ' '.join(
                filter(
                    None,
                    [
                        self.last_name,
                        self.first_name,
                        self.patronymic_name,
                    ],
                )
            )
            self.short_name = '{} {}.{}.'.format(
                self.last_name,
                (self.first_name or '')[0: 1],
                (self.patronymic_name or '')[0: 1],
            ).strip()
            self.last_name_upper = self.last_name.upper()
            self.short_name_upper = self.short_name.upper()
            if self._created:
                self.is_developer = False
        elif 'LegalTenant' in self._type:
            if self.legal_form is None:
                self.str_name = '«{}»'.format(self.name)
            else:
                self.str_name = '{} «{}»'.format(self.legal_form, self.name)
            self.short_name = self.str_name
        else:
            raise ValidationError(
                'Not specified _type (LegalTenant or PrivateTenant).'
            )

    def check_area_move(self):
        """Проверка на перемещение в другую квартиру и запуск денормализации"""
        if self._created or not self._is_key_dirty('area._id'):
            return

        self._area_denormalize()
        self._delete_old_relations()
        self._denormalize_documents()
        self._break_family_ties()

    def check_householder_sign_change(self):
        """
        Проверка на то, что главу семьи добавили в другую семью.
        В таком случае все семейство нужно прилепить туда.
        """
        cond = (
                self.is_family_householder
                and self.family.householder != self.id
                and not self._is_key_dirty('area._id')
        )
        if cond:
            family = self._get_family()
            if family:
                for tenant in family:
                    tenant.family.householder = self.family.householder
                    tenant.save()

    def denormalize_creation(self):
        """Денормализации, которые нужны только при создании документа"""
        if 'Tenant' not in self._type:
            self._type.append('Tenant')
        if self._created:
            self._area_denormalize()
            # Когда не указан собственник при создании,
            # собственником становится созданный житель
            if self.family and not self.family.householder:
                self.id = ObjectId()
                self.family.householder = self.id
                self._created = True

    def denormalize_family_roles(self, ignore_family=False):
        """
        При сохранении жителя проверять, изменилась ли связь с кем-то в семье,
        и менять у этого кого-то обратную связь.
        """
        denormalize_condition = (
                not ignore_family
                and self._is_triggers(['family.relations'])
                and self.family
                and self.family.relations
        )
        if denormalize_condition:
            changed_indexes = self._get_changed_family_indexes()
            roles = (
                (num, x.related_to, self._get_id_from_referenced_field(x.role))
                for num, x in enumerate(self.family.relations)
            )
            for num, related_to, role in roles:
                if changed_indexes is None or num in changed_indexes:
                    self._set_mate_family_role(role, related_to)

    def _check_finance_documents_existence(self):
        from processing.models.billing.accrual import Accrual
        from processing.models.billing.payment import Payment

        query = dict(account__id=self.id, is_deleted__ne=True)
        any_documents = bool(
            Accrual.objects(**query).only('id').as_pymongo().first()
            or Payment.objects(**query).only('id').as_pymongo().first()
        )
        if any_documents:
            raise ValidationError(
                'Нельзя удалить жителя, который имеет начисления или оплаты.'
            )

    def _check_tickets_existence(self):
        from app.tickets.models.tenants import Ticket

        query = dict(initial__author=self.id)
        any_documents = bool(
            Ticket.objects(**query).only('id').as_pymongo().first()
        )
        if any_documents:
            raise ValidationError(
                'Нельзя удалить жителя, который имеет зарегистрированное '
                'обращение'
            )

    def _break_family_ties(self):
        family = self._get_family()
        if family:
            for tenant in family:
                tenant.family.householder = tenant.id
                tenant.save()

    def _set_mate_family_role(self, role, related_to):
        """Установка обратной роли сожителю"""
        mate = Tenant.objects(pk=related_to).get()
        # Создадим роль, если
        role_create_condition = (
            # нет данных о семье
                not mate.family
                or not mate.family.relations
                # или нет данного жителя в ролях
                or self.id not in [x.related_to for x in mate.family.relations]
        )
        new_role_id = self._get_new_mate_role(role)
        if role_create_condition:
            new_role = FamilyRole(
                role=new_role_id,
                related_to=self.id
            )
            if not mate.family:
                mate.family = FamilyRelations(relations=[])
            mate.family.relations.append(new_role)
        # Человечек уже есть, просто изменим роль
        else:
            for relation in mate.family.relations:
                if relation.related_to == self.id:
                    relation.role = new_role_id
                    break
        # Передадим флаг, чтобы не возникло рекурсии по денормализации ролей
        mate.save(ignore_family=True)

    def _delete_old_relations(self):
        if self.family:
            # Удаление связей с проживающими
            related_accounts = []
            for relation in getattr(self.family, 'relations', []):
                if relation.related_to:
                    related_accounts.append(relation.related_to)

            for account in related_accounts:
                tenant = self.__class__.objects(id=account).first()
                if tenant and tenant.family and tenant.family.relations:
                    tenant.family.relations = [
                        x
                        for x in tenant.family.relations
                        if x.related_to != self.id
                    ]
                    tenant.save(ignore_family=True)

            # Удаление собственных связей
            delattr(self.family, 'relations')

    def _denormalize_documents(self):
        from processing.models.billing.accrual import Accrual
        from processing.models.billing.payment import Payment
        from app.offsets.models.offset import Offset

        updater = {
            # Квартира
            'account.area._id': self.area.id,
            'account.area.number': self.area.number,
            'account.area.order': self.area.order,
            'account.area.str_number': self.area.str_number,
            'account.area.str_number_full': self.area.str_number_full,
            'account.area._type': self.area._type,
            # Дом
            'account.area.house._id': self.area.house.id,
        }
        query = dict(account__id=self.id)
        Accrual.objects(**query).update(__raw__={'$set': updater})
        Payment.objects(**query).update(__raw__={'$set': updater})
        Offset.objects(
            __raw__={'refer.account._id': self.id}
        ).update(
            __raw__={'$set': {f'refer.{k}': v for k, v in updater.items()}}
        )

    def _get_new_mate_role(self, role):
        """Определение обратной роли для сожителя"""
        from processing.models.billing.family_role_catalogue import \
            FamilyRoleCatalogue

        reverse_roles = FamilyRoleCatalogue.objects(
            id=role).only('reverse_links').as_pymongo().get()['reverse_links']
        query = dict(id__in=reverse_roles)
        new_roles = FamilyRoleCatalogue.objects(**query).as_pymongo()
        mate_role = next(
            x for x in new_roles
            if (x['sex'] == self.sex if self.sex else True)
        )
        return mate_role['_id']

    def _get_changed_family_indexes(self):
        """Получение индексов измененных ролей из всего списка"""
        return None if self._created else {
                                              int(re.search(r'\d', x).group(0))
                                              for x in
                                              self._get_changed_fields()
                                              if 'family.relations.' in x
                                          } or None

    def _get_id_from_referenced_field(self, field):
        return field if isinstance(field, ObjectId) else field.id

    def _get_family(self):
        if not self._area__id:
            return []

        return self.__class__.objects(
            area__id=self._area__id,
            id__ne=self.id,
            family__householder=self.id
        )

    def perform_started_at(self, *args, **kwargs):
        if not self.statuses.ownership:
            return
        if not self.statuses.ownership.started_at:
            for elem in self.statuses.ownership.property_share_history:
                if elem.date == datetime.min.isoformat():
                    continue
                self.statuses.ownership.started_at = elem.date
                break

    def perform_property_share(self, *args, **kwargs):
        def get_attr(instance):
            return instance.date

        # Todo statuses проверяется на изменение поверхностно
        # Вложенные в него поля не проверяются на наличие изменений, поэтому не
        # считается суммарная площадь
        # if 'statuses' not in self._changed_fields:
        #     return
        if not self.statuses.ownership:
            return
        for elem in self.statuses.ownership.property_share_history:
            if elem.date is None:
                elem.date = datetime.min
        self.statuses.ownership.property_share_history = \
            sorted(self.statuses.ownership.property_share_history,
                   key=get_attr)
        history = self.statuses.ownership.property_share_history
        for elem in history:
            if elem.value[0] == 0 and elem.value[1] == 0:
                elem.value[1] = 1
        for counter, elem in enumerate(history):
            if elem['op'] == 'total':
                if counter:
                    p_before = sum([(-1 if x['op'] == 'red' else 1) *
                                    Fraction(*map(int, x['value']))
                                    for x in history[0: counter]
                                    if x['value']])
                    d = Fraction(*map(int, elem['value'])) - p_before
                    if d.numerator >= 0:
                        elem['op'] = 'inc'
                        elem['value'] = [d.numerator, d.denominator]
                    else:
                        elem['op'] = 'red'
                        elem['value'] = [-d.numerator, d.denominator]
                else:
                    elem['op'] = 'inc'
        if history.__len__() == 0:
            pass
            pass
            return
        total_share = sum(
            [(-1 if x.op == 'red' else 1) * Fraction(*map(int, x.value))
             for x in history if x.value])

        if total_share.numerator > total_share.denominator:
            raise ValidationError("Доля собственности не может быть больше "
                                  "100%. Измените значение долей собственности")
        if total_share.numerator < 0 or total_share.denominator < 0:
            raise ValidationError("Доля собственности не может быть меньше 0%."
                                  " Измените значение долей собственности")
        self.statuses.ownership.property_share = total_share.numerator, \
                                                 total_share.denominator
        if not self.statuses.ownership.is_owner and \
                self.statuses.ownership.property_share[0] > 0:
            self.statuses.ownership.is_owner = True

        if self.statuses.ownership.is_owner and \
                self.statuses.ownership.property_share[0] == 0:
            self.statuses.ownership.is_owner = False

    def _get_house_binds(self):
        return get_area_house_groups(self.area.id, self.area.house.id)

    @classmethod
    def process_house_binds(cls, house_id):
        areas = Area.objects(house__id=house_id).distinct('id')
        for area in areas:
            groups = get_area_house_groups(area, house_id)
            cls.objects(area__id=area).update(set___binds__hg=groups)

    def _area_denormalize(self):
        area = Area.objects(pk=self.area.id).get()
        self.area = DenormalizedAreaWithFias.from_ref(area)

    def update_contacts(self, phones=None, email=None, denormalize_to=None):
        """
        Обновляет список телефонов, добавляет недостающие. Можно передать,
        объекты, куда надо денормализовать телефоны из жителя
        """
        if phones is not None:
            self._update_phones(phones, denormalize_to=denormalize_to)
        if email is not None:
            from app.auth.models.actors import Actor
            actor = Actor.get_or_create_actor_from_account(self)
            if not actor.has_access and not self.has_access:
                self._update_email(email, denormalize_to=denormalize_to)
        self.save()
        if denormalize_to:
            for obj in denormalize_to:
                obj.save()

    def _update_email(self, email, denormalize_to=None):
        self.email = email
        if denormalize_to:
            for obj in denormalize_to:
                if not self.has_access:
                    obj.tenant.email = self.email

    def _update_phones(self, phones, denormalize_to=None):
        old = sorted(
            (x.phone_type or '', x.code or '', x.number or '', x.add or '')
            for x in self.phones
        )
        new = sorted(
            (
                ph.get('type') or ph.get('phone_type') or '',
                ph.get('code') or '',
                ph['number'] or '',
                ph.get('add') or '',
            )
            for ph in phones
        )
        if old != new:
            self.phones = [
                DenormalizedPhone(
                    phone_type=ph.get('type') or ph.get('phone_type'),
                    code=ph.get('code') or '',
                    number=ph['number'],
                    add=ph.get('add'),
                )
                for ph in phones
            ]
            if denormalize_to:
                for obj in denormalize_to:
                    obj.tenant.phones = self.phones

    def _get_house(self):
        from app.house.models.house import House

        return House.objects(
            id=self.area.house.id
        ).only('developer').as_pymongo().get()


class OtherTenant(Document, BindedModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Account',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
        ]
    }

    # Системные поля
    _type = ListField(StringField())
    is_deleted = BooleanField(null=True)

    # Общие поля Account
    email = StringField(
        null=True,
        verbose_name='Пользовательский эл. адрес',
    )
    phones = EmbeddedDocumentListField(
        DenormalizedPhone,
        verbose_name='Список телефонов'
    )
    str_name = StringField(
        null=True,
        verbose_name='Строка имени',
    )

    # Поля жителя или собственника помещения в доме
    area = EmbeddedDocumentField(
        DenormalizedAreaWithFias,
        verbose_name='Информация о помещении'
    )
    rating = IntField(verbose_name="Рейтинг жителя")
    assessment = EmbeddedDocumentField(
        AssessmentEmbedded,
        verbose_name="Рейтинг жителя",
    )

    # Поля человеческого существа
    short_name = StringField()
    first_name = StringField(verbose_name='Имя')
    last_name = StringField(null=True, verbose_name='Фамилия')
    patronymic_name = StringField(null=True, verbose_name='Отчество')

    # Поля юр.лица - собственника помещения
    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к организации и группе домов (P, HG и D)'
    )

    @queryset_manager
    def objects(doc_cls, queryset):
        return queryset.filter(_type__in=['OtherTenant'])

    @property
    def name_secured(self):
        if 'PrivateTenant' in self._type:
            return '{} {}'.format(
                self.first_name,
                self.patronymic_name,
            ).strip()
        elif 'LegalTenant' in self._type:
            return self.str_name
        return ''

    @classmethod
    def process_house_binds(cls, house_id):
        from app.area.models.area import Area

        areas = Area.objects(house__id=house_id).distinct('id')
        for area in areas:
            groups = get_area_house_groups(area, house_id)
            cls.objects(area__id=area).update(set___binds__hg=groups)

    def save(self, *args, **kwargs):
        self.denormalize_area()
        if self._created:
            self._type = ['OtherTenant', 'Tenant']
        self.str_name = ' '.join(filter(None, [
            self.last_name, self.first_name, self.patronymic_name
        ]))
        self.short_name = '{} {}.{}.'.format(
            self.last_name,
            (self.first_name or '')[0:1],
            (self.patronymic_name or '')[0:1]
        ).strip()
        if not self._binds:
            self._binds = HouseGroupBinds(hg=self._get_house_binds())
        return super().save(*args, **kwargs)

    def _get_house_binds(self):
        return get_area_house_groups(self.area.id, self.area.house.id)

    def denormalize_area(self):
        from app.area.models.area import Area
        area = Area.objects(pk=self.area.id).get()
        self.area = DenormalizedAreaWithFias.from_ref(area)


def generate_unique_account_number(kladr_code='78', max_attempts=None):
    if max_attempts is None:
        max_attempts = settings.get('ACCOUNT_NUMBER_ATTEMPTS', 20)
    for _ in range(max_attempts):
        number = _generate_number(kladr_code)
        if not Account.objects(number=number).as_pymongo().first():
            return number
    raise Exception(
        'Could not generate account number. Number of tries: {}'.format(
            max_attempts))


def _generate_number(kladr_code):
    account_number = kladr_code
    # Генерация 3 и 4 случайного разряда
    account_number += '{:02d}'.format(randint(0, 99))
    # Генерация 5 и 6 случайного разряда за исключением чисел 01 .. 12
    tmp_int = (randint(1, 87) + 13) % 100
    account_number += '{:02d}'.format(tmp_int)
    # Генерация разрядов 7 .. 13
    account_number += '{:07d}'.format(randint(0, 9999999))
    return account_number
