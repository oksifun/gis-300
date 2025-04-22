import traceback
from datetime import datetime, timedelta
from bson import ObjectId

from django.http import JsonResponse, \
    HttpResponseForbidden, HttpResponseBadRequest

from mongoengine import QuerySet, ValidationError

from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED, \
    HTTP_400_BAD_REQUEST, HTTP_410_GONE
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet

from app.gis.api.v4.filters import MongoParamsFilter, \
    ProviderIdFilter, ObjectTagFilter, ErrorTextFilter
from app.gis.api.v4.serializers import (
    GisQueuedSerializer, GisTaskSerializer, GisOperationSerializer,
    GisRecordSerializer, FullRecordSerializer, GisGuidSerializer,
    RegistryNumbersSerializer, PeriodSerializer, RecordIdSerializer,
    AccountNumbersSerializer, EntityPropsSerializer, MeteringsSerializer,
    ForceUpdateSerializer, GisSendRequestSerializer,
    OptionalDateIntervalSerializer, ExportClosedSerializer,
    PreviousMonthSerializer, ExportAsPrivateSerializer, AllRecordSerializer,
)
from app.gis.api.v4.house.serializers import HousesSerializer

from app.gis.models.choices import (
    GIS_OBJECT_CHOICES, GisObjectType,
    GIS_OPERATION_CHOICES, GisOperationType,
    GIS_RECORD_STATUS_CHOICES, GisRecordStatusType,
    GIS_GUID_STATUS_CHOICES, GisGUIDStatusType, GIS_TASK_STATE_CHOICES,
    GisTaskStateType
)
from app.gis.models.gis_queued import GisQueued
from app.gis.models.gis_record import GisRecord
from app.gis.models.guid import GUID
from app.gis.models.log_models import GisInErrorsLog

from app.gis.tasks.gis_task import GisTask
from app.gis.tasks.bills import export_pd, withdraw_pd
from app.gis.tasks.house import (
    import_house_data, export_house_data,
    import_provider_tenants, export_house_tenants, export_accounts,
    import_provider_meters, export_provider_meters, export_period_tenants,
    archive_closed_tenants, archive_provider_meters, import_house_tenants,
    import_provider_period_meters
)
from app.gis.tasks.contracts import import_provider_documents
from app.gis.tasks.metering import import_readings, export_readings
from app.gis.tasks.nsi import (
    import_common_nsi, import_group_nsi, import_provider_nsi,
    export_additional_services, export_municipal_services,
    export_municipal_resources
)
from app.gis.tasks.org import import_organisation_data, import_entity_data

from app.gis.utils.common import sb, fmt_period
from app.gis.utils.nsi import NSI_GROUP, NSIRAO_GROUP, \
    PRIVATE_GROUP, SERVICE_NSI
from app.gis.utils.houses import get_binded_houses, get_agent_providers
from app.meters.models.meter import Meter
from utils.drf.authentication import RequestAuth
from utils.drf.base_serializers import json_serializer
from utils.drf.base_viewsets import BaseLoggedViewSet
from utils.drf.constants_view import ConstantsBaseViewSet
from utils.drf.crud_filters import LimitFilterBackend
from utils.drf.crud_view import BaseCrudViewSet
from utils.drf.decorators import permission_validator
from utils.drf.permissions import SuperUserOnly


def get_requested_houses(request) -> list:

    from app.house.models.house import House
    from processing.models.billing.house_group import HouseGroup

    house_serializer = HousesSerializer(data=request.data)

    binds_permissions = RequestAuth(request).get_binds()
    house_binds_query: dict = House.get_binds_query(binds_permissions, raw=True)

    # WARN валидация преобразует str идентификаторы в ObjectId
    house_ids = set(house_serializer.get_param('houses'))  # преобразуем в набор

    house_groups: list = house_serializer.get_param('house_groups')
    group_house_ids = set(HouseGroup.objects(__raw__={
        '_id': {'$in': house_groups}, 'is_deleted': {'$ne': True},
    }).distinct('houses')) if house_groups else set()

    any_fias: list = house_serializer.get_param('fias')  # улицы, города, страны
    fias_house_ids = set(House.objects(__raw__={
        'fias_addrobjs': {'$in': any_fias}, 'is_deleted': {'$ne': True},
        **house_binds_query,
    }).distinct('id')) if any_fias else set()

    house_ids: set = house_ids | group_house_ids | fias_house_ids  # без дублей

    return House.objects(__raw__={
        '_id': {'$in': [*house_ids]},  # WARN набор не допускается
        **house_binds_query,
    }).distinct('id') if house_ids else []


