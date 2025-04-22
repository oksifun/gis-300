import logging
import base64
import datetime
from typing import (
    Dict,
    Union,
    List,
)
from bson import ObjectId
from dateutil.relativedelta import relativedelta
from bson.errors import InvalidId
from mongoengine import DoesNotExist
from rest_framework import authentication, exceptions

import settings
from app.house.models.house import House
from app.personnel.models.personnel import Worker
from processing.models.billing.account import Tenant
from processing.models.billing.base import BindsPermissions
from app.auth.models.actors import Actor, SessionEmbedded, RoboActor
from processing.models.billing.provider.main import Provider
from processing.models.billing.session import Session
from processing.models.choices import PhoneType
from processing.models.logging.auth import UserActionWarning
from processing.models.logging.user_activity import UserActivity

ACTOR_TYPES = dict(
    Actor=Actor,
    RoboActor=RoboActor
)

logger = logging.getLogger('c300')


def _get_actor_session_id(request):
    """Достает ID сессии из кук"""
    cookies = request.COOKIES.get("session_id")
    if not cookies:
        raise DoesNotExist()
    try:
        return ObjectId(cookies)
    except InvalidId:
        raise DoesNotExist()


def get_session_id(request, is_ws=False) -> str or None:
    if is_ws:
        session_cookie = request
    else:
        session_cookie = request.COOKIES.get("session_id")
        if not session_cookie:
            return
    session_id = str(base64.b64decode(
        session_cookie.split("|")[-2].split(":")[1]
    ), 'utf-8')
    return session_id


def _check_user_request_rate(user, session):
    requests_number = UserActivity.objects(
        user=user.id,
        created__gte=datetime.datetime.now() - relativedelta(seconds=10),
    ).count()
    if requests_number > 100:
        UserActionWarning(
            message='too much requests',
            source='_check_user_request_rate',
            user=user.id,
            provider=user.provider.id,
            session=session.id,
        ).save()
        return False
    return True


def get_authenticators(actor: Actor,
                       session_id: ObjectId,
                       fetch_slave=True) -> (Actor, SessionEmbedded):
    """
    Возвращает модели актёра и сессии в зависимости от переданных параметров.
    """
    # Поиск нужной сессии из списка сессий
    session = next(x for x in actor.sessions if x.id == session_id)
    if fetch_slave:
        slave = getattr(session, 'slave', None)
        if slave:
            model = ACTOR_TYPES[slave._type]
            actor = model.objects.get(id=slave.id)
    return actor, session


class BaseAuth(authentication.BaseAuthentication):
    def authenticate(self, request):
        pass

    def authenticate_header(self, request):
        return 'Password'


class ActorSessionAuthentication(BaseAuth):
    """
    Аутентификация по Actor
    """
    def authenticate(self, request):
        try:
            session = _get_actor_session_id(request)
            actor = Actor.objects.get(sessions__id=session)
            if actor.is_super and not settings.DEVELOPMENT:
                remote_ip = request.META.get('HTTP_X_FORWARDED_FOR')
                if remote_ip not in settings.IP_SUPERS:
                    actor.deactivate_all_sessions()
                    raise exceptions.AuthenticationFailed("Wrong user location")
            actor, session = get_authenticators(actor, session)
            if not _check_user_request_rate(actor, session):
                raise exceptions.AuthenticationFailed("Too much requests")
            actor.is_authenticated = True
            return actor, session
        except DoesNotExist:
            raise exceptions.AuthenticationFailed()


class SuperActorSessionAuthentication(BaseAuth):
    def authenticate(self, request):
        try:
            session = get_session_id(request)
            actor = Actor.objects.get(
                sessions__id=session,
                is_super=True,
            )
            actor.parent_actor = actor
            return get_authenticators(actor, session, fetch_slave=False)
        except DoesNotExist:
            raise exceptions.AuthenticationFailed()


class MasterSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request) -> tuple or None:
        session_id = get_session_id(request)
        if not session_id:
            raise exceptions.AuthenticationFailed('Сессия не найдена')

        try:
            session = Session.objects.get(id=session_id)
            if not session.is_active:
                return
        except DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Session not found.") from e

        try:
            account_id = session.account.id
            if 'Tenant' in session.account._type:
                user = Tenant.objects.get(pk=account_id)
            else:
                user = Worker.objects.get(pk=account_id)
        except DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Account not found.") from e

        if not _check_user_request_rate(user, session):
            raise exceptions.AuthenticationFailed("Too much requests")
        return user, session


class SlaveSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        try:
            session = Session.objects.get(id=get_session_id(request))
            if not session.slave.account:
                return None
            if not session.is_active:
                return None
            account = Worker.objects(
                pk=session.slave.account,
            ).only(
                '_type',
            ).as_pymongo().first()
            if not account or 'Tenant' in account['_type']:
                user = Tenant.objects.get(pk=session.slave.account)
            else:
                user = Worker.objects.get(pk=session.slave.account)
            return user, session
        except (IndexError, KeyError, AttributeError) as e:
            return None
        except Session.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Session not found.") from e
        except Worker.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Account not found.") from e


class SuperSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        try:
            session = Session.objects.get(
                id=get_session_id(request),
                account__is_super=True,
            )
            if not session.is_active:
                return None
            user = Worker.objects.get(
                pk=session.account.id,
                is_super=True,
            )
            return user, session
        except (IndexError, KeyError, AttributeError) as e:
            return None
        except Session.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Session not found.") from e
        except Worker.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Account not found.") from e


class TokenActorSessionAuthentication(BaseAuth):
    def authenticate_header(self, request):
        return 'Token'

    def authenticate(self, request):
        try:
            session = ObjectId(request.query_params.get('_token'))
            actor = Actor.objects.get(sessions__id=session)
            return get_authenticators(actor, session)
        except DoesNotExist:
            raise exceptions.AuthenticationFailed()


class TenantOrTokenActorSessionAuthentication(BaseAuth):

    def authenticate_header(self, request):
        return 'Token or password'

    def authenticate(self, request):
        try:
            return self.get_token(request)
        except DoesNotExist:
            try:
                return self.get_tenant_session(request)
            except DoesNotExist:
                raise exceptions.AuthenticationFailed()

    def get_token(self, request):
        session = ObjectId(request.query_params.get('_token'))
        actor = Actor.objects.get(sessions__id=session)
        if not _check_user_request_rate(actor, session):
            raise exceptions.AuthenticationFailed("Too much requests")
        return get_authenticators(actor, session)

    def get_tenant_session(self, request):
        session = get_session_id(request)
        actor = Actor.objects.get(sessions__id=session)
        if not _check_user_request_rate(actor, session):
            raise exceptions.AuthenticationFailed("Too much requests")
        actor, session = get_authenticators(actor, session)
        if 'Tenant' != actor.owner.owner_type:
            return

        return actor, session


class TokenSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        try:
            session = Session.objects.get(id=request.query_params.get('_token'))
            if not session.is_active:
                return None
            if 'Tenant' in session.account._type:
                user = Tenant.objects.get(pk=session.account.id)
            else:
                user = Worker.objects.get(pk=session.account.id)
            return user, session
        except (IndexError, KeyError, AttributeError) as e:
            return None
        except Session.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Session not found.") from e
        except Worker.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Account not found.") from e


class TenantOrTokenSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        try:
            return self.get_token(request)
        except (IndexError, KeyError, AttributeError) as e:
            return None
        except (Session.DoesNotExist, Tenant.DoesNotExist):
            try:
                return self.get_tenant_session(request)
            except Session.DoesNotExist as e:
                raise exceptions.AuthenticationFailed(
                    "Session not found.") from e
            except Tenant.DoesNotExist as e:
                raise exceptions.AuthenticationFailed(
                    "Account not found.") from e
            except Exception as e:
                raise exceptions.AuthenticationFailed(
                    "Authentication failed.") from e

    def get_token(self, request):
        session = Session.objects.get(id=request.query_params.get('_token'))
        if not session.is_active:
            return None
        user = Tenant.objects.get(pk=session.account.id)
        return user, session

    def get_tenant_session(self, request):
        session = Session.objects.get(id=get_session_id(request))
        if not session.is_active:
            return None
        if 'Tenant' in session.account._type:
            user = Tenant.objects.get(pk=session.account.id)
        else:
            user = Worker.objects.get(pk=session.account.id)
        if 'Tenant' not in user._type:
            if not hasattr(session, 'slave'):
                raise exceptions.AuthenticationFailed("Account not found.")
            user = Tenant.objects.get(pk=session.slave.account)
        return user, session


