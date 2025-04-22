import mimetypes

from bson import ObjectId
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
)
from mongoengine import ValidationError, DoesNotExist
from rest_framework import status
from rest_framework import viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from lib.gridfs import put_file_to_gridfs, delete_file_in_gridfs
from processing.models.billing.files import Files
from utils.drf.authentication import RequestAuth
from utils.drf.base_serializers import PrimaryKeySerializer
from utils.drf.base_viewsets import MongoModelViewSet, ViewLogMixin, \
    BaseLoggedViewSet
from utils.drf.crud_filters import LimitFilterBackend, ParamsFilter
from utils.drf.decorators import permission_validator


class CustomPagination(LimitOffsetPagination):
    default_limit = 150


class BaseCrudViewSet(MongoModelViewSet, ViewLogMixin):
    """
    Универсальный CRUD контроллер с
    предустановленными фильтрами по ограничению выдачи и
    с возможностью передовать mongoengine команды
    """
    protect_personal_data = False
    allow_destroy = False

    filter_backends = (
        LimitFilterBackend,
        ParamsFilter,
    )

    def get_object_or_none(self):
        try:
            return self.get_object()
        except Http404:
            return None

    def infest_request_data_by_provider(self, request, as_object=False):
        """Подмешивание ID организации из сессии, если не передан"""
        if not request.data.get('provider'):
            provider_id = RequestAuth(self.request).get_provider_id()
            if as_object:
                request.data['provider'] = {'id': provider_id}
            else:
                request.data['provider'] = provider_id

    def dispatch(self, request, *args, **kwargs):
        # создать запись в логе о запросе
        u_act = self.create_log(request)
        # выполнить запрос
        result = super().dispatch(request, *args, **kwargs)
        # сохранить информацию о запросе в лог
        self.finish_log(u_act, request, result)
        return result

    @permission_validator
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(self._process_results(serializer, request))

    @permission_validator
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self._process_results(serializer, request)
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(self._process_results(serializer, request))

    @permission_validator
    def partial_update(self, request, *args, **kwargs):
        self._validate_action(request)
        return super().partial_update(request, *args, **kwargs)

    @permission_validator
    def create(self, request, *args, **kwargs):
        self._validate_action(request)
        return super().create(request, *args, **kwargs)

    def _is_exists_protected_serializer(self):
        serializers = getattr(self, 'serializer_classes', [])
        return self.action + '_protected' in serializers

    def _get_one_object(self, collection, field, _id):
        """
        Получение одного объекта в сериализуемой части
        вложенного поля модели
        :param collection: модель коллекции полученная через self.get_object()
        :param field: название поля в модели с которым нужно работать
        :param _id: ID записи в списке вложенного поля field
        """

        embedded_object = [
            x for x in getattr(collection, field) if x.id == _id
        ]
        if embedded_object:
            setattr(collection, field, embedded_object)
            return Response(self.serializer_class(collection).data[field][0])
        return Response(
            dict(detail="Not found."),
            status=status.HTTP_404_NOT_FOUND
        )

    def _delete_object(self, collection, field, _id):
        """
        Удаление объекта.
        :param collection: модель коллекции полученная через self.get_object()
        :param field: название поля в модели с которым нужно работать
        :param _id: ID записи в списке вложенного поля field
        """

        if _id not in [x.id for x in getattr(collection, field)]:
            return Response(
                dict(detail="Not found."),
                status=status.HTTP_404_NOT_FOUND
            )
        embedded_object = [
            x for x in getattr(collection, field) if x.id != _id
        ]
        setattr(collection, field, embedded_object)
        collection.save()
        return Response(self.serializer_class(collection).data[field])

    def _create_object(self, collection, field, serialized_data, model):
        """
        Создание нового объекта вложенного поля модели.
        :param collection: модель коллекции полученная через self.get_object()
        :param field: название поля в модели с которым нужно работать
        :param serialized_data: Сериализованные данные из запроса.
                                Пример: SomeSerializer(data=request.data)
        :param model: модель вложенного поля field
        """

        if not serialized_data.is_valid():
            return Response(
                serialized_data.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        # Модель нового объекта
        new_raw_object = serialized_data._kwargs['data']
        new_object = model(**new_raw_object)
        # Получаем список объектов нужного поля
        object_place = getattr(collection, field)
        # Добавляем созданный объект
        object_place.append(new_object)
        collection.save()
        return Response(self.serializer_class(collection).data[field][-1])

    def _patch_object(self, collection, field, serializer, model, _id):
        """
        Изменение объекта вложенного поля модели.
        :param collection: модель коллекции полученная через self.get_object()
        :param field: название поля в модели с которым нужно работать
        :param serialized_data: Сериализованные данные из запроса.
                                Пример: SomeSerializer(data=request.data)
        :param model: модель вложенного поля field
        :param _id: ID записи в списке вложенного поля field
        """

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        # Модель измененного объекта
        new_raw_object = serializer.validated_data
        new_object = model(**new_raw_object)
        # Нужно найти поля, которые изменились, запихнуть их в поля
        # старой версии поля, чтобы _changed_fields зарегестрировали
        # изменения
        for old_object in getattr(collection, field):
            # Находим комнату
            if old_object.id == _id:
                # Проходим по каждому полю
                for object_field in old_object._fields:
                    # Если поле не было передано, то его не нужно
                    # проверять, т.к. null=True поля затрут данные
                    if object_field in new_raw_object:
                        old_field = getattr(old_object, object_field)
                        new_field = getattr(new_object, object_field)
                        # Если требует изменений - меняем!)
                        if new_field != old_field:
                            setattr(old_object, object_field, new_field)
        collection.save()
        # Оставляем только изменяемый объект
        return self._get_one_object(collection, field, _id)

    def operate_list_objects(
            self,
            request,
            object_name,
            object_serializer
    ):
        """
        Работа со спиком объектов вложенного поля (получение/добавление).
        :param request: Объект запроса
        :param object_name: название вложенного поля объекта
        :param object_serializer: его сериализатор
        :return: Response object
        """

        collection = self.get_object()
        # Получение списка объектов
        if request.method == 'GET':
            return Response(
                self.serializer_class(collection).data[object_name]
            )
        # Создание нового объекта
        elif request.method == 'POST':
            results = self._create_object(
                collection=collection,
                field=object_name,
                serialized_data=object_serializer(data=request.data),
                model=object_serializer.Meta.model
            )
            return results

    def operate_one_object(
            self,
            request,
            object_id,
            object_name,
            object_serializer
    ):
        """
        Работа с одним объектом (удаление/редактирование/получение одного).
        :param request: Объект запроса
        :param object_id: ID объекта из списка объектов вложенного поля
        :param object_name: название вложенного поля объекта
        :param object_serializer: его сериализатор
        :return: Response object
        """

        collection = self.get_object()
        try:
            object_id = ObjectId(object_id)
        except Exception:
            return Response(
                data=dict(detail='Invalid {} ID.'.format(object_name)),
                status=status.HTTP_400_BAD_REQUEST
            )
        # Если нет комнат
        if not getattr(collection, object_name):
            return Response(
                dict(detail="Not found."),
                status=status.HTTP_404_NOT_FOUND
            )

        # Получение комнаты
        if request.method == 'GET':
            # Оставляем только искомую комнату
            return self._get_one_object(collection, object_name, object_id)

        # Удаление
        elif request.method == 'DELETE':
            return self._delete_object(collection, object_name, object_id)

        # Изменение комнаты
        elif request.method == 'PATCH':
            results = self._patch_object(
                collection=collection,
                field=object_name,
                serializer=object_serializer(data=request.data),
                model=object_serializer.Meta.model,
                _id=object_id
            )
            return results


class PublicCrudViewSet(BaseCrudViewSet):
    """
    Контролеры, которые не требуют аутентификации
    """
    authentication_classes = tuple()
    permission_classes = tuple()


class ModelFilesViewSet(BaseLoggedViewSet):
    model = None
    flag = False

    @permission_validator
    def retrieve(self, request, pk):
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        file_id = PrimaryKeySerializer.get_validated_pk(
            request.query_params.get('file')
        )
        request_auth = RequestAuth(request)
        binds = request_auth.get_binds()
        model = self.model.objects(
            self.model.get_binds_query(binds),
            is_deleted__ne=True,
            id=pk,
        ).as_pymongo().first()
        self.parse_file(model, file_id)
        if not self.flag:
            return HttpResponseNotFound()

        return self.file_response(file_id, clear=False)

    @permission_validator
    def partial_update(self, request, pk):
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        # получаем исходные данные
        request_auth = RequestAuth(request)
        current_provider = request_auth.get_provider()
        try:
            queryset = self.model.objects(pk=pk)
            obj = queryset.get()
            assert len(request.data)
        except Exception:
            return HttpResponseBadRequest('Неверные параметры запроса')
        self.put_file(request, obj, queryset, current_provider.pk)
        return HttpResponse('success')

    def put_file(self, request, obj, queryset, provider_id,
                 sub_object_field_name=None):
        files = {}
        files_to_delete = []  # тут буду ID файлов для удаления из GridFS
        files_list = []
        for field, file in request.data.items():
            # Получим ID или UUID затираемых файлов
            old_file = self.retrieve_file_id(obj, field)
            if old_file:
                files_to_delete.append(old_file)

            # Сохраним в GridFS новые файлы
            file_id, _ = put_file_to_gridfs(
                self.model.__name__,
                provider_id,
                file.read(),
                filename=file.name,
                content_type=file.content_type,
            )
            if sub_object_field_name:
                field = f'{sub_object_field_name}__$__{field}'
            # Если на конце что-то вроде __7
            field_splitted = field.split('__')
            if field_splitted[-1].isdigit():
                files_list.append(Files(file=file_id, name=file.name))
                files[f"add_to_set__{'__'.join(field_splitted[:-1])}"] = files_list
            else:
                files[f'set__{field}'] = Files(file=file_id, name=file.name)
        queryset.update(**files)
        self.delete_files(files_to_delete)

    def delete_files(self, files):
        """
        Удаляем файлы из GridFS по их ID или UUID
        """
        for file in files:
            try:
                query = (
                    {'file_id': file}
                    if isinstance(file, ObjectId)
                    else {'file_id': None, 'uuid': file}
                )
                delete_file_in_gridfs(**query)
            except DoesNotExist:
                pass

    def retrieve_file_id(self, obj, path):
        """
        Находит в переданной модели ID или UUID файла по указанному пути
        """
        for field in path.split('__'):
            obj = getattr(obj, field, None)
            if not obj:
                return
        return obj.file or obj.uuid

    def parse_file(self, fields, file_id):
        type_of_field = {
            list: self.parse_file,
            dict: self.parse_file,

        }

        if type(fields) == dict and len(fields) > 0:
            for field in fields:
                if fields[field] == file_id:
                    self.flag = True
                if type_of_field.get(type(fields[field])):
                    type_of_field.get(type(fields[field]))(
                        fields[field],
                        file_id
                    )
        elif type(fields) == list:
            for i in fields:
                if i == file_id:
                    self.flag = True
                if type_of_field.get(type(i)):
                    type_of_field.get(type(i))(i, file_id)


class ModelFilesNewRulesViewSet(viewsets.ViewSet):
    """ Класс для работы с фалами по новому регламенту """
    model = None

    def partial_update(self, request, pk, **kwargs):
        # получаем исходные данные
        request_auth = RequestAuth(request)
        current_provider = request_auth.get_provider()
        try:
            obj = self.model.objects(pk=pk)
            assert len(request.data)
        except Exception:
            return HttpResponseBadRequest('Неверные параметры запроса')
        # кладём файлы в базу
        files = {}
        for field, file in request.data.items():
            file_id, uuid = put_file_to_gridfs(
                self.model.__name__,
                kwargs.get('owner_id') or current_provider.pk,
                file.read(),
                filename=file.name,
                content_type=file.content_type,
            )
            files['set__{}'.format(field)] = Files(file=file_id, name=file.name)
        obj.update(**files)
        return HttpResponse('success')
