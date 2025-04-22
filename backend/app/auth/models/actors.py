# -*- coding: utf-8 -*-
import binascii
import datetime
import os
import sha3
import logging
from uuid import uuid4
from urllib.parse import urlparse, urlencode, urlunparse
from typing import Optional

from bson import ObjectId
from mongoengine import (
    Document,
    StringField,
    ObjectIdField,
    EmbeddedDocument,
    EmbeddedDocumentField,
    BooleanField,
    DateTimeField,
    IntField,
    EmbeddedDocumentListField,
    queryset_manager,
    ListField,
    DictField,
    Q)

from app.crm.models.crm import CRM, CRMStatus
from app.messages.core.email.extended_mail import AccessMail
from processing.models.permissions import Permissions, ClientTab
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from lib.helpfull_tools import get_mail_templates
from app.auth.models.sessions import SessionDataMixin
from processing.models.billing.crm.crm import CRMStatus
from processing.models.billing.provider.main import Provider
from processing.models.billing.base import BindsPermissions
from processing.models.billing.account import ACCRUAL_SECTOR_TYPE_CHOICES
from utils.crm_utils import provider_can_access, provider_can_tenant_access
from app.auth.models.embeddeds import (
    ChangedEmailEmbedded,
    ConnectedActorEmbedded,
    AccountEmbedded,
    SlaveEmbedded,
    CloudMessagingEmbedded,
)
from app.auth.models.mixins import (
    ActorsMixin,
)
from app.auth.models.sessions import Session
from app.house.models.house import (
    BusinessTypeEmbedded,
)
from processing.models.billing.provider.embeddeds import ActorProviderEmbedded
from app.permissions.mixins import PermissionsMixin, CABINET_PERMISSIONS


logger = logging.getLogger('c300')


class SessionEmbedded(SessionDataMixin, EmbeddedDocument):
    id = ObjectIdField(db_field='_id')


