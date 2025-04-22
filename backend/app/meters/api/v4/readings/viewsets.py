from collections import defaultdict
from datetime import datetime

from bson import ObjectId
from mongoengine import Q

from django.http import JsonResponse
from rest_framework.serializers import Serializer
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, \
    HTTP_400_BAD_REQUEST, HTTP_406_NOT_ACCEPTABLE

from api.v4.authentication import RequestAuth
from api.v4.serializers import json_serializer, PrimaryKeySerializer
from api.v4.utils import permission_validator
from api.v4.viewsets import BaseLoggedViewSet

from app.meters.api.v4.readings.serializers import \
    ImportMeterReadingsSerializer, MeterReadingsSerializer, \
    CabinetMetersSerializer

from app.meters.models.meter import AreaMeter, HouseMeter, \
    ReadingsValidationError, ReadingsExistValidationError
from app.meters.tasks.import_meter_readings import parse_meter_readings, \
    save_meter_readings
from app.meters.models.tasks import ImportMeterReadingsTask
from app.meters.models.choices import ImportReadingsTaskStatus

from app.area.models.area import Area
from processing.models.billing.settings import ProviderAccrualSettings
from processing.data_producers.associated.base import get_houses_meters_periods

from lib.gridfs import put_file_to_gridfs


_IMPORT_READINGS_FILE_EXTENSIONS = ['csv']


class AreaMetersAllReadingsViewSet(BaseLoggedViewSet):

    http_method_names = ['patch']
    serializer_class = CabinetMetersSerializer  # ~ meters: [ {_id, values} ]

    slug = 'payments'

    def partial_update(self, request, pk):

        serializer: Serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)  # для validated_data

        meter_values: dict = {meter['id']: meter['values']
            for meter in serializer.validated_data['meters']}  # many=True

        area: dict = Area.objects.only('house').as_pymongo().with_id(pk)
        house_id: ObjectId = area['house']['_id']

        request_auth = RequestAuth(request)
        provider_id: ObjectId = request_auth.get_provider_id()
        accrual_settings: dict = ProviderAccrualSettings.objects(
            _type='ProviderAccrualSettings',
            provider=provider_id, house=house_id,
        ).as_pymongo().first()
        preservation_interval: int = \
            accrual_settings.get('meters_preservation') or 0

        period: datetime = get_houses_meters_periods(
            provider_id=provider_id, house=house_id,
            accrual_settings=[accrual_settings] if accrual_settings else None
        )[house_id]

        now: datetime = datetime.now()  # текущая дата и время
        binds = request_auth.get_binds()  # : BindsPermissions

        area_meter_ids: list = AreaMeter.objects(  # актуальные ИПУ в помещении
            AreaMeter.get_binds_query(binds)  # включает _type и is_deleted
            & Q(area__id=pk) & Q(is_automatic__ne=True)
            & (Q(working_finish_date=None) | Q(working_finish_date__gte=now))
        ).distinct('id')

        if [*meter_values].sort() != area_meter_ids.sort():
            return Response(data={'errors': [
                "Необходимо передать показания всех приборов учета помещения"
            ]}, status=HTTP_400_BAD_REQUEST)

        meters: dict = {meter.id: meter for meter in
            AreaMeter.objects(id__in=area_meter_ids)}  # полноценные документы!

        # get_(super)_account: Tenant или Worker
        account = request_auth.get_account() or request_auth.get_super_account()
        creator: str = account._type[0].lower()  # ReadingsCreator.WORKER?

        data = defaultdict(list)
        incorrect_values: bool = False

        for meter_id, values in meter_values.items():
            meter: AreaMeter = meters[meter_id]

            if meter.is_preserved(preservation_interval):  # законсервирован?
                data['errors'].append("Запрещена передача показаний ИПУ"
                    f" №{meter.serial_number or 'ОТСУТСТВУЕТ'}")
                meters.pop(meter_id)  # WARN удаляем прибор учета
                continue

            try:
                meter.add_readings(
                    period=period, values=values,
                    actor_id=account.id, creator=creator,
                    values_are_deltas=False,  # всегда абсолютное значение
                    comment="При оплате по приходному кассовому ордеру",
                    allow_float=False,  # дробная часть отбрасывается
                )
            except ReadingsExistValidationError:
                data['errors'].append("Повторная передача показаний ИПУ"
                    f" №{meter.serial_number or 'ОТСУТСТВУЕТ'}"
                    f" за {period.month}.{period.year}")
                meters.pop(meter_id)  # WARN удаляем прибор учета
            except ReadingsValidationError:
                data['errors'].append("Некорректные показания ИПУ"
                    f" №{meter.serial_number or 'ОТСУТСТВУЕТ'}")
                # meters.pop(meter_id)  # WARN удаляем прибор учета
                incorrect_values = True  # все или ничего

        if incorrect_values or not meters:  # ошибки?
            data['errors'].append("Показания приборов учета отклонены")
            return Response(data=data, status=HTTP_406_NOT_ACCEPTABLE)

        for meter in meters.values():  # : AreaMeter
            meter.save(ignore_meter_validation=True)

        return Response(status=HTTP_200_OK)  # TODO data / message?