def _get_object_url(guid_id: str) -> str:

    assert guid_id, "Некорректный идентификатор данных ГИС ЖКХ объекта"

    guid: GUID = GUID.objects.with_id(guid_id)
    assert guid is not None, "Идентификатор ГИС ЖКХ объекта не загружен"

    if guid.tag == GisObjectType.PROVIDER:
        return f"/#/providers/detail/{guid.object_id}/providerInfo"
    elif guid.tag in {GisObjectType.UO_ACCOUNT, GisObjectType.CR_ACCOUNT}:
        return f"/#/tenant/detail/{guid.object_id}"
    elif guid.tag in {GisObjectType.HOUSE}:
        return f"/#/houses/detail/{guid.object_id}/houseInfo"
    elif guid.tag in {GisObjectType.AREA}:
        return f"/#/areas/detail/{guid.object_id}/areaInfo"
    elif guid.tag == GisObjectType.AREA_METER:
        assert guid.premises_id, "Отсутствует идентификатор помещения"
        return f"/#/areas/detail/{guid.premises_id}/areaMeters"
    elif guid.tag == GisObjectType.HOUSE_METER:
        assert guid.premises_id, "Отсутствует идентификатор помещения"
        return f"/#/houses/detail/{guid.premises_id}/houseCounters"
    elif guid.tag == GisObjectType.LEGAL_ENTITY:
        assert guid.premises_id, "Отсутствует идентификатор помещения"
        from processing.models.billing.account import Tenant
        tenant_id: ObjectId = Tenant.objects(__raw__={
            'area._id': guid.premises_id,  # индекс
            'entity': guid.object_id,
        }).scalar('id').first()  # ~ only
        assert tenant_id, f"Лицевой счет ЮЛ {guid.object_id}" \
            f" в помещении {guid.premises_id} не найден"
        return f"/#/tenant/detail/{tenant_id}"
    elif guid.tag in {GisObjectType.ACCRUAL}:
        from processing.models.billing.accrual import Accrual
        accrual: dict = Accrual.objects(__raw__={
            '_id': guid.object_id,
        }).only('doc', 'account').as_pymongo().first()
        assert accrual, "Документ начислений не найден"
        return "/#/accruals" \
            f"/{accrual['account']['area']['house']['_id']}" \
            f"/edit/{accrual['doc']['_id']}" \
            f"/account?accountId={accrual['account']['_id']}"
    else:  # ссылка на форму не сформирована?
        raise Exception("Форма объекта с ошибкой не найдена")


class GisTasksConstants(ConstantsBaseViewSet):

    CONSTANTS_CHOICES = (
        (GIS_OPERATION_CHOICES, GisOperationType),
        (GIS_RECORD_STATUS_CHOICES, GisRecordStatusType),
        (GIS_GUID_STATUS_CHOICES, GisGUIDStatusType),
        (GIS_OBJECT_CHOICES, GisObjectType),
        (GIS_TASK_STATE_CHOICES, GisTaskStateType)
    )


class GisTaskViewSet(BaseCrudViewSet):
    serializer_class = GisTaskSerializer
    http_method_names = ['get']
    slug = 'gis_zkh'
    permission_classes = (SuperUserOnly,)

    def get_queryset(self) -> QuerySet:

        task_query: dict = {
            'name': {'$ne': 'gis.scheduled'},  # заменяется переданным в запросе
        }

        request_auth = RequestAuth(self.request)
        if request_auth.is_slave():  # Внешнее управление?
            task_query['providers'] = request_auth.get_provider_id()

        return GisTask.objects(__raw__=task_query).order_by('-saved')


class GisRecordViewSet(BaseCrudViewSet):
    serializer_class = GisRecordSerializer
    http_method_names = ['get']
    slug = ('gis_zkh', 'all_apartments_accruals')

    @staticmethod
    def actual_time(hours=96) -> datetime:

        return datetime.now() + timedelta(hours=-hours)

    @staticmethod
    def actual_date(weeks=4) -> datetime:

        return datetime.now() + timedelta(weeks=-weeks)

    def get_queryset(self) -> QuerySet:
        """Данные об операциях"""
        assert 'is_actual' not in self.request.query_params

        provider_id: ObjectId = RequestAuth(self.request).get_provider_id()

        return GisRecord.objects(__raw__={'$or': [
                {'provider_id': provider_id},
                {'agent_id': provider_id},
            ]
        }).order_by('-saved')