class Actor(ActorsMixin, PermissionsMixin, Document):
    """
    Модель пользователя
    """
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
    SALT_SIZE = 10
    # Некрасивая, но оптимальная конструкиця для получения шаблонов
    (
        BLOCK_TEMPLATE,  # Оповещение о блокировке регистрации
        RECOVERY_TEMPLATE,  # Восстановление пароля
        ACTIVATION_TEMPLATE,  # Начало активации аккаунта и подтверждение почты
        PASSWORD_TEMPLATE,  # Предоставление пароля для входа в область
        CONNECTED_TEMPLATE,  # Уведомление о присоединении адреса к кабинету
        DEACTIVATION_TEMPLATE,  # Приостановление доступа
        UNBLOCK_TEMPLATE,  # Разблокировка регистрации

    ) = get_mail_templates([
        'on_activation_blocking.html',
        'password_reset.html',
        'activate.html',
        'password.html',
        'account_connected.html',
        'on_deactivate.html',
        'on_unblocking.html'
    ])

    meta = {
        'db_alias': 'auth-db',
        'collection': 'actors',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'username',
            'owner.id',
            'sessions.uuid',
            ('provider.id', '_type', 'owner.owner_type'),
        ],
    }

    @queryset_manager
    def objects(doc_cls, queryset):
        return queryset.filter(_type='Actor')

    slugs = ListField()
    # идентификация пользователя
    owner = EmbeddedDocumentField(
        AccountEmbedded,
        required=True,
        verbose_name='Человек-владелец пользователя',
    )
    provider = EmbeddedDocumentField(
        ActorProviderEmbedded,
        required=True,
        verbose_name='Организация-владелец пользователя',
    )
    parent = ObjectIdField(
        required=False,
        verbose_name='Actor-организация, выдавшая доступ',
    )
    connected = EmbeddedDocumentListField(
        ConnectedActorEmbedded,
        verbose_name='Присоединённые аккаунты',
    )
    # настройки
    _type = StringField(reqired=True)
    created = DateTimeField(required=True, default=datetime.datetime.now)
    max_sessions = IntField(
        required=True,
        default=3,
        verbose_name='Максимально разрешённое количество сессий',
    )
    # права
    binds_permissions = EmbeddedDocumentField(
        BindsPermissions,
        verbose_name='Привязки к организации и группе домов (P,HG и D)',
    )
    is_super = BooleanField(default=False)
    limited_access = BooleanField(default=False)
    # параметры доступа
    username = StringField(required=True)
    password = StringField()
    password_dump = StringField(required=False, null=True)
    password_dump2 = StringField(required=False, null=True)
    has_access = BooleanField(
        required=True,
        default=False,
        verbose_name='Имеет доступ в систему',
    )
    get_access_date = DateTimeField(
        verbose_name='Дата получения доступа в систему',
    )
    activation_code = StringField(null=True)
    activation_step = IntField()
    activation_tries = IntField(
        default=0,
        verbose_name='Количество попыток активации',
    )
    password_reset_code = StringField()
    # активные сессии
    sessions = EmbeddedDocumentListField(
        SessionEmbedded,
        verbose_name='Список активных сессий',
    )
    visit_counter = IntField(
        default=0,
        verbose_name='Счетчик кол-ва логов жителем в лкж',
    )
    last_auth = DateTimeField(default=datetime.datetime.now)
    default = BooleanField(default=False)
    active = BooleanField(default=False)
    sectors = ListField(
        StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES),
    )
    new_email = EmbeddedDocumentField(
        ChangedEmailEmbedded,
    )
    archived_emails = ListField(StringField())
    cloud_messaging = EmbeddedDocumentListField(
        CloudMessagingEmbedded,
        required=False,
        verbose_name='Данные для отправки push-уведомлений через '
                     'Firebase Cloud Messaging и статистики',
    )

    def __init__(self, *args, **values):
        super().__init__(*args, **values)
        self.parent_actor = None

    def save(self, *args, **kwargs):
        self._type = self.__class__.__name__
        self._block_change_rights()
        self._access_trigger()

        if not kwargs.pop('ignore_mirroring', False):
            self.mirroring()
        super().save(*args, **kwargs)

    def _fill_parent(self):
        if not self.parent:
            robo_actor = RoboActor.objects(
                provider__id=self.provider.id,
            ).get()
            self.parent = robo_actor.id

    @property
    def parent_permissions(self):
        """Права организации пользователя."""
        if not self.provider:
            return {}
        provider = RoboActor.objects(provider__id=self.provider.id).first()
        if provider:
            return provider.permissions

    def deactivate_all_sessions(self):
        """Дективирует все сессии учётной записи."""
        sessions = [s.id for s in self.sessions]
        self.update(sessions=[])
        Session.objects(id__in=sessions).update(active=False)

    def activate_random_session_from_connected_account(
            self, connected_accounts: Optional[list]
    ):
        """Переключение на сессию другого аккаунта."""
        if connected_accounts:
            return self.switch_account(connected_accounts[0].id)

    def deactivate_tenant_actor(self):
        """Мягкое удаление ЛКЖ жителем.

        Task: https://redmine.eis24.me/issues/297045
        """
        if self.username == '' and not self.owner.owner_type != 'Tenant':
            raise ValueError
        connected_accounts = list(self._connected())
        if self.username not in self.archived_emails:
            self.archived_emails.append(self.username)
        self.has_access = False
        self.owner.email = None
        self.username = ''
        self.save()
        session = self.activate_random_session_from_connected_account(
            connected_accounts
        )
        return session

    def activate_tenant_actor(self, email):
        """Восстановление ЛКЖ сотрудником.

        Task: https://redmine.eis24.me/issues/297045
        """
        if self.username != '':
            raise ValueError('Невозможно восстановить email при записанном '
                             'email')
        if self.owner.owner_type != 'Tenant':
            raise ValueError('Вызов возможен только для жителей.')
        if email not in self.archived_emails:
            raise ValueError('Переданный email не находится в архиве.')
        self.archived_emails.remove(email)
        self.has_access = True
        self.owner.email = email
        self.username = email.lower().strip()
        self.save()

    def _set_new_email(self, new_email: str):
        """Добавление данных о потенциальном новом email."""
        self.update(
            new_email=ChangedEmailEmbedded(
                new_email=new_email,
                code=str(uuid4()),
            )
        )

    def start_change_email(self, new_email: str):
        """Начало процесса смены email."""
        self._set_new_email(new_email=new_email)
        self.send_code_change_email()

    def _change_email(self, new_email=None):
        """Смена старой почты на новую."""
        from processing.models.billing.account import Tenant
        if self.username not in self.archived_emails:
            self.archived_emails.append(self.username)
        new_email_field = getattr(self, 'new_email')
        if not new_email and not new_email_field:
            raise ValueError('Не указан новый email.')
        new_email = new_email or new_email_field.new_email
        tenant = Tenant.objects(id=self.owner.id).first()
        if tenant:
            tenant.update(email=new_email)
        self.owner.email = new_email
        self.username = new_email.lower().strip()
        self.new_email = None

    def update_email(self):
        """Подтверждение смены электронной почты."""
        return self._change_email()

    def __mirroring_to_actors(self, changed_values):
        """
        Дублирует значения связанные с auth в родственные акторы.
        Если username равен '', то значит этот актор удалён жителем и
        дублировать данные из него никуда не нужно.
        """
        if self.username == '':
            return
        self.__class__.objects(username=self.username).update(**changed_values)

    def __mirroring_to_tenants(self, changed_values):
        """
        Дублирует значения связанные с auth в родственных жителей.
        Если username равен '', то значит этот актор удалён жителем и
        дублировать данные нужно только в один конкретный Tenant.
        """
        from processing.models.billing.account import Tenant
        tenants = Tenant.objects(_type__in=['Tenant'])
        if self.username == '':
            tenants = tenants.filter(id=self.owner.id)
            changed_values['email'] = None
        else:
            tenants = tenants.filter(email=self.username)
        tenants.update(**changed_values)

    def __mirroring_to_workers(self, changed_values):
        """Дублирует значения связанные с auth в родственных сотрудников."""
        from app.personnel.models.personnel import Worker
        Worker.objects(
            _type__in=['Worker'],
            id=self.owner.id,
        ).update(**changed_values)

    def mirroring(self):
        if not getattr(self, '_changed_fields', None):
            return
        changed_fields = self.AUTH_FIELDS.intersection({*self._changed_fields})
        changed_values = {k: v for k, v in self.to_mongo().items()
                          if k in changed_fields}
        if changed_values:
            self.__mirroring_to_actors(changed_values)
            self.__mirroring_to_tenants(changed_values)
            self.__mirroring_to_workers(changed_values)

    @property
    def is_superuser(self):
        """Для совместимости AnonymousUser"""
        return self.is_super

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
        return (
            self.has_access
            and self.activation_code is None
            and self.activation_step is None
            and getattr(self.provider, 'client_access', False)
        )

    @property
    def can_reset_password(self):
        return getattr(self.provider, 'client_access', False)

    @classmethod
    def get_actor_id_by_session(cls, session_id):
        actor = cls.objects(sessions__id=session_id).first()
        if not actor or not actor.owner:
            raise KeyError('Actor not found by session.')
        return actor.owner.id

    @classmethod
    def compare_password_with_hash(cls, password, password_hash_with_salt):
        """
        Функция для сравнения хеш + соль с паролем.
        Тип password_hash_with_salt должен быть bytes.
        Возвращает True если пароли равны или False если пароли не равны
        """
        salt = password_hash_with_salt[-cls.SALT_SIZE * 2:]
        ph = cls.password_hash(password, binascii.a2b_hex(salt))

        if ph != password_hash_with_salt:
            return False

        return True

    @property
    def has_access_crm(self):
        if self._type == "RoboActor" or self.is_super:
            return True
        crm_obj = CRM.objects(owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
                              provider__id=self.provider.id).first()
        if crm_obj:
            accesses = {
                'Tenant': [CRMStatus.CLIENT, CRMStatus.DEBTOR],
                'Worker': [CRMStatus.CLIENT]
            }
            return crm_obj.status in accesses[self.owner.owner_type]
        return False

    @classmethod
    def password_hash(cls, password, salt_for_password=None):
        """
        Функция для создания хеша от пароля с добавлением соли.
        Тип salt_for_password должен быть bytes.
        На выходе получается хеш + соль. Размер соли на выходе SALT_SIZE * 2
        """
        password_hash = sha3.keccak_256()

        if salt_for_password is None:
            salt = os.urandom(cls.SALT_SIZE)
        else:
            if not isinstance(salt_for_password, bytes):
                raise Exception('Type of salt_for_password must be bytes')
            salt = salt_for_password

        password_hash.update(password.encode() + salt)
        return password_hash.hexdigest() + binascii.hexlify(salt).decode()

    @staticmethod
    def generate_new_password():
        return uuid4().hex[:8]

    def get_existing_user(self):
        exist_actor = Actor.objects(
            username=self.username,
            id__ne=self.id,
            has_access=True,
            provider__client_access=True,
        ).first()
        return exist_actor

    def _connected(self):
        """Временное решение для переключения аккаунтов."""
        return self.__class__.objects(username=self.username)

    def get_active_connected(self):
        actors = Actor.objects(
            Q(
                owner__owner_type='Tenant',
                username=self.username,
                has_access=True,
                provider__client_access=True,
            )
            | Q(
                owner__owner_type='Worker',
                owner__email=self.owner.email,
                has_access=True,
                provider__client_access=True,
            ),
        ).filter(
            id__ne=self.id,
        ).only(
            'owner.id',
            'owner.area',
            'owner.house',
            'provider',
        )
        return [
            {
                '_id': actor.id,
                'owner': actor.owner.to_mongo(),
                'provider': actor.provider.to_mongo(),
            }
            for actor in actors
        ]

    def validate_access_data(self):
        self.provider.client_access = provider_can_access(self.provider.id)
        for connected_user in self.connected:
            connected_user.provider.client_access = \
                provider_can_access(self.provider.id)
        self.save()

    def create_new_session(self, remote_ip, screen_sizes, uuid=None):
        if not uuid:
            uuid = Session.generate_uuid()
        session_params = {
            'uuid': uuid,
            'remote_ip': remote_ip,
            'screen_sizes': screen_sizes,
        }
        session = Session(
            owner=self.pk,
            **session_params,
        )
        session.save()
        if len(self.sessions) >= self.max_sessions:
            extra = len(self.sessions) - self.max_sessions + 1
            for s in self.sessions[0: extra]:
                Actor.objects(pk=self.pk).update(
                    pull__sessions__id=s.id,
                )
                Session.objects(pk=s.id).update(active=False)
            self.sessions = self.sessions[extra:]
        session_params['id'] = session.pk
        session_params['created'] = session.created
        session = SessionEmbedded(**session_params)
        Actor.objects(pk=self.pk).update(
            push__sessions=session,
        )
        self.sessions.append(session)
        return session.id, uuid

    def set_slave_for_session(self, session_id, slave_id):
        for session in self.sessions:
            if session.id == session_id:
                session_ins = Session.objects(
                    pk=session_id,
                ).get()
                session_ins.slave = SlaveEmbedded(
                    id=slave_id,
                    _type=self._get_slave_type(slave_id)
                )
                session_ins.save()
                session.slave = session_ins.slave
                self.save()
                return True
        return False

    def destroy_session(self, session_id):
        """Уничтожает переданную сессию (эквивалентно логауту)"""
        for num, session in enumerate(self.sessions):
            if session.id == session_id:
                self.sessions.pop(num)
                self.save()
                return

        raise KeyError('Session not found in Actor.')

    def switch_account(self, account_id, session: SessionEmbedded = None):
        """Переключение аккаунта"""
        user = next(
            iter(
                user
                for user in self._connected()
                if str(user.id) == str(account_id)
            ),
            None,
        )
        if not user:
            raise KeyError('Connected Actor not found in Actor.')
        new_actor = Actor.objects(id=account_id).first()
        if self.owner.owner_type != new_actor.owner.owner_type:
            raise ValueError('Disallow switching to actor of another type.')
        if new_actor and new_actor.has_access:
            session, _ = new_actor.create_new_session(
                remote_ip=getattr(session, 'remote_ip', ''),
                screen_sizes=getattr(session, 'screen_sizes', [])
            )
            return session

    def check_can_login(self):
        return all((
            self.can_login,
            self.password
        ))

    def reset_password(self, code):
        """Восстановление пароля"""
        if not self.can_reset_password:
            raise PermissionError('Нет доступа у организации')

        if code != self.password_reset_code:
            raise PermissionError('Неверный код')

        password = self.generate_new_password()
        self.password = self.password_hash(password)
        self.password_reset_code = None
        self.save()
        self.send_password_mail(password)

    def set_new_password(self, new_password: Optional[str] = None):
        """Установка нового пароля."""
        logger.debug('set_new_password starts')
        if not new_password:
            new_password = self.generate_new_password()
        self.password = self.password_hash(new_password)
        if self.owner.owner_type == 'Tenant':
            self.permissions = self.get_cabinet_permission(self)
        self.save()
        self.send_password_mail(new_password)

    def set_new_password_for_connected_accounts(self, new_password):
        for account in self._connected():
            account.password = account.password_hash(new_password)
            account.save()

    def send_code_change_email(self):
        """Отправка кода подтверждения смены email жителя."""
        if not self.owner.owner_type == 'Tenant':
            return
        url_parts = list(
            urlparse(
                '/'.join(
                    (self._get_base_url(),
                     'api',
                     'v4',
                     'cabinet',
                     'confirm_new_email',
                     )
                )
            )
        )
        params = {'account': str(self.id), 'code': self.new_email.code}
        url_parts[-2] = urlencode(params)
        url = urlunparse(url_parts)

        variables = {
            'provider_name': self.provider.str_name,
            'provider_url': self._get_base_url(),
            'actor_type': self.owner.owner_type,
            'url': url,
            'tenant_address': self.owner.house.address,
            'current_email': self.owner.email,
            'new_email': self.new_email.new_email,
        }
        mail = AccessMail(
            provider_id=self.provider.id,
            addresses=self.new_email.new_email,
            subject='Подтверждение смены e-mail',
            body=self.TENANT_CHANGE_EMAIL_TEMPLATE.render(variables),
        )
        mail.send()

    def send_activation_mail(self, change_email=False):
        """
        Отправка письма со ссылкой на активацию и подтверждение квартиры
        """
        logger.debug('send_activation_mail starts')
        is_tenant = self.owner.owner_type == 'Tenant'
        url = self._make_url_for_tenant() if is_tenant else self._make_url_for_account()

        variables = {
            'title': 'Подтверждение эл. адреса почты',
            'provider_name': self.provider.str_name,
            'provider_url': self._get_base_url(),
            'actor_type': self.owner.owner_type,
            'url': url,
            'account': self,
            'tenant_address': self.owner.house.address if is_tenant else None
        }
        email = self.new_email.new_email if self.new_email else self.owner.email
        mail = AccessMail(
            provider_id=self.provider.id,
            addresses=email,
            subject='Подтверждение e-mail',
            body=self.ACTIVATION_TEMPLATE.render(variables)
        )
        mail.send()

    def _make_url_for_tenant(self) -> str:
        """Возвращает URL для жителя"""
        base_url = self._get_base_url()
        params = urlencode({'account': str(self.id), 'code': self.activation_code})
        url_string = f'{base_url}/api/v4/registration/first_step_activation/?{params}'
        return url_string

    def _make_url_for_account(self) -> str:
        """Возвращает URL для аккаунта (не жителя)"""
        base_url = self._get_base_url()
        url_string = f'{base_url}/api/v4/a/activate/{self.owner.id}/{self.activation_code}/'
        return url_string

    def send_password_mail(self, password):
        """
        Отправка письма со сгенерированным паролем для входа
        после регистрации
        """
        logger.debug('send_password_mail starts')
        variables = {
            'provider_name': self.provider.str_name,
            'provider_url': self._get_base_url(),
            'actor_type': self.owner.owner_type,
            'actor_password': password,
            'actor_username': self.username,
            'url': self._get_base_url(),
            'account': self,
        }
        if variables['actor_type'] == 'Tenant':
            variables['tenant_address'] = self.owner.house.address

        mail = AccessMail(
            provider_id=self.provider.id,
            addresses=self.owner.email,
            subject='Новый пароль',
            body=self.PASSWORD_TEMPLATE.render(variables)
        )
        mail.send()

    def send_account_connected_mail(self):
        """
        Отправка письма со сгенерированным паролем для входа
        после регистрации
        """
        logger.debug('send_account_connected_mail starts')
        mail = AccessMail(
            provider_id=self.provider.id,
            addresses=self.owner.email,
            subject='Новый пароль',
            body=self.CONNECTED_TEMPLATE.render(
                dict(
                    account=self,
                    base_url=self._get_base_url(),
                    title='Личный кабинет добавлен'
                )
            )
        )
        mail.send()

    def send_password_reset_mail(self):
        """Отправка письма с паролем восстановления"""
        logger.debug('send_password_reset_mail starts')
        if not self.can_reset_password:
            raise PermissionError('Нет доступа!')
        actor_password = self.generate_new_password()
        self.password_reset_code = actor_password
        self.save()
        url_parts = list(
            urlparse(
                '/'.join(
                    (self._get_base_url(),
                     'api',
                     'v4',
                     'registration',
                     'apply_password',
                     )
                )
            )
        )
        params = {'account': str(self.id), 'code': self.password_reset_code}
        url_parts[-2] = urlencode(params)
        url = urlunparse(url_parts)
        variables = {
            'provider_name': self.provider.str_name,
            'provider_url': self._get_base_url(),
            'actor_type': self.owner.owner_type,
            'url': url,
            'actor_password': actor_password,
        }
        if variables['actor_type'] == 'Tenant':
            variables['tenant_address'] = self.owner.house.address
        mail = AccessMail(
            provider_id=self.provider.id,
            addresses=self.owner.email,
            subject='Восстановление пароля',
            body=self.RECOVERY_TEMPLATE.render(variables),
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

            variables = {
                'provider_name': self.provider.str_name,
                'provider_url': self._get_base_url(),
                'actor_type': self.owner.owner_type,
            }
            if variables['actor_type'] == 'Tenant':
                variables['tenant_address'] = self.owner.house.address

            if self.owner.email:
                mail = AccessMail(
                    provider_id=self.provider.id,
                    addresses=self.owner.email,
                    subject='Активация ЛК заблокирована',
                    body=self.BLOCK_TEMPLATE.render(variables),
                )
                mail.send()

        raise PermissionError(
            'Превышено количество попыток активации. '
            'Лицевой счёт заблокирован, обратитесь в вашу '
            'управляющую организацию для разблокировки'
        )

    def send_deactivation_mail(self):
        """Отправка письма, уведомляющая о приостановлении доступа в кабинет"""
        logger.debug('send_deactivation_mail starts')
        variables = {
            'title': 'Приостановление доступа в систему',
            'provider_name': self.provider.str_name,
            'provider_url': self._get_base_url(),
            'actor_type': self.owner.owner_type,
            'account': self,
            'account_number': self.owner.number,
            'worker': False if self.owner.owner_type != 'Worker' else True,
        }
        if variables['actor_type'] == 'Tenant':
            variables['tenant_address'] = self.owner.house.address

        if self.owner.email:
            mail = AccessMail(
                provider_id=self.provider.id,
                addresses=self.owner.email,
                subject='Приостановление доступа в систему',
                body=self.DEACTIVATION_TEMPLATE.render(variables),
            )
            mail.send()

    def send_registration_unlock_mail(self):
        """Отправка письма о разблокировке регистрации"""
        if self.owner.email:
            mail = AccessMail(
                provider_id=self.provider.id,
                addresses=self.owner.email,
                subject='Регистрация ЛК разблокирована',
                body=self.UNBLOCK_TEMPLATE.render(
                    dict(
                        account=self,
                        title='Регистрация ЛК разблокирована',
                    ),
                ),
            )
            mail.send()

    def send_confirm_mail(self):
        mail = AccessMail(
            provider_id=self.provider.id,
            addresses=self.owner.email,
            subject='Регистрация ЛК разблокирована',
            body=f'{self._get_base_url()}' + '/api/v4/worker/confirm_mail/'
                                             f'?code={self.activation_code}&id={self.owner.id}',
        )
        mail.send()

    def _get_slave_type(self, slave_id):
        query = dict(__raw__=dict(_id=slave_id))
        slave = Actor.objects(**query).only('_type').as_pymongo().get()
        return slave['_type']

    @classmethod
    def get_or_create_actor_by_worker(cls, worker, has_access=None):
        actor = cls.objects(owner__id=worker.pk).first()
        if actor:
            return actor
        return cls.create_actor_by_worker(worker, has_access=has_access)

    @classmethod
    def create_actor_by_worker(cls, worker, has_access=None):
        from processing.models.billing.provider.main import Provider
        provider = Provider.objects(pk=worker.provider.id).get()
        parent_actor = RoboActor.get_default_robot(provider.pk)
        actor = Actor(
            owner=AccountEmbedded.from_worker(worker),
            provider=ActorProviderEmbedded(
                id=provider.pk,
                str_name=provider.str_name,
                inn=provider.inn,
                client_access=provider_can_access(provider.pk),
            ),
            parent=parent_actor.id,
            connected=[],
            is_super=False,
            binds_permissions=BindsPermissions(
                pr=provider.pk,
                ac=worker.pk,
                hg=None,
            ),
            username=worker.number,
            password=None,
            has_access=False,
            get_access_date=None,
            sessions=[],
        )
        actor.copy_access(worker, has_access)
        actor.save()
        return actor

    def copy_access(self, worker, has_access=None):
        from app.auth.models.embeddeds import SlugEmbedded
        from app.permissions.migrations.slug_permission import (
            transform_permissions,
        )
        perms = Permissions.objects(actor_id=worker.id).first()
        tabs = ClientTab.get_tabs_list()
        slugs = []
        if perms:
            for tab in tabs:
                if 'Tab' not in perms.granular:
                    continue
                if str(tab['_id']) in perms.granular.get('Tab'):
                    perm = perms.granular.get('Tab').get(str(tab['_id']))
                    if perm:
                        slugs.append(
                            SlugEmbedded(
                                slug=tab['slug'],
                                c=perm[0]['permissions'].get('c'),
                                r=perm[0]['permissions'].get('r'),
                                u=perm[0]['permissions'].get('u'),
                                d=perm[0]['permissions'].get('d'),
                            ),
                        )
        tabs_dict = {str(tab['_id']): tab['slug'] for tab in tabs}
        perms = transform_permissions(perms, tabs_dict)
        self.slugs = slugs or []
        self.permissions = perms
        if has_access is None:
            has_access = worker.has_access and not worker.activation_code
        if has_access:
            self.password = worker.password
            self.get_access_date = worker.get_access_date
        self.has_access = has_access
        self.activation_code = worker.activation_code
        self.binds_permissions.hg = worker._binds_permissions.hg

    @staticmethod
    def get_house_business_types(house):
        house_btypes = list()
        if house.service_binds:
            house_btypes = [
                BusinessTypeEmbedded(**{
                    'id': x.business_type, 'provider': x.provider})
                for x in house.service_binds]
        return house_btypes

    @classmethod
    def _create_actor_from_tenant(cls, tenant):
        from app.house.models.house import House
        from processing.models.billing.provider.main import Provider
        from processing.models.billing.account import Tenant

        if isinstance(tenant, ObjectId):
            tenant = Tenant.objects(pk=tenant).get()

        house = House.objects(pk=tenant.area.house.id).get()
        provider_id = house.get_default_provider_by_sectors()
        sectors = house.get_sectors()
        provider = Provider.objects(pk=provider_id).get()
        parent_actor = RoboActor.get_default_robot(provider_id)
        settings = getattr(tenant, 'settings', None)
        limited_access = getattr(settings, 'limited_access', False)
        actor = Actor(
            owner=AccountEmbedded.from_tenant(
                tenant,
                business_types=cls.get_house_business_types(house),
            ),
            provider=ActorProviderEmbedded(
                id=provider.pk,
                str_name=provider.str_name,
                inn=provider.inn,
                client_access=provider_can_tenant_access(provider.pk),
            ),
            parent=parent_actor.id,
            connected=[],
            username=tenant.email,
            password=tenant.password,
            has_access=False,
            get_access_date=tenant.get_access_date,
            sessions=[],
            sectors=sectors,
            limited_access=limited_access,
        )
        fields = (
            'activation_code',
            'activation_step',
            'activation_tries',
            'password_reset_code',
        )
        for field in fields:
            value = getattr(tenant, field, None)
            if value:
                setattr(actor, field, value)
        actor.permissions = cls.get_cabinet_permission(actor)
        actor.save()
        return actor

    @staticmethod
    def get_cabinet_permission(actor):
        perms = RoboActor.get_cabinet_permissions(
            actor.provider.id,
            actor.owner.house.id,
        )
        if actor.limited_access:
            RoboActor.cut_cabinet_permissions_for_limited_access(perms)
        return perms

    @classmethod
    def get_or_create_actor_from_account(cls, account):
        """Возвращает актора по профилю.
        Если актор не найден, то он создаётся.
        """
        actor = cls.objects(owner__id=account.id).first()
        if actor:
            return actor
        if 'Worker' in account._type:
            return cls.create_actor_by_worker(account)
        if 'Tenant' in account._type:
            if 'OtherTenant' in account._type:
                return None
            return cls._create_actor_from_tenant(account)

    def _block_change_rights(self):
        """Запрет апгрейда прав актера через модель"""
        if not self._created:
            if self.is_super and 'is_super' in self._changed_fields:
                self.is_super = False

    def _access_trigger(self):
        """Рассылка сообщений при смене прав доступа в систему"""
        logger.debug('_access_trigger starts')
        if not self._created and 'has_access' in self._changed_fields:
            if self.has_access:
                self.get_access_date = datetime.datetime.now()
                if not self.owner.email:
                    return
                if self.owner.owner_type == 'Tenant':
                    self.permissions = self.get_cabinet_permission(self)
                actor_exist = self.get_existing_user()
                if actor_exist:
                    self.password = actor_exist.password
                    self.send_account_connected_mail()
                elif not actor_exist and 'activation_code' not in self._changed_fields:
                    self.has_access = False
                    self.activation_code = uuid4().hex
                    self.send_confirm_mail()
                elif not actor_exist and 'activation_code' in self._changed_fields:
                    logger.debug("IF BRANCH: "
                                 "not actor_exist and 'activation_code' in self._changed_fields ")
                    logger.debug("'activation_code' in self._changed_fields: %s",
                                 'activation_code' in self._changed_fields)
                    # На этом месте отрабатывает access_trigger из аккаунта
                    # и отправляет письмо с активацией

                    # password = self.generate_new_password()
                    # self.password = self.password_hash(password)
                    # self.send_password_mail(password)

            else:
                if hasattr(self.owner, 'email'):
                    self.send_deactivation_mail()

    def _get_base_url(self):
        """Получение базовой URL"""
        provider = Provider.objects(id=self.provider.id).get()
        if self.owner.owner_type == 'Tenant':
            return provider.get_cabinet_url()
        else:
            return provider.get_url()

    @staticmethod
    def add_cloud_messaging(users, cloud_messaging: dict):
        """
        Добавляет пользователям данные для FCM
        """
        # Временная переменная для _id, по которым копируется в тестовую базу
        updated_ids = []
        for user in users:
            if (
                    user.provider.client_access
                    and user.has_access
                    and user.password
            ):
                updated = user.update(
                    add_to_set__cloud_messaging=cloud_messaging)
                if updated:
                    updated_ids.append(user.owner.id)
        return updated_ids

    @classmethod
    def remove_invalid_cloud_messaging(cls, cloud_messaging: dict):
        if not cloud_messaging.get('fcm_token'):
            return
        connected_actors = cls.objects(
            cloud_messaging__fcm_token=cloud_messaging['fcm_token'],
        )
        for actor in connected_actors:
            actor.cloud_messaging.remove(cloud_messaging)
            actor.save()


_ONLY_READ_PERMISSION = 2


class RoboActor(Document, ActorsMixin, PermissionsMixin):
    """
    Модель пользователя-робота
    """
    meta = {
        'db_alias': 'auth-db',
        'collection': 'actors',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'provider.id',
        ],
    }

    @queryset_manager
    def objects(doc_cls, queryset):
        return queryset.filter(_type='RoboActor')

    slugs = ListField()
    _type = StringField(reqired=True)
    provider = EmbeddedDocumentField(
        ActorProviderEmbedded,
        required=True,
        verbose_name='Организация-владелец',
    )
    # настройки
    created = DateTimeField(required=True, default=datetime.datetime.now)
    default = BooleanField(default=False)
    # права
    binds_permissions = EmbeddedDocumentField(
        BindsPermissions,
        verbose_name='Привязки к организации и группе домов (P,HG и D)',
    )
    # параметры доступа
    active = BooleanField(
        required=True,
        default=False,
        verbose_name='Действующий',
    )
    # активные сессии
    sessions = EmbeddedDocumentListField(
        SessionEmbedded,
        verbose_name='Список активных сессий',
    )
    has_access = BooleanField(default=True)
    activation_code = StringField(default=None)
    activation_step = StringField(default=None)
    activation_tries = IntField(default=None)
    password_reset_code = StringField(default=None)
    password = StringField(default=None)

    def __init__(self, *args, **values):
        super().__init__(*args, **values)
        self.parent_actor = self

    def save(self, *args, **kwargs):
        self._type = self.__class__.__name__
        super().save(args, kwargs)

    @property
    def parent_permissions(self):
        """Права организации пользователя."""
        if not self.provider:
            return {}
        provider = Provider.objects(id=self.provider.id).first()
        permissions = {}
        if provider and provider.business_types:
            permissions = provider.business_types[0].permissions
            for business_type in provider.business_types[1:]:
                for slug, perm in business_type.permissions.items():
                    permissions[slug] = max(perm, permissions.get(slug, 0))
        return permissions

    @classmethod
    def get_default_robot(cls, provider_id):
        robots = list(
            cls.objects(
                provider__id=provider_id,
                _type=cls.__name__,
            ).order_by('default')[0: 1],
        )
        if robots:
            return robots[0]
        return cls.create_actor_by_provider(provider_id)

    @classmethod
    def create_actor_by_provider(cls, provider_id):
        from processing.models.billing.provider.main import Provider
        provider = Provider.objects(pk=provider_id).get()
        actor = cls(
            provider=ActorProviderEmbedded(
                id=provider.pk,
                str_name=provider.str_name,
                inn=provider.inn,
                client_access=provider_can_access(provider.pk),
            ),
            default=True,
            slugs=[],
            binds_permissions=BindsPermissions(
                pr=provider.pk,
                hg=None,
            ),
            active=True,
            sessions=[],
        )
        actor.save()
        return actor

    @staticmethod
    def cut_cabinet_permissions_for_limited_access(perms):
        perms.pop('request_log', None)
        perms.pop('tickets_from_tenants', None)

    @classmethod
    def get_cabinet_permissions(cls, provider_id, house_id):
        provider_actor = cls.get_default_robot(provider_id)
        perms = {
            slug: (
                    provider_actor.permissions.get(slug, 0)
                    & _ONLY_READ_PERMISSION
            )
            for slug in CABINET_PERMISSIONS
        }
        cls._cut_catalogue_restrictions(perms, provider_id, house_id)
        return perms

    @staticmethod
    def _cut_catalogue_restrictions(permissions, provider_id, house_id):
        if not (permissions['request_log'] & _ONLY_READ_PERMISSION):
            permissions.pop('catalogue_cabinet_positions')
            return
        from app.catalogue.models.catalogue import CatalogueHouseBind
        catalog_allow = CatalogueHouseBind.objects(
            house=house_id,
            provider=provider_id,
        ).as_pymongo().first()
        if not catalog_allow or not catalog_allow.get('catalog_codes'):
            permissions.pop('catalogue_cabinet_positions')
            return
        from app.catalogue.models.catalogue import Catalogue
        catalog_allow = Catalogue.objects(
            provider=provider_id,
            is_deleted__ne=True,
            public=True,
            code__in=catalog_allow['catalog_codes'],
        ).only(
            'id',
        ).as_pymongo().first()
        if not catalog_allow:
            permissions.pop('catalogue_cabinet_positions')