class BaseReadingsManipulatorViewSet(BaseLoggedViewSet):
    """
    Базововое представление для работы с показаниями счетчика.
    """
    MODEL = None

    def partial_update(self, request, pk):
        return self._perform_action(pk, request)

    def destroy(self, request, pk):
        return self._perform_action(pk, request)

    @permission_validator
    def _perform_action(self, pk, request):
        pk, data, binds = self._get_validated_params(pk, request)

        meter = self._get_meter(binds, pk)
        if self.action == 'destroy':
            meter.delete_readings(data['period'])
            return Response()
        else:
            meter.add_readings(**data)
            meter.save(ignore_meter_validation=True)
            return self.json_response(dict(meter.readings[-1].to_mongo()))

    def _get_validated_params(self, pk, request):
        request_auth = RequestAuth(request)
        account = request_auth.get_account() or request_auth.get_super_account()
        binds = request_auth.get_binds()

        pk = PrimaryKeySerializer.get_validated_pk(pk)
        serializer = MeterReadingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(
            actor_id=account.id,
            creator=account._type[0].lower(),
            **serializer.validated_data
        )
        data['values_are_deltas'] = data.pop('as_deltas')
        return pk, data, binds

    def _get_meter(self, binds, pk):
        binds_query = self.MODEL.get_binds_query(binds)
        return self.MODEL.objects(binds_query, pk=pk).get()


class HouseMeterReadingsManipulatorViewSet(BaseReadingsManipulatorViewSet):
    slug = (
        'house_green_table',
        'apartment_meters_data',
        'apartment_meters',
    )
    MODEL = HouseMeter


class AreaMeterReadingsManipulatorViewSet(BaseReadingsManipulatorViewSet):
    slug = (
        'all_apartments_meters_data',
        'apartment_meters_data',
        'apartment_meters',
    )
    MODEL = AreaMeter


class ImportMeterReadingsViewSet(BaseLoggedViewSet):
    http_method_names = ['get', 'post', 'delete']
    slug = 'all_apartments_meters_data'
    serializer_classes = {
        'create': ImportMeterReadingsSerializer,
    }

    def create(self, request, *args, **kwargs):
        """ Сохранение файла csv в gridfs и его парсинг. """
        request_auth = RequestAuth(request)
        account = request_auth.get_super_account()
        serializer = ImportMeterReadingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        file = data['meter_file']
        self._check_file_extension(file)
        house_id = data['house_id']
        period = data['period']
        task_id = ObjectId()

        file_id, _ = put_file_to_gridfs(
            'ImportMeterReadingsTask', task_id, file.read(), filename=file.name,
        )

        model_task = ImportMeterReadingsTask(
            id=task_id, house_id=house_id, period=period, file=file_id
        )
        model_task.save()

        parse_meter_readings.delay(
            model_task.id, file_id, house_id, period, account.id
        )
        return JsonResponse(
            data={'result': 'success'},
            json_dumps_params={'default': json_serializer}
        )

    @action(
        detail=True,
        methods=['post'],
    )
    def save(self, request, pk):
        """ Создание новых счетчиков и сохранение новых показаний. """
        create_new_meters = request.data.get('create_new_meters') or False
        request_auth = RequestAuth(request)
        account = request_auth.get_super_account()
        model_task = ImportMeterReadingsTask.objects(
            house_id=pk,
        ).order_by('-created').first()
        celery_task = save_meter_readings.delay(
            model_task.id,
            create_new_meters,
            account.id,
        )
        model_task.celery_task = celery_task.id
        model_task.save()
        return JsonResponse(
            data={'results': 'success'},
            json_dumps_params={'default': json_serializer}
        )

    @permission_validator
    def retrieve(self, request, pk):
        """ Получение результатов импорта. """
        task = ImportMeterReadingsTask.objects(
            house_id=pk,
        ).as_pymongo().order_by('-created').first()
        if task:
            status = task['status']
            if status == ImportReadingsTaskStatus.FAILED:
                data = {
                    'status': ImportReadingsTaskStatus.FAILED.upper(),
                    'error': task.get('error'),
                    'created': task['created']
                }
            elif status == ImportReadingsTaskStatus.PARSED or status == ImportReadingsTaskStatus.FINISHED:
                data = {
                    'status': status.upper(),
                    'results': dict(
                        found=task['found'],
                        not_found=task['not_found'],
                        not_found_meters=task['not_found_meters'],
                        fail_meters=task['fail_meters'],
                        fail_readings=task['fail_readings'],
                    )
                }
                if status == ImportReadingsTaskStatus.FINISHED:
                    data.update(created=task['created'])
            else:
                data = {
                    'status': status.upper(),
                    'description': task.get('description')
                }
        else:
            data = {'status': 'EMPTY'}
        return JsonResponse(
            data=data,
            json_dumps_params={'default': json_serializer}
        )

    def destroy(self, request, pk):
        """ Отмена задачи. """
        task = ImportMeterReadingsTask.objects(
            house_id=pk,
        ).order_by('-created').first()
        if task:
            task.status = ImportReadingsTaskStatus.CANCELLED
            task.save()
        return JsonResponse(
            data={'results': 'success'},
            json_dumps_params={'default': json_serializer}
        )

    @staticmethod
    def _check_file_extension(file):
        try:
            extension = file.name.split('.')[-1] or None
            if extension not in _IMPORT_READINGS_FILE_EXTENSIONS:
                raise ValidationError('Неизвестный тип файла')
        except Exception:
            raise ValidationError('Неизвестный тип файла')