class FullRecordViewSet(BaseCrudViewSet):
    serializer_class = FullRecordSerializer
    http_method_names = ['get']
    slug = 'gis_zkh'
    permission_classes = (SuperUserOnly,)

    def get_queryset(self) -> QuerySet:
        """Детальные записи об операциях"""
        provider_id: ObjectId = RequestAuth(self.request).get_provider_id()

        return GisRecord.objects(__raw__={'$or': [
                {'provider_id': provider_id},
                {'agent_id': provider_id},
            ],
            # 'saved': {'$gte': GisRecordViewSet.actual_time()},
        }).order_by('-saved')


class AllGisRecordViewSet(BaseCrudViewSet):
    serializer_class = AllRecordSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']
    slug = 'gis_zkh'
    permission_classes = (SuperUserOnly,)

    def get_queryset(self) -> QuerySet:
        """Данные (операции) ГИС ЖКХ"""
        return GisRecord.objects.all().order_by('-saved')

    def get_object(self):
        """Получение объекта по `generated_id`"""
        queryset = self.filter_queryset(self.get_queryset())
        # Преобразуем pk в ObjectId
        obj = queryset.get(generated_id=ObjectId(self.kwargs['id']))
        self.check_object_permissions(self.request, obj)
        return obj

    def partial_update(self, request, *args, **kwargs):
        """ Изменение объекта с отлавливанием статуса 'restart' """
        # Вызываем метод валидации для проверки запроса
        self._validate_action(request)

        # Получаем объект для обновления
        instance = self.get_object()

        # Проверяем, если статус в запросе 'restart'
        if 'task_state' in request.data and request.data['task_state'] == 'restart':
            # Клонируем задачу
            new_instance = instance.clone_reset()
            # Перезапускаем задачу
            from app.gis.tasks.async_operation import send_request
            # форсированный запуск операции
            send_request.delay(new_instance.id, True)

        # выполняем стандартное обновление
        return super().partial_update(request, *args, **kwargs)

class GisRecordErrorsViewSet(BaseLoggedViewSet):
    """
    Получение ошибок, связанных с записью GisRecord.
    """
    slug = 'gis_zkh'
    permission_classes = (SuperUserOnly,)

    def retrieve(self, request, pk):
        """
        Получение всех ошибок для GisRecord по ID.
        """
        try:
            # Получение GisRecord по ObjectId
            record = GisRecord.objects.get(generated_id=ObjectId(pk))
        except Exception as exc:
            return Response({"error": f"GisRecord error. {exc}"}, status=404)

        # Ошибки операции (поле `error`)
        operation_error = record.error

        # Предупреждения (поле `warnings`)
        warnings = record.warnings if hasattr(record, 'warnings') else []

        # Ошибки GUID, связанные с `record_id` записи GisRecord
        guid_errors = GUID.objects.filter(
            record_id=record.generated_id,
            status=GisGUIDStatusType.ERROR
        ).only(
            'id', 'provider_id', 'premises_id',
            'object_id', 'tag', 'desc',
            'gis', 'root', 'version',
            'unique', 'number',
            'updated', 'deleted', 'saved',
            'record_id', 'transport',
            'status', 'error',
        )

        guid_errors_serialized = GisGuidSerializer(guid_errors,many=True).data

        # Формирование ответа
        response_data = {
            "operation_error": operation_error,  # Ошибка операции
            "warnings_count": len(warnings) if warnings else 0,  # Список предупреждений
            "warnings": warnings,  # Список предупреждений
            "guid_errors_count": len(guid_errors_serialized)
                if guid_errors_serialized else 0, # количество ошибок
            "guid_errors": guid_errors_serialized,  # Ошибки GUID
        }
        return Response(response_data, status=200)