class RequestAuthByActor:

    def __init__(self, request):
        self.session = request.auth
        self.user = request.user

    def is_super(self) -> bool:
        """Является ли юзер суперпользователем?"""
        return getattr(self.user, 'is_super', False)

    def get_account(self) -> Union[Actor, RoboActor]:
        """Возвращает модель пользователя сессии"""
        return self.user

    @staticmethod
    def __get_profile(
            actor: Union[Actor, RoboActor]
    ) -> Union[Provider, Worker, Tenant, None]:
        """Возвращает профиль актора."""
        if not actor:
            return None
        if isinstance(actor, Actor):
            model = Worker if actor.owner.owner_type == 'Worker' else Tenant
            return model.objects.get(id=actor.owner.id)
        return Provider.objects.get(id=actor.provider.id)

    def get_profile(self) -> Union[Provider, Worker, Tenant]:
        """Возвращает профиль пользователя или организации."""
        return self.__get_profile(self.user)

    def get_super_profile(self) -> Union[Provider, Worker, Tenant]:
        """Возвращает профиль супера."""
        return self.__get_profile(self.get_master_account())

    def get_master_account(self) -> Actor:
        for session in self.user.sessions:
            if session.id == self.session.id:
                return self.user
        return Actor.objects.get(sessions__id=self.session.id)

    def get_account_anyway(self):
        account = self.get_profile() or self.get_super_profile()
        if not account:
            raise DoesNotExist('Account not found.')
        return account

    def get_provider(self) -> Provider:
        """Возвращает модель организации пользователя"""
        return Provider.objects(id=self.user.provider.id).first()

    def get_provider_id(self) -> ObjectId:
        """Возвращает ID организации пользователя"""
        return self.user.provider.id

    def get_binds(self):
        """Получение привязки к организации и группе домов"""
        if self.is_super():
            return None
        if not self.user.binds_permissions:
            raise PermissionError('User has no binds_permissions.')
        return self.user.binds_permissions

    def is_slave_session(self) -> bool:
        """Является ли сессия slave-сессией?"""
        return bool(self.session.slave) or False

    def is_master_super(self) -> bool:
        """Является ли аккаунт владелец сессии суперпользователем."""
        master = self.get_master_account()
        return master.is_super

    def get_tenant_provider_id(self):
        if self.user and self.user.owner.owner_type == 'Tenant':
            house_id = self.user.owner.house.id
            provider_id = House.find_bound_provider(house_id)
            return provider_id
        return None


class RequestAuth:

    def __new__(cls, request):
        if isinstance(request.user, Actor):
            return super().__new__(RequestAuthByActor)
        return super().__new__(cls)

    def __init__(self, request):
        self.request = request

    def get_session(self) -> Session:
        return self.request.auth

    def get_account(self, session=None):
        session = session or self.get_session()
        if session and session.account:
            if getattr(session, 'slave', None):
                if session.slave.account:
                    account = self._get_user_dict(session.slave.account)
                    if 'Tenant' in account['_type']:
                        return Tenant.objects(
                            pk=session.slave.account,
                        ).first()
                    else:
                        return Worker.objects(
                            id=session.slave.account,
                            is_super__ne=True,
                        ).first()
                return None
            if isinstance(session.account, ObjectId):
                account = self._get_user_dict(session.account)
                account_type = account['_type']
                account_id = session.account
            else:
                account_type = session.account._type
                account_id = session.account.id
            if 'Tenant' in account_type:
                return Tenant.objects(pk=account_id).first()
            return Worker.objects(
                id=account_id,
                is_super__ne=True,
            ).first()
        return None

    def get_profile(self):
        return self.get_account()

    def get_super_account(self, session=None):
        session = session or self.get_session()
        if session and session.account:
            if 'Tenant' in session.account._type:
                return Tenant.objects(pk=session.account.id).first()
            return Worker.objects(pk=session.account.id).first()
        return None

    def get_account_anyway(self):
        account = self.get_account() or self.get_super_account()
        if not account:
            raise DoesNotExist('Account not found.')
        return account

    def get_provider(self, session=None) -> Provider:
        provider_id = self.get_provider_id(session)
        if provider_id:
            return Provider.objects(id=provider_id).first()
        return None

    def get_tenant_provider_id(self, session=None):
        session = session or self.get_session()
        account = self.get_account(session)
        if account:
            house_id = account.area.house.id
            provider = House.find_bound_provider(house_id, tenant=True)
            return provider
        return None

    def get_provider_id(self, session=None):
        session = session or self.get_session()
        if session and session.slave:
            if session.slave.provider:
                return session.slave.provider
            if session.slave.account:
                provider = self._get_user_slave_provider(session)
                if provider:
                    return provider
                else:
                    return self.get_tenant_provider_id(session)
        account = self.get_super_account(session)
        if account and account.provider:
            return account.provider.id
        else:
            return self.get_tenant_provider_id(session)

    def get_slave_session(self, session=None):
        session = session or self.get_session()
        if session and session.slave:
            return session.slave
        return None

    def is_super(self) -> bool:
        session = self.get_session()
        if session and session.account["is_super"]:
            return True
        else:
            return False

    def is_slave(self, session=None) -> bool:
        return bool(self.get_slave_session(session))

    def get_binds(self, session=None):
        binds = self._get_binds(session)
        if not binds:
            account = self.get_super_account(session)
            if account and account.is_super:
                return binds
            raise exceptions.AuthenticationFailed("No binds permissions.")
        return binds

    def _get_binds(self, session=None):
        session = session or self.get_session()
        if session and hasattr(session, 'slave') and session.slave:
            worker = self.get_account(session.slave)
            if not worker:
                # Если это не работник, то значит организация
                provider = Provider.objects(
                    pk=self.request.auth.slave.provider,
                ).only(
                    '_binds_permissions',
                ).as_pymongo().get()
                return BindsPermissions(
                    pr=self.request.auth.slave.provider,
                    hg=provider['_binds_permissions'].get('hg'),
                )
        else:
            worker = self.get_account(session)
        if worker:
            return worker._binds_permissions
        return None

    @staticmethod
    def _get_user_dict(account_id):
        account = Worker.objects(
            pk=account_id,
        ).only(
            'id',
            '_type',
            'provider',
        ).as_pymongo().first()
        if account:
            return account
        return Tenant.objects(
            pk=account_id,
        ).only(
            'id',
            '_type',
        ).as_pymongo().first()

    @staticmethod
    def _get_user_slave_provider(session):
        account = Worker.objects(
            pk=session.slave.account,
        ).only(
            'provider',
        ).as_pymongo().first()
        if account and account.get('provider'):
            return account['provider'].get('_id')
        return None


