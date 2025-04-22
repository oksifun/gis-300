import datetime
import mimetypes
from typing import Tuple

from bson import ObjectId
from dateutil.parser import parse
from django.http import HttpResponse, JsonResponse
from django.template.response import ContentNotRenderedError
from mongoengine import DoesNotExist
from rest_framework import mixins, viewsets, exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.viewsets import ViewSet

from rest_framework_mongoengine.viewsets import ModelViewSet, GenericViewSet

from app.personnel.models.personnel import Worker
from lib.gridfs import get_file_from_gridfs, delete_file_in_gridfs
from processing.models.billing.base import BindsPermissions
from processing.models.logging.user_activity import UserActivity
from utils.drf.authentication import RequestAuth
from utils.drf.base_serializers import json_serializer


class MongoModelViewSet(ModelViewSet):
    pass


class HandyRouter(DefaultRouter):

    def mix_routes(self, router):
        self.registry.extend(router.registry)


class ApiCreateModelMixin(mixins.CreateModelMixin):
    def create(self, request, *args, **kwargs):
        for processor in self.create_processors:
            self.request.POST._mutable = True
            processor.process(request, data=request.data)
        return super().create(request, *args, **kwargs)


class ApiUpdateModelMixin(mixins.UpdateModelMixin):
    def update(self, request, *args, **kwargs):
        for processor in self.update_processors:
            processor.process(request, data=request.data)
        return super().update(request, *args, **kwargs)


class ApiDestroyModelMixin(mixins.DestroyModelMixin):
    def destroy(self, request, *args, **kwargs):
        for processor in self.destroy_processors:
            processor.process(request, data=request.data)
        return super().destroy(request, *args, **kwargs)