class GisGuidViewSet(BaseCrudViewSet):
    serializer_class = GisGuidSerializer
    http_method_names = ['get', 'post', 'put']
    slug = ('gis_zkh', 'houses')

    lookup_field = 'id'  # добавляется в get_object, по умолчанию = 'pk'

    filter_backends = (
        ProviderIdFilter, ObjectTagFilter, ErrorTextFilter,
        SearchFilter, OrderingFilter,
        LimitFilterBackend,  # ~ BaseCrudViewSet.filter_backends
        MongoParamsFilter,  # WARN после других фильтров
    )  # : tuple

    search_fields = ['error']

    ordering_fields = ['saved']
    ordering = ['-saved']  # по умолчанию

    def get_queryset(self) -> QuerySet:
        """Данные (идентификаторы) ГИС ЖКХ"""
        return GUID.objects.all()

    @permission_validator
    def create(self, request, *args, **kwargs):  # POST/PUT
        """
        Выгрузка в ГИС ЖКХ данных объекта
        """
        object_id = ObjectId(request.data['object_id'])  # : str
        tag: str = request.data['tag']

        if not object_id or not tag:
            return Response(status=HTTP_400_BAD_REQUEST, data={
                'error': "Отсутствует идентификатор объекта"
            })  # TODO HttpResponseBadRequest?

        provider_id: ObjectId = \
            RequestAuth(self.request).get_provider_id()  # TODO request?

        from app.gis.services.house_management import HouseManagement

        if tag in {GisObjectType.HOUSE, GisObjectType.AREA, GisObjectType.ROOM}:
            return Response(status=HTTP_410_GONE, data={
                'message': f"Выгрузка {GUID.object_name(tag)} отключена"
            })  # TODO выгрузка данных дома, помещения или комнаты
        elif tag in {'Tenant', *GUID.ACCOUNT_TAGS}:
            _import = HouseManagement.importAccountData(provider_id,
                update_existing=True)  # принудительное обновление данных
            _import(object_id)  # WARN по всем направлениям платежа (начислений)
        elif tag in GUID.METER_TAGS:
            meter = Meter.objects(id=object_id).first()
            if not meter:
                raise ValueError(f'Счетчик с id {object_id} не найден')
            # Определяем house_id в зависимости от типа счётчика
            if meter._type and meter._type[1] == 'AreaMeter':
                house_id = getattr(meter.area, 'house', None).id
            elif meter._type and meter._type[1] == 'HouseMeter':
                house_id = getattr(meter, 'house', None).id
            else:
                raise ValueError(f'Неизвестный тип счетчика {object_id}, '
                                 f'не могу определить дом')
            _import = HouseManagement.importMeteringDeviceData(
                provider_id, house_id,
                update_existing=True)  # принудительное обновление данных
            _import(object_id)
        else:  # неопределенный тип объекта!
            return Response(status=HTTP_400_BAD_REQUEST, data={
                'message': f"Выгрузка {GUID.object_name(tag)} не поддерживается"
            })

        return Response(status=HTTP_202_ACCEPTED, data={  # TODO 200_OK?
            'message': f"Данные {GUID.object_name(tag)} выгружаются в ГИС ЖКХ"
        })

    @action(detail=True)  # methods=[GET], url_path=gis/guids/{pk}/object_url/
    def object_url(self, request, **kwargs):  # args = (request)
        """
        Формирование ссылки на объект по идентификатору ГИС ЖКХ
        """
        guid_id: str = kwargs.get(self.lookup_field)

        try:
            url: str = _get_object_url(guid_id)
        except Exception as exc:
            return Response(
                data={'error': str(exc)}, status=HTTP_400_BAD_REQUEST
            )
        else:
            return Response(data={'url': url}, status=HTTP_200_OK)


class GisQueuedViewSet(BaseCrudViewSet):
    serializer_class = GisQueuedSerializer
    http_method_names = ['get']
    slug = 'gis_zkh'
    permission_classes = (SuperUserOnly,)

    def get_queryset(self) -> QuerySet:
        """Данные подлежащих выгрузке в ГИС ЖКХ объектов Системы"""
        provider_id: ObjectId = RequestAuth(self.request).get_provider_id()

        return GisQueued.objects(__raw__={
            'house_id': {'$in': [*get_binded_houses(provider_id)]}
        }).order_by('-saved')


class GisProviderNSIViewSet(BaseLoggedViewSet):

    slug = 'gis_zkh'

    @permission_validator
    def list(self, request) -> JsonResponse:

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        from processing.models.billing.service_type import ServiceTypeGisName
        # имеющиеся справочники организации: ReferenceNumber: 'ReferenceName'
        provider_references: dict = ServiceTypeGisName.references(provider_id)

        return self.json_response({
            'private_nsi': PRIVATE_GROUP,  # все частные справочники
            'missing_nsi': {num: title for num, title in PRIVATE_GROUP.items()
                if num not in provider_references},  # отсутствующие справочники
            'service_nsi': {num: title for num, title in PRIVATE_GROUP.items()
                if num in SERVICE_NSI},  # (частные) справочники услуг
        })


