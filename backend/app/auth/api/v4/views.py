import traceback
import urllib.parse
import logging

import mongoengine
from django.shortcuts import redirect
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_201_CREATED,
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from api.v4.authentication import RequestAuth, get_session_id
from api.v4.partner_apps.partner_apps_crud import PartnerAppsLoggedTokenViewSet
from api.v4.permissions import SuperUserOnly, WhiteListedAuthOnly, IsAuthenticated
from api.v4.serializers import PrimaryKeySerializer
from api.v4.universal_crud import BaseCrudViewSet
from api.v4.viewsets import BaseLoggedViewSet
from app.auth.api.services.drivethrough_token_service import DriveThroughTokenService
from app.auth.api.v4.serializers import (
    FirstStepActivationSerializer,
    SecondStepActivationSerializer, DriveThroughTokenSerializer
)
from app.auth.api.v4.serializers import (
    ActorSerializer,
    AuthTokenPartnerApiUserSerializer,
    RegisterPartnerApiUserSerializer,
)
from app.auth.core.exceptions import PasswordError, UsernameError
from app.auth.models.actors import Actor
from processing.models.billing.account import Account
from app.personnel.models.personnel import Worker


logger = logging.getLogger('c300')


class ActorViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    http_method_names = ['get']
    serializer_class = ActorSerializer
    slug = 'apartment_meters'

    def get_queryset(self):
        provider_id = RequestAuth(self.request).get_provider_id()
        return Actor.objects(provider__id=provider_id)


class RegisterPartnerApiUserViewSet(BaseCrudViewSet):

    http_method_names = ['post', ]
    permission_classes = (SuperUserOnly,)
    serializer_class = RegisterPartnerApiUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        password = serializer.save()
        return Response(dict(password=password), status=HTTP_201_CREATED)


class AuthTokenPartnerApiUserViewSet(PartnerAppsLoggedTokenViewSet):

    http_method_names = ['post', ]
    permission_classes = (WhiteListedAuthOnly, )
    serializer_class = AuthTokenPartnerApiUserSerializer
    authentication_classes = []

    def create(self, request):
        try:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            access_token = serializer.save()
            data = dict(
                token=access_token.key,
                expiration=access_token.expiration,
            )
            status = HTTP_200_OK
        except (PasswordError, UsernameError) as data_error:
            data = dict(error=str(data_error))
            status = HTTP_401_UNAUTHORIZED
        return Response(data, status=status)


class ActivateUserViewSet(viewsets.ViewSet):
    """ViewSet для активации Worker"""
    permission_classes = []
    authentication_classes = []

    def list(self, request, pk, code):
        logger.debug('ActivateUserViewSet starts. PK: %s, code: %s', pk, code)
        pk = PrimaryKeySerializer.get_validated_pk(pk)

        try:
            worker: Worker = Worker.objects.get(pk=pk)
        except mongoengine.DoesNotExist as dne:
            logger.error('Account does not exist: %s', dne)
            return redirect('/#/error/activation')

        if "Tenant" in worker._type:
            logger.error('Это житель. Житель не должен быть здесь. '
                         '400: Bad Request')
            return Response(status=HTTP_400_BAD_REQUEST)

        try:
            worker.activate(code)
        except Exception as e:
            logger.error('ActivateUserViewSet exception %s', e)
            logger.error('ActivateUserViewSet traceback %s', traceback.format_exc())
            return redirect('/#/error/activation')

        logger.debug('ActivateUserViewSet redirect, reason - OK')
        return redirect('/#/login?' + urllib.parse.urlencode({'from': 'activate'}))


class FirstStepActivationViewSet(viewsets.ViewSet):
    """ViewSet для активации жителей"""
    permission_classes = []
    authentication_classes = []

    def list(self, request):
        logger.debug('FirstStepActivationViewSet starts')
        try:  # удалить сессию, если она уже есть
            session = get_session_id(request)
            actor = Actor.objects.get(sessions__id=session)
            actor.destroy_session(session)
        except mongoengine.DoesNotExist as dne:
            logger.error('Нет актора с текущей сессией: %s', dne)
        except mongoengine.ValidationError as ve:
            logger.error('Ошибка: %s', ve)

        serializer = FirstStepActivationSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        # logger.debug('Serializer data: %s', serializer.data)

        account_id, activation_code = serializer.data.values()

        try:
            account = Actor.objects.get(id=account_id)
        except mongoengine.DoesNotExist as dne:
            logger.error('Актор с id %s не найден: %s', account_id, dne)
            return redirect('/#/error/activation')

        if activation_code != account.activation_code:
            logger.error('Не верный код активации!')
            return redirect('/#/error/activation')

        account.activation_code = None
        account.activation_step = 2
        account.save()
        logger.debug('FirstStepActivationViewSet redirect')
        # TODO: ссылка на активацию жителя не рабочая: не понятно где он должен продолжать
        return redirect(f'/#/auth/activation/{account_id}')


class SecondStepActivationViewSet(viewsets.ViewSet):
    """Второй этап активации жителя. Сюда должны попадать после ввода информации о помещении"""
    def create(self, request):
        # TODO: не понятно откуда сюда должны попадать вообще
        logger.debug('SecondStepActivationViewSet starts')
        serializer = SecondStepActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.debug('Serializer validated data: %s', serializer.validated_data)

        account_id, area_number = serializer.validated_data.values()
        area_number = area_number.low
        try:
            account: Actor = Actor.objects.get(id=account_id)
        except mongoengine.DoesNotExist as dne:
            logger.error('Актора %s не найдено: %s', account_id, dne)
            return Response(status=HTTP_404_NOT_FOUND)

        if not account.activation_step or account.activation_step < 2:
            logger.error('Activation step != 2')
            return Response(status=HTTP_400_BAD_REQUEST)

        if account.is_blocked:
            logger.warning('Аккаунт заблокирован. Отправляем письмо на почту')
            account.send_activation_blocked_mail()

        if area_number.upper() != account.owner.area.str_number.upper():
            logger.error('Не совпадает введённый номер помещения '
                         'с номером помещения, который находится в БД')
            account.activation_step += 1
            account.save()
            return Response(status=HTTP_400_BAD_REQUEST)

        # следующее условие нужно для того, чтобы письмо с паролем отправлялось
        # при активации аккаунта сотрудником. Стандартный flow не работает,
        # потому что при активации сотрудником has_access сразу же становиться
        # равным True
        if account.has_access:
            account.set_new_password()

        account.activation_code = None
        account.activation_step = None
        account.has_access = True
        account.save()
        logger.debug('SecondStepActivationViewSet finished')

class DriveThroughAuthViewSet(BaseLoggedViewSet):
    """Интерфейс для взаимодействия с токеном сквозной авторизации
    из старого интерфейса
    """

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """Создает токен сквозной авторизации для авторизованного
        пользователя

        Args:
            Request приходит пустой

        Returns:
            key<str>: строковый токен, необходимый для авторизации в новом
                      интерфейсе

        """
        try:
            token = DriveThroughTokenService.create(
                self.request.user
            )
            return Response(
                DriveThroughTokenSerializer(token).data,
                status=HTTP_201_CREATED
            )
        except Exception as err:
            return Response(
                {'detail': f"Error occupied: {err}"},
                status=HTTP_400_BAD_REQUEST
            )
