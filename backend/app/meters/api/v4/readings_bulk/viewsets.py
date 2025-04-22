from bson import ObjectId

from celery.result import AsyncResult

from django.core.files import File
from django.http import HttpResponse, JsonResponse

from urllib.parse import quote

from rest_framework.response import Response
from rest_framework.request import Request

from api.v4.authentication import RequestAuth
from api.v4.viewsets import BaseLoggedViewSet
from api.v4.utils import permission_validator

from processing.data_producers.associated.meters import \
    get_current_readings_period
from processing.celery.tasks.dr_hugo_strange.export_area_meter import \
    export_meters_data_to_csv

from app.meters.models.meters_readings import (AreaMetersReadings,
                                               HouseMetersReadings)
from .meters_excel import AreaMetersStatsReport
from .permissions import WhiteListProvider
from .serializers import (
    MeterReadingsSerializer,
    MeterReadingsExcelSerializer,
    MeterReadingsPeriodSerializer,
    ExportMetersDataToCSVSerializer,
)


class BaseMeterReadingsViewSet(BaseLoggedViewSet):
    """
    Вывод списка показаний счетчиков по дому/квартире.
    """

    def list(self, request):
        serializer = MeterReadingsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        auth = RequestAuth(request)
        instance = getattr(self, 'readings_class')(
            provider=auth.get_provider_id(),
            account=auth.get_account_anyway(),
            binds=auth.get_binds(),
            **serializer.validated_data
        )
        results, read_only = instance.get_readings()
        return self.json_response(dict(results=results, read_only=read_only))


class HouseMeterReadingsViewSet(BaseMeterReadingsViewSet):
    readings_class = HouseMetersReadings


class AreaMeterReadingsViewSet(BaseMeterReadingsViewSet):
    readings_class = AreaMetersReadings


class BaseMeterReadingsExcelViewSet(BaseMeterReadingsViewSet):
    REPORT = AreaMetersStatsReport

    @permission_validator
    def list(self, request):
        serializer = MeterReadingsExcelSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        auth = RequestAuth(request)
        provider = auth.get_provider()
        actor = auth.get_account_anyway()
        binds = auth.get_binds()
        instance = getattr(self, 'readings_class')(
            provider=provider.id,
            account=actor,
            binds=binds,
            **serializer.validated_data
        )
        data, _ = instance.get_readings()
        report = self.REPORT(
            provider=provider,
            actor=actor,
            binds=binds,
        )
        report.DATA = data
        report.METER_TYPE = instance.METER_TYPE
        rows = report.get_rows()
        header = report.get_header()
        schema = report.get_extended_scheme(rows)
        file = report.get_xlsx(header=header,
                               rows=rows,
                               rows_after=None,
                               rows_before=None,
                               schema=schema)

        response = HttpResponse(
            File(file),
            content_type='application/vnd.openxmlformats-'
                         'officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = \
            'attachment; filename*=UTF-8\'\'{}.xlsx'.format(
                quote(header['report_name'])
            )
        return response


class AreaMeterReadingsExcelViewSet(BaseMeterReadingsExcelViewSet):
    readings_class = AreaMetersReadings


class HouseMeterReadingsExcelViewSet(BaseMeterReadingsExcelViewSet):
    readings_class = HouseMetersReadings


class MeterReadingsPeriodViewSet(BaseLoggedViewSet):

    def list(self, request):
        serializer = MeterReadingsPeriodSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        auth = RequestAuth(request)
        period = get_current_readings_period(
            auth.get_provider_id(),
            serializer.validated_data['house'],
            readings_stat=True
        )
        return self.json_response({'current_readings_period': period})


class ExportMetersDataToCSV(BaseLoggedViewSet):
    serializer_class = ExportMetersDataToCSVSerializer

    permission_classes = [
        WhiteListProvider,
    ]

    def create(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = export_meters_data_to_csv.delay(
            house_id=serializer.validated_data['house'],
            period=serializer.validated_data['period'],
        )
        return Response(data=dict(task_id=task.id), status=200)

    def retrieve(self, request: Request, pk: AsyncResult.id):
        task = AsyncResult(pk)
        if task.failed():
            return JsonResponse(data={'state': 'failed'})
        if task.successful():
            return Response(f'/api/v4/get_file/?file_id={task.result}')
        else:
            return JsonResponse(data={'state': 'wip'}, status=200)