class HouseProvidersViewSet(BaseLoggedViewSet):

    slug = ('gis_zkh', 'houses', 'providers')

    @permission_validator
    def list(self, request):

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        from processing.models.billing.provider.main import Provider
        providers = Provider.objects(
            __raw__={
                # только обслуживаемые (РЦ) управляющие домами организации (УО)
                '_id': {'$in': get_agent_providers(provider_id)},
            },
        ).only(
            'str_name',
        ).as_pymongo()
        return JsonResponse(
            data={
                str(provider['_id']): provider['str_name']
                for provider in providers
            },
            json_dumps_params={'default': json_serializer},
        )


class GisCommonNsiViewSet(BaseLoggedViewSet):
    slug = 'gis_zkh'

    @permission_validator
    def list(self, request):

        return self.json_response({'nsi': NSI_GROUP, 'nsirao': NSIRAO_GROUP})


class _BaseInterServiceViewSet(ViewSet):
    """
    Контролеры, которые не требуют аутентификации
    """
    authentication_classes = tuple()
    permission_classes = tuple()


class _BaseGisRequestViewSet(_BaseInterServiceViewSet):
    serializer_class = GisSendRequestSerializer

    def _handle_request(self, request_data, celery_func):
        try:
            serializer = self.serializer_class(data=request_data)
            if serializer.is_valid(raise_exception=True):
                task = celery_func.delay(
                    **serializer.validated_data,
                )
                return JsonResponse(
                    data={
                        'task_id': task.id,
                        'message': 'Task created',
                    },
                )
            return JsonResponse(
                data={
                    'message': 'No task created',
                },
            )
        except Exception as exc:
            self._error_log(traceback.format_exc())
            raise exc

    @staticmethod
    def _error_log(msg):
        GisInErrorsLog(message=msg).save()


class GisSendRequestViewSet(_BaseGisRequestViewSet):
    serializer_class = GisSendRequestSerializer

    def create(self, request):
        from app.gis.tasks.async_operation import send_request
        return self._handle_request(request.data, send_request)

    def list(self, request):
        from app.gis.tasks.async_operation import send_request
        return self._handle_request(request.query_params, send_request)


class GisFetchResultViewSet(_BaseGisRequestViewSet):
    serializer_class = GisSendRequestSerializer

    def create(self, request):
        from app.gis.tasks.async_operation import fetch_result
        return self._handle_request(request.data, fetch_result)

    def list(self, request):
        from app.gis.tasks.async_operation import fetch_result
        return self._handle_request(request.query_params, fetch_result)