class ModelViewSet(ApiCreateModelMixin,
                   mixins.RetrieveModelMixin,
                   ApiUpdateModelMixin,
                   ApiDestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
    """ModelViewSet with preprocessors"""
    pass


class ViewLogMixin:
    def create_log(self, request):
        u_act = UserActivity(
            url=request.path,
            method=request.method,
            addr=request.META['REMOTE_ADDR'],
        )
        if request.META.get('QUERY_STRING'):
            u_act.query_string = request.META['QUERY_STRING']
        if request.body:
            try:
                u_act.body = request.body.decode()
            except Exception:
                if request.content_type == 'multipart/form-data':
                    u_act.body = 'files (size {})'.format(len(request.body))
        # u_act.save()
        self.user_activity_log = u_act
        return u_act

    def finish_log(self, log, request, result):
        if not log:
            log = self.user_activity_log
        request_auth = RequestAuth(request)
        if request.user:
            log.user = request.user.pk
        if request.auth:
            log.session = request.auth.pk
            log.session_ip = request.auth.remote_ip
            log.provider = request_auth.get_provider_id()
            log.superuser = request_auth.is_super()
            if request.auth.slave and request.auth.slave.account:
                log.slave = request.auth.slave.account
        log.action = self.action
        log.result_status = result.status_code
        if hasattr(result, 'rendered_content'):
            content = result.rendered_content
        else:
            try:
                content = result.content
            except ContentNotRenderedError:
                content = None
        if content:
            log.result_len = len(content)
        time_delta = datetime.datetime.now() - log.created
        log.millis = \
            (time_delta.seconds * 10 ** 6 + time_delta.microseconds) / 1000
        log.save()


class SerializationMixin:
    """
    Миксин, определяющий работу с сериализатором, а также добавляющий методы

        - обработки запроса (следует определить serializer_classes)

        - определения существования прав Permission на вкладку (следует
        определить TAB_ID и изменить method_action_map)
    """
    TAB_ID = None
    serializer_classes = None
    method_action_map = {
        'POST': 'c',
        'GET': 'r',
        'PATCH': 'u',
        'PUT': 'u',
        'DELETE': 'd',
    }

    def handle_request(
            self: ViewSet
    ) -> Tuple[BindsPermissions, Worker]:
        """
        RequestAuth request handling
        :returns: BindsPermissions, Worker objects tuple
        """
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        account = request_auth.get_account()
        worker = Worker.objects(pk=account.id).get()
        return binds, worker

    def handle_super_request(
            self: ViewSet
    ) -> Worker:
        """
        RequestAuth superuser request handling
        :returns: Worker instance
        """
        request_auth = RequestAuth(self.request)
        worker = request_auth.get_super_account()
        return worker

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action)

    def get_serializer(self, data):
        serializer_class = self.get_serializer_class()
        return serializer_class(data=data)

    def get_validated_data(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def permit_action(
            self,
            worker_id: ObjectId,
    ) -> bool:
        """
        Метод проверки права пользователя на вкладку self.TAB_ID
        по request.action
        """
        from processing.models.permissions import Permissions
        permissions = Permissions.objects(
            actor_id=worker_id
        ).as_pymongo().get()
        action = self._get_action()
        if not permissions:
            raise exceptions.NotFound(detail='Permissions not found')
        if not permissions.get('granular', {}).get('Tab'):
            raise exceptions.NotFound(detail='Granular tabs not found')
        tabs = permissions['granular']['Tab']
        tab = tabs.get(self.TAB_ID)
        if not tab:
            raise exceptions.NotFound(detail=f'Tab {self.TAB_ID} not found')
        tab_obj = tab[0]
        tab_permissions = tab_obj.get('permissions')
        result = tab_permissions.get(action)
        if result:
            return result
        raise exceptions.PermissionDenied()

    def _get_action(self):
        return self.method_action_map.get(self.request.method)


class ParamsValidator:
    """ Валидация параметров запроса """

    PARAMS_SCHEMA = None

    def validate_params(self, request_params):
        """
        Сравнивает переданные параметры со схемой и
        преобразовывает к нужному типу.
        В случае ошибок - формирует соответсвующий ответ.
        :param request_params: объект с параметрами запроса
                               (data или query_params).
        :return: success_state - флаг успешности сбора и валидации (bool).
                 response_dict - в зависимости от успеха возвращает словарь
                    либо с преобразованными и провалидированными параметрами,
                    либо ключами, которые необходимы для класса Response.
        """
        # Предотвратим вызов метода при пустой схеме
        if not self.PARAMS_SCHEMA:
            raise NotImplementedError(
                'Нельзя вызвать метод validate_params, '
                'если PARAMS_SCHEMA не определена!'
            )

        # Получим и провалидируем параметры
        collected_params = {}
        errors = dict(required=[], types_errors=[])
        for param_setting in self.PARAMS_SCHEMA:
            name, setting = tuple(param_setting.items())[0]
            if not setting.get('type'):
                raise NotImplementedError(
                    f'Для параметра {name} не указан тип в схеме!!'
                )
            param = request_params.get(name)

            # Проверим обязательность параметра и примем соответсвующие меры
            if setting.get('required') and not param:
                errors['required'].append(name)
                continue

            # Проверим, что переданный тип параметра
            # (если он передан, так как может быть необязательным)
            # соответсвует требуемому
            try:
                if param:
                    if setting['type'].__name__ == 'bool':
                        param = self._get_bool(param)
                    elif setting['type'].__name__ == 'datetime':
                        param = parse(param)
                    else:
                        param = setting['type'](param)
                collected_params.update({name: param})
            except Exception:
                errors['types_errors'].append(
                    f"{name} must be type of "
                    f"{self._get_readable_type(setting)}"
                )

        # Если есть ошибки - сформируем ответ
        if errors['types_errors'] or errors['required']:
            response = dict(
                status=status.HTTP_400_BAD_REQUEST,
                data=dict(results=dict(errors=dict()))
            )
            r_errors = response['data']['results']['errors']
            if errors['required']:
                r_errors['required'] = (
                    f"Parameter(s) is required: "
                    f"{', '.join(errors['required'])}!"
                )
            if errors['types_errors']:
                r_errors['invalid_types'] = errors['types_errors']
            return False, response
        else:
            return True, collected_params

    def _get_bool(self, value):
        if value == 'true':
            return True
        elif value == 'false':
            return False
        elif value == 'null':
            return
        else:
            raise ValueError('Not a boolean string!')

    def _get_readable_type(self, setting):
        return (
            setting['type'].__name__.upper()
            if setting['type'].__name__ != 'ObjectId'
            else str.__name__.upper()
        )


class PublicViewSet(viewsets.ViewSet, ViewLogMixin):
    """
    Контролеры, которые не требуют аутентификации
    """
    authentication_classes = tuple()
    permission_classes = tuple()

    def dispatch(self, request, *args, **kwargs):
        # создать запись в логе о запросе
        u_act = self.create_log(request)
        # выполнить запрос
        result = super().dispatch(request, *args, **kwargs)
        # сохранить информацию о запросе в лог
        self.finish_log(u_act, request, result)
        return result


class BaseLoggedViewSet(viewsets.ViewSet, ViewLogMixin, ParamsValidator):

    protect_personal_data = False

    def dispatch(self, request, *args, **kwargs):
        # создать запись в логе о запросе
        u_act = self.create_log(request)
        # выполнить запрос
        result = super().dispatch(request, *args, **kwargs)
        # сохранить информацию о запросе в лог
        self.finish_log(u_act, request, result)
        return result

    @staticmethod
    def file_response(file_id, clear, html_as_file=True):
        """
        Метод принимает ID файла из GridFS и возвращает готовый класс
        респонса для контроллера с нужными заголовками
        :param file_id: ID файла
        :param clear: True если нужно почистить GridFS после скачки
        """
        try:
            some_file = get_file_from_gridfs(file_id, raw=True)
        except DoesNotExist:
            return Response('File not found.', status=status.HTTP_404_NOT_FOUND)

        if some_file.content_type:
            mime_type = some_file.content_type
        else:
            mime_type, encoding = mimetypes.guess_type(some_file.filename)
        response = HttpResponse(
            some_file.read(),
            content_type=mime_type,
            charset='utf-8'
        )
        filename = some_file.filename.replace(' ', '_').replace(',', '_')
        if mime_type != 'text/html' or html_as_file:
            disposition = f"attachment; filename={filename}"
            response['Content-Disposition'] = disposition.encode('UTF-8', 'replace')
        if clear:
            delete_file_in_gridfs(file_id)
        return response

    def json_response(self, data, status=None):
        if isinstance(data, list):
            response = {'results': data}
        elif isinstance(data, dict):
            response = data
        else:
            raise ValueError('Wrong data type for response')
        return JsonResponse(
            data=response,
            status=status,
            json_dumps_params={'default': json_serializer}
        )