class ScopeAuth:
    """Класс аутентификации для сокета."""

    def __init__(self, scope: Dict):
        self.user = scope['user']
        self.session = scope['auth']

    def is_super(self) -> bool:
        """Является ли юзер суперпользователем?"""
        return self.user.get('is_super', False)

    def get_account(self) -> Union[Actor, RoboActor]:
        """Возвращает модель пользователя сессии"""
        return self.user

    @staticmethod
    def __get_profile(
            actor: Union[Actor, RoboActor]
    ) -> Union[Provider, Worker, Tenant, None]:
        """Возвращает профиль актора."""
        if not actor:
            return None
        if isinstance(actor, Actor):
            model = Worker if actor.owner.owner_type == 'Worker' else Tenant
            return model.objects.get(id=actor.owner.id)
        return Provider.objects.get(id=actor.provider.id)

    def get_profile(self) -> Union[Provider, Worker, Tenant]:
        """Возвращает профиль пользователя или организации."""
        return self.__get_profile(self.user)

    def get_work_phone(self) -> List[str]:
        """Возвращает рабочие номера телефонов сотрудника."""
        result = []
        if self.user['owner']['phones']:
            for phones in self.user['owner']['phones']:
                if phones['phone_type'] == PhoneType.WORK:
                    if phones['add']:
                        result.append(phones['add'])
        return result

    def get_super_profile(self) -> Union[Provider, Worker, Tenant]:
        """Возвращает профиль супера."""
        return self.__get_profile(self.get_master_account())

    def get_master_account(self) -> Actor:
        for session in self.user.sessions:
            if session.id == self.session.id:
                return self.user
        return Actor.objects.get(sessions__id=self.session.id)

    def get_account_anyway(self):
        account = self.get_profile() or self.get_super_profile()
        if not account:
            raise DoesNotExist('Account not found.')
        return account

    def get_provider(self) -> Provider:
        """Возвращает модель организации пользователя"""
        return Provider.objects(id=self.user.provider.id).first()

    def get_provider_id(self) -> ObjectId:
        """Возвращает ID организации пользователя"""
        return self.user.provider.id

    def get_binds(self):
        """Получение привязки к организации и группе домов"""
        if self.is_super():
            return None
        if not self.user.binds_permissions:
            raise PermissionError('User has no binds_permissions.')
        return self.user.binds_permissions

    def is_slave_session(self) -> bool:
        """Является ли сессия slave-сессией?"""
        return bool(self.session.slave) or False

    def is_master_super(self) -> bool:
        """Является ли аккаунт владелец сессии суперпользователем."""
        master = self.get_master_account()
        return master.is_super

    def get_tenant_provider_id(self):
        if self.user and self.user.owner.owner_type == 'Tenant':
            house_id = self.user.owner.house.id
            provider_id = House.find_bound_provider(house_id)
            return provider_id
        return None