class GisOperationViewSet(BaseLoggedViewSet):

    slug = 'gis_zkh'
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def send_operation_request(request):
        """
        Отправка запроса операции
        """
        serialized_request = RecordIdSerializer(data=request.data)
        record_id: ObjectId = serialized_request.get_param('record_id')

        from app.gis.tasks.async_operation import send_request
        send_request.delay(record_id, True)  # форсированный запуск операции

        return JsonResponse(data={'message':
            f"Выполняется отправка запроса операции {record_id}"})

    @staticmethod
    def get_operation_result(request):
        """
        Получение результата операции
        """
        serialized_request = RecordIdSerializer(data=request.data)
        record_id: ObjectId = serialized_request.get_param('record_id')

        from app.gis.tasks.async_operation import fetch_result
        fetch_result.delay(record_id, True)  # форсированный запуск операции

        return JsonResponse(data={'message':
            f"Выполняется запрос результата операции {record_id}"})

    @staticmethod
    def import_org_registry(request):
        """
        Загрузка данных организации
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        serializer = EntityPropsSerializer(data=request.data)
        serializer.is_valid(raise_exception=False)
        if serializer.ogrn:  # реквизиты (организаций) ЮЛ?
            binds_permissions = RequestAuth(request).get_binds()
            entity_props: dict = serializer.entity_props(binds_permissions)

            import_entity_data.delay(provider_id, entity_props)

            return JsonResponse(data={'message':
                f"Выполняется выгрузка в ГИС ЖКХ {len(entity_props)}"
                f" ЮЛ из {len(serializer.ogrn)} запрошенных по ОГРН"})

        import_organisation_data.delay(provider_id)

        return JsonResponse(data={'message':
            "Выполняется загрузка данных поставщика информации"})

    @staticmethod
    def import_group_nsi(request):
        """
        Загрузка группы общих справочников
        """
        if not RequestAuth(request).is_super():
            return HttpResponseForbidden()

        import_group_nsi.delay('NSI')  # TODO запускать пачками?
        import_group_nsi.delay('NSIRAO')

        return JsonResponse(data={'message':
            "Выполняется загрузка групп общих справочников"})

    @staticmethod
    def import_common_nsi(request):
        """
        Загрузка общих справочников
        """
        serialized_request = RegistryNumbersSerializer(data=request.data)

        registry_numbers: list = \
            serialized_request.get_param('registry_numbers')

        import_common_nsi.delay(registry_numbers)

        return JsonResponse(data={'message':
            "Выполняется загрузка общих справочников"})

    @staticmethod
    def import_provider_nsi(request):
        """
        Загрузка частных справочников организации
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        serialized_request = RegistryNumbersSerializer(data=request.data)
        registry_numbers = serialized_request.get_param('registry_numbers') \
            or SERVICE_NSI  # : set

        for registry_number in registry_numbers:
            import_provider_nsi.delay(provider_id, registry_number)

        return JsonResponse(data={'message':
            "Выполняется загрузка частных справочников организации"})

    @staticmethod
    def export_provider_nsi(request):
        """
        Выгрузка частных справочников (услуг) организации
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        serialized_request = RegistryNumbersSerializer(data=request.data)
        registry_numbers = serialized_request.get_param('registry_numbers') \
            or SERVICE_NSI  # : set

        for registry_number in registry_numbers:
            if registry_number == 1:  # справочник дополнительных услуг?
                export_additional_services(provider_id)
            elif registry_number == 51:  # справочник коммунальных услуг?
                export_municipal_services(provider_id)
            elif registry_number == 337:  # справочник комм. ресурсов на ОДН?
                export_municipal_resources(provider_id)

        return JsonResponse(data={'message':
            "Выполняется выгрузка частных справочников (услуг) организации"})

    @staticmethod
    def import_provider_documents(request):
        """
        Загрузка устава (договора управления) управляющей домом организации
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            import_provider_documents.delay(provider_id, house_id)

        return JsonResponse(data={'message':
            "Выполняется загрузка ДУ домов управляющей организации"})

    @staticmethod
    def import_houses(request):
        """
        Загрузка данных дома и помещений
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            import_house_data.delay(provider_id, house_id)

        return JsonResponse(data={'message':
            "Выполняется загрузка данных домов и помещений"})

    @staticmethod
    def export_houses(request):
        """
        Выгрузка данных дома и помещений
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            export_house_data.delay(provider_id, house_id)

        return JsonResponse(data={'message':
            "Выполняется выгрузка данных домов и помещений"})

    @staticmethod
    def import_provider_tenants(request):
        """
        Загрузка ЛС (жильцов домов) управляющей организации по дому
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        # Проверяем наличие отдельных ЛС
        serializer = AccountNumbersSerializer(data=request.data)
        serializer.is_valid(raise_exception=False)

        # Получен список отдельных ЛС?
        if serializer.accounts:
            binds_permissions = RequestAuth(request).get_binds()
            house_tenants = serializer.house_tenants(binds_permissions)
            if not house_tenants:  # пустой список идентификаторов?
                return HttpResponseBadRequest("Указанные лицевые счета"
                    " не могут быть загружены из ГИС ЖКХ")
            for house_id, tenant_ids in house_tenants.items():
                import_provider_tenants.delay(provider_id, house_id, *tenant_ids)
            return JsonResponse(data={'message':
                "Выполняется загрузка из ГИС ЖКХ указанных лицевых счетов"})

        # Выгрузка по дому
        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            import_provider_tenants.delay(provider_id, house_id)

        return JsonResponse(data={'message':
            "Выполняется загрузка ЛС (жильцов домов) управляющей организации"})

    @staticmethod
    def import_house_tenants(request):
        """
        Загрузка ЛС (жильцов домов) управляющей организации по списку
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        # Выгрузка по дому
        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            import_house_tenants.delay(provider_id, house_id)

        return JsonResponse(data={'message':
            "Выполняется загрузка ЛС (жильцов домов) управляющей организации"})

    @staticmethod
    def export_provider_tenants(request):
        """
        Выгрузка ЛС (жильцов домов) организации в ГИС ЖКХ
        """
        provider_id = RequestAuth(request).get_provider_id()

        # Проверяем наличие ключей
        boolean_serializers = {
            'force_update': ForceUpdateSerializer,
            'export_closed': ExportClosedSerializer,
            'as_private': ExportAsPrivateSerializer
        }

        validated_data = {}
        for key, serializer_class in boolean_serializers.items():
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data[key] = serializer.validated_data.get(key, False)

        # Извлекаем ключи
        force_update = validated_data['force_update']
        export_closed = validated_data['export_closed']
        as_private = validated_data['as_private']

        # Проверяем наличие отдельных ЛС
        serializer = AccountNumbersSerializer(data=request.data)
        serializer.is_valid(raise_exception=False)

        # Проверяем наличие периодов выгрузки
        date_serializer = OptionalDateIntervalSerializer(data=request.data)
        date_serializer.is_valid(raise_exception=True)
        date_from = date_serializer.validated_data.get('date_from', None)
        date_till = date_serializer.validated_data.get('date_till', None)

        # Получен список отдельных ЛС?
        if serializer.accounts:
            binds_permissions = RequestAuth(request).get_binds()
            house_tenants = serializer.house_tenants(binds_permissions)
            if not house_tenants:  # пустой список идентификаторов?
                return HttpResponseBadRequest("Указанные лицевые счета"
                    " не могут быть выгружены в ГИС ЖКХ")
            for house_id, tenant_ids in house_tenants.items():
                export_accounts.delay(provider_id, house_id, *tenant_ids,
                                      update_existing=force_update,
                                      export_closed=export_closed,
                                      as_private=as_private,
                                      )
            return JsonResponse(data={'message':
                "Выполняется выгрузка в ГИС ЖКХ указанных лицевых счетов"})

        # Получены периоды выгрузки?
        elif date_from and date_till:
            for house_id in get_requested_houses(request) \
                    or get_binded_houses(provider_id):
                export_period_tenants.delay(
                    provider_id, house_id, date_from, date_till,
                    update_existing=force_update,
                    export_closed=export_closed,
                    as_private=as_private
                )
            return JsonResponse(data={'message':
            "Выполняется выгрузка в ГИС ЖКХ лицевых счетов домов по периодам"})

        # Обычная выгрузка (ЛС из последнего проведенного докнача)
        else:
            for house_id in get_requested_houses(request) \
                            or get_binded_houses(provider_id):
                export_house_tenants.delay(provider_id, house_id,
                                           update_existing=force_update,
                                           export_closed=export_closed,
                                           as_private=as_private
                                           )
            return JsonResponse(data={'message':
                "Выполняется выгрузка в ГИС ЖКХ лицевых счетов домов"})

    @staticmethod
    def archive_provider_tenants(request):
        """
        Архивация ЛС (жильцов домов) организации в ГИС ЖКХ
        """
        previous_month_serializer = PreviousMonthSerializer(data=request.data)
        previous_month_serializer.is_valid(raise_exception=True)
        previous_month: bool = \
            previous_month_serializer.validated_data.get('previous_month', False)

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            archive_closed_tenants.delay(
                provider_id, house_id,
                update_existing=True,
                previous_month=previous_month
            )

        return JsonResponse(data={'message':
            "Выполняется архивация данных ЛС домов организации"})

    @staticmethod
    def import_provider_meters(request):
        """
        Загрузка данных ПУ домов организации
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            import_provider_meters.delay(provider_id, house_id)

        return JsonResponse(data={'message':
            "Выполняется загрузка данных ПУ домов организации"})

    @staticmethod
    def import_provider_period_meters(request):
        """
        Загрузка данных ПУ домов организации по дате открытия
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        # Проверяем наличие периодов выгрузки
        date_serializer = OptionalDateIntervalSerializer(data=request.data)
        date_serializer.is_valid(raise_exception=True)
        date_from = date_serializer.validated_data.get('date_from', None)
        date_till = date_serializer.validated_data.get('date_till', None)

        # Получены периоды выгрузки?
        assert date_from and date_till, "Необходимо указать периоды выгрузки"

        # Проверяем необходимость загрузки закрытых
        export_closed_serializer = ExportClosedSerializer(data=request.data)
        export_closed_serializer.is_valid(raise_exception=True)
        export_closed: bool = \
            export_closed_serializer.validated_data.get('export_closed', False)

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):
            import_provider_period_meters.delay(
                provider_id, house_id, date_from, date_till,
                export_closed=export_closed,
            )

        return JsonResponse(data={'message':
            "Выполняется загрузка данных ПУ домов организации по периодам"})

    @staticmethod
    def export_provider_meters(request):
        """
        Выгрузка данных ПУ домов организации
        """
        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        # Проверяем наличие ключей
        boolean_serializers = {
            'force_update': ForceUpdateSerializer,
            'export_closed': ExportClosedSerializer,
        }
        validated_data = {}
        for key, serializer_class in boolean_serializers.items():
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data[key] = serializer.validated_data.get(key, False)

        # Извлекаем ключи
        force_update = validated_data['force_update']
        export_closed = validated_data['export_closed']

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):
            if export_closed:# ~ keys:
                archive_provider_meters.delay(
                    provider_id, house_id,
                    update_existing=force_update
                )
            else:
                export_provider_meters.delay(
                    provider_id, house_id,
                    update_existing=force_update
                )

        return JsonResponse(data={'message':
            "Выполняется выгрузка данных ПУ домов организации"})

    @staticmethod
    def import_readings(request):
        """
        Загрузка снятых за период показаний ПУ (помещений) домов
        """
        serializer = MeteringsSerializer(data=request.data)
        period = serializer.get_param('period')

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys:
            import_readings.delay(provider_id, house_id, period)

        return JsonResponse(data={'message': "Выполняется загрузка"
            f" из ГИС ЖКХ показаний ПУ за {fmt_period(period)}"})

    @staticmethod
    def export_readings(request):
        """
        Выгрузка показаний ПУ (помещений) домов
        """
        serializer = MeteringsSerializer(data=request.data)
        period = serializer.get_param('period')
        is_collective = serializer.get_param('is_collective') or False

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys
            export_readings.delay(provider_id, house_id, period, is_collective)

        return JsonResponse(data={'message': "Выполняется выгрузка"
            f" в ГИС ЖКХ показаний {'ОД' if is_collective else 'И'}ПУ"
            f" за {fmt_period(period)}"})

    @staticmethod
    def export_pd(request):
        """
        Выгрузка ПД за (текущий) период
        """
        period_serializer = PeriodSerializer(data=request.data)
        period = period_serializer.get_param('period')

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys
            export_pd.delay(provider_id, house_id, period,
                element_limit=200)  # WARN максимум 500

        return JsonResponse(data={'message':
            f"Выполняется выгрузка ПД за {fmt_period(period)}"})

    @staticmethod
    def withdraw_pd(request):
        """
        Отзыв ПД за (текущий) период
        """
        period_serializer = PeriodSerializer(data=request.data)
        period = period_serializer.get_param('period')

        provider_id: ObjectId = RequestAuth(request).get_provider_id()

        for house_id in get_requested_houses(request) \
                or get_binded_houses(provider_id):  # ~ keys
            withdraw_pd.delay(provider_id, house_id, period)

        return JsonResponse(data={'message':
            f"Выполняется отзыв ПД за {fmt_period(period)}"})

    @permission_validator
    def create(self, request):

        TASK_METHODS = {
            'send_operation_request': self.send_operation_request,
            'get_operation_result': self.get_operation_result,
            'import_provider_documents': self.import_provider_documents,
            'import_org_registry': self.import_org_registry,
            'import_common_nsi': self.import_common_nsi,
            'import_group_nsi': self.import_group_nsi,
            'import_houses': self.import_houses,
            'export_houses': self.export_houses,
            'import_provider_nsi': self.import_provider_nsi,
            'export_provider_nsi': self.export_provider_nsi,
            'import_provider_tenants': self.import_provider_tenants,
            'import_house_tenants': self.import_house_tenants,
            'import_provider_meters': self.import_provider_meters,
            'import_provider_period_meters': self.import_provider_period_meters,
            'export_provider_meters': self.export_provider_meters,
            'import_readings': self.import_readings,
            'export_provider_tenants': self.export_provider_tenants,
            'archive_provider_tenants': self.archive_provider_tenants,
            'export_readings': self.export_readings,
            'export_pd': self.export_pd,
            'withdraw_pd': self.withdraw_pd,
        }  # TODO __class__.getattr

        serializer = GisOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_name: str = serializer.validated_data['task']

        if task_name not in TASK_METHODS:
            return self.json_response(data={
                'message': f"Задача ГИС ЖКХ {sb(task_name)} не найдена"
            }, status=HTTP_400_BAD_REQUEST)

        try:
            return TASK_METHODS[task_name](request)
        except Exception as error:
            raise ValidationError(str(error))
