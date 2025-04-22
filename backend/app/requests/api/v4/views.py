import datetime

from bson import ObjectId
from django.http import HttpResponseNotFound, JsonResponse, \
    HttpResponseBadRequest, HttpResponse
from jinja2 import Template
from mongoengine import DoesNotExist

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_mongoengine.viewsets import ModelViewSet

from api.v4.authentication import RequestAuth
from api.v4.base_crud_filters import LimitFilterBackend
from api.v4.permissions import READONLY_ACTIONS
from api.v4.serializers import json_serializer
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet
from api.v4.utils import permission_validator
from api.v4.viewsets import BaseLoggedViewSet, SerializationMixin
from app.catalogue.models.catalogue import Catalogue
from app.messages.models.messenger import UserTasks
from app.personnel.models.personnel import Worker
from app.reports.core.utils import money_to_str
from app.requests.api.v4.filters import (
    NonstandardFilter,
    ForcedLimitFilter,
    StatisticDaysFilter,
    StatisticStatusesFilter,
)
from app.requests.api.v4.form.serializers import (
    MonitoringMessageSerializer,
    MonitoringPersonSerializer,
)
from app.requests.api.v4.serializers import (
    RequestCreateSerializer,
    RequestSerializer,
    RequestUpdateSerializer,
    RequestSampleSerializer,
    RequestAutoSelectSerializer,
    RequestBoundCallSerializer,
)
from app.requests.core.controllers.selectors import RequestSelector
from app.requests.core.controllers.services import RequestService
from app.telephony.api.v4.selectors.calls_selector import CallsSelector
from app.requests.core.utils import get_contracting_providers_for_request
from app.requests.models.request import (
    Request,
    RequestSample,
    RequestBlank,
    RequestAutoSelectExecutorBinds,
)
from app.telephony.models.call_log_history import Calls
from lib.barcode import get_barcode_image_io, generate_qr_code_for_blank_edit
from lib.gridfs import get_file_from_gridfs, put_file_to_gridfs
from processing.models.billing.account import Tenant
from processing.models.billing.files import Files
from app.requests.models.choices import RequestPayStatus
from processing.models.billing.storage import CompletionAct
from processing.models.exceptions import CustomValidationError


class RequestViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    serializer_classes = {
        'create': RequestCreateSerializer,
        'list': RequestSerializer,
        'retrieve': RequestSerializer,
        'partial_update': RequestUpdateSerializer,
    }
    # Добавим кастомный фильтр
    filter_backends = (
        LimitFilterBackend,
        NonstandardFilter,
        ForcedLimitFilter
    )
    slug = 'request_log'
    pagination_class = None

    PAID_REQUESTS_STATUSES = (
        RequestPayStatus.ON_THE_WAY,
        RequestPayStatus.GOT_REGISTRY,
        RequestPayStatus.PAID,
        None
    )

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        # Документы только для данной организации
        request_auth = RequestAuth(self.request)
        account = request_auth.get_super_account()
        binds = request_auth.get_binds()
        if account:
            UserTasks.clean_field('journal', account.pk)
        return Request.objects(
            Request.get_binds_query(binds),
            is_deleted__ne=True,
        ).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        account = request_auth.get_account()
        request.data['dispatcher'] = {'id': account.id}
        return super().create(request)

    @permission_validator
    def destroy(self, request, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        super_worker = request_auth.is_super()
        req = self.get_object_or_none()
        # Если заявка подана жителем, то может удалить только суперсотрудник
        if req.dispatcher.id or (not req.dispatcher.id and super_worker):
            req.delete()
            return Response()
        raise CustomValidationError("Заявка подана жителем, поэтому "
                                        "Вы не можете её удалить.")

    def partial_update(self, request, *args, **kwargs):
        """
        Особый переопределенный патч, который подпихивает данные
        из сессии для ведения истории изменения заявки
        """
        session_detail = self._get_session_info()
        kwargs['partial'] = True
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data
        # Подпихнем детали сессии
        instance.session_detail = session_detail
        if data.get('common_status') and data['common_status'] != 'performed':
            obj_request = Request.objects.get(id=data['id'])
            obj_request.total_rate, request.data['total_rate'] = None, None
            obj_request.rates, data['rates'] = [], []
            obj_request.save()
        serializer = self.get_serializer(
            instance, data=data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def _get_session_info(self):
        request_auth = RequestAuth(self.request)
        session = request_auth.get_session()
        session_detail = dict(
            master_session=dict(
                _id=session.id,
                account=session.account.id
            ),
            slave_session={},
            client_ip=self.request._request.META.get('REMOTE_ADDR', ''),
            datetime=datetime.datetime.now()
        )
        if session.slave:
            acc = request_auth.get_account()
            ss = dict(
                _id=session.slave.id,
                account=acc.id if acc else None,
                provider=(
                    session.slave.provider
                    if session.slave.provider
                    else None
                )
            )
            session_detail['slave_session'] = ss
        return session_detail


class RequestCountViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    serializer_class = RequestSerializer
    http_method_names = ['get']
    slug = 'request_log'
    # Нестандартный фильтр
    nf = NonstandardFilter()

    def list(self, request, *args, **kwargs):
        return self._get_results(request, count=True)

    def _get_results(self, request, count=False):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        queryset = Request.objects(
            Request.get_binds_query(binds),
            is_deleted__ne=True,
        )
        # Применение нестандартного фильтра
        results = self.nf.filter_queryset(request, queryset, None)
        return Response(
            data=(
                dict(count=results.count())
                if count
                else dict(results=results)
            ),
            status=status.HTTP_200_OK
        )


class RequestCountByDaysViewSet(RequestCountViewSet):
    """ Получения статистки по дням """

    nf = StatisticDaysFilter()

    def list(self, request, *args, **kwargs):
        return self._get_results(request)


class RequestsSamplesViewSet(BaseCrudViewSet):
    serializer_class = RequestSampleSerializer
    slug = (
        'requests_samples',
        {
            'name': 'request_log',
            'actions': READONLY_ACTIONS,
        },
    )
    paginator = None

    def create(self, request, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        request.data['provider'] = request_auth.get_provider_id()
        return super().create(request)

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return RequestSample.objects(
            RequestSample.get_binds_query(binds),
        ).order_by('title').all()


class RequestBlankViewSet(BaseLoggedViewSet):
    slug = 'request_log'

    def create(self, r, *args, **kwargs):
        auth = RequestAuth(r)
        provider = auth.get_provider()

        # Получаем шаблон бланка заявки
        blank_id = provider.request_blank
        params = dict(id=blank_id) if blank_id else dict(is_default=True)
        request_blank = RequestBlank.objects(**params).first()
        try:
            file_query = {'file_id': request_blank.file.file} if \
                request_blank.file.file else {'file_id': None,
                                              'uuid': request_blank.file.uuid}
            filename, file_bytes = get_file_from_gridfs(**file_query)
        except DoesNotExist:
            return HttpResponseNotFound()

        # Извлекаем данные из заявок и рендерим
        requests = Request.objects(id__in=r.data['ids'])
        rendered_requests = ''
        for request in requests:
            if 'AreaRequest' in request._type:
                if not request.tenant.phones and request.tenant.id:
                    tenant = Tenant.objects(
                        id=request.tenant.id).only('phones').get()
                    if not tenant.phones and (
                            request.other_person and request.other_person.id):
                        tenant = Tenant.objects(
                            id=request.other_person.id).only('phones').get()
                        request.other_person.phones = tenant.phones
                    else:
                        request.tenant.phones = tenant.phones
            executors = Worker.objects(id__in=request.executors)
            barcode = get_barcode_image_io(request.number)
            template = Template(file_bytes.decode('utf-8'))
            services = self.get_services(request_id=request.id)

            rendered_requests += template.render(
                request=request, executors=executors,
                barcode=barcode, services=services,
                qr_code=generate_qr_code_for_blank_edit(
                    provider_domain=provider.url_managers,
                    request_id=request.id
                )
            ) + '\n'

        file_id, _ = put_file_to_gridfs(
            resource_name=None,
            resource_id=None,
            file_bytes=str.encode(rendered_requests),
            filename='Заявки.html',
            content_type='text/html'
        )
        return JsonResponse({'file_id': str(file_id)})

    def retrieve(self, request, pk):
        return super().file_response(
            ObjectId(pk),
            clear=True,
            html_as_file=False,
        )

    @staticmethod
    def get_services(request_id: str) -> list:
        """
        Получение всех услуги по заявке, через акт выполненных работ.

        :param request_id: id Заявки(Request).
        :return: Список с услугами. Услуга dict(Наименование, Количество, Цена).
        """
        all_service = list()
        service_price_total = 0
        service_amount_total = 0
        act = CompletionAct.objects(
            request=request_id
        ).only(
            'positions'
        ).as_pymongo().first()
        if not act:
            return all_service

        # Получаем словари с id(service) и ценами(price) всех услуг.
        service_dictionaries = act.get('positions')

        # Сборка отчета.
        for dictionary in service_dictionaries:
            service_id = str(dictionary.get('service'))
            service_amount = int(dictionary.get('amount', 0))
            service_sum = dictionary.get('price', 0) * service_amount
            service = Catalogue.objects(
                id=service_id
            ).only(
                'title'
            ).as_pymongo().first()
            service_name = service.get('title', 'Услуга не опознана')

            # Показание для ряда "Итого".
            service_price_total += service_sum
            service_amount_total += service_amount

            # Добавляем услугу.
            all_service.append(
                dict(
                    name_service=service_name,
                    amount_service=service_amount,
                    price_service=money_to_str(service_sum),
                )
            )

        # Добавляем ряд "Итого".
        all_service.append(
            dict(
                name_service='Итого:',
                amount_service=service_amount_total,
                price_service=money_to_str(service_price_total),
            )
        )
        return all_service


class RequestCountByStatusViewSet(RequestCountViewSet):
    """ Получения статистки по статусам """

    nf = StatisticStatusesFilter()

    def list(self, request, *args, **kwargs):
        return self._get_results(request)


class RequestsFilesViewSet(ModelFilesViewSet):
    model = Request
    slug = 'request_log'

    def partial_update(self, request, pk):
        # получаем исходные данные
        request_auth = RequestAuth(request)
        current_provider = request_auth.get_provider()
        try:
            queryset = self.model.objects(pk=pk)
            obj = queryset.get()
            assert len(request.data)
        except Exception:
            return HttpResponseBadRequest('Неверные параметры запроса')
        # кладём файлы в базу
        files = {}
        files_to_delete = []
        for field, file in request.data.items():
            split_field = field.split('__')
            if split_field[0] == 'pull':
                array_field = split_field[1]
                file_id = ObjectId(file)
                updated = obj.update(
                    __raw__={
                        '$pull': {
                            array_field: {
                                'file.file': file_id
                            }
                        }
                    }
                )
                if updated:
                    files_to_delete.append(file_id)
                continue
            file_bytes = file.read()
            # Сохраним в GridFS новые файлы
            file_id, _ = put_file_to_gridfs(
                self.model.__name__,
                current_provider.pk,
                file_bytes,
                filename=file.name,
                content_type=file.content_type,
            )
            # Если на конце что-то вроде __7
            if split_field[-1].isdigit():
                push_field = f'push_all__{"__".join(split_field[:-1])}'
                photos = files.setdefault(push_field, list())
                photos.append(dict(
                    file=Files(
                        file=file_id,
                        name=file.name,
                        size=len(file_bytes),
                    ),
                    description=self._get_description(request, split_field)
                ))
            else:
                files['set__{}'.format(field)] = Files(
                    file=file_id,
                    name=file.name,
                    size=len(file_bytes),
                )
        if files:
            queryset.update(**files)
        # Удалим файлы
        self.delete_files(files_to_delete)
        return HttpResponse('success')

    @staticmethod
    def _get_description(request, split_field):
        description_name = 'description_{}'.format(split_field[-1])
        return request.query_params.get(description_name, '')


class RequestMonitoringViewSet(BaseLoggedViewSet, SerializationMixin):
    serializer_classes = {
        'message': MonitoringMessageSerializer,
        'persons_in_charge': MonitoringPersonSerializer,
    }
    slug = 'request_log'
    TAB_ID = '6436c8bf956c480030010d00'

    @action(detail=True, methods=['PATCH'])
    def message(self, request, pk, *args, **kwargs):
        """
        Добавление сообщений контролирующим лицом
        """
        validated_data = self.get_validated_data(request)
        binds, worker = self.handle_request()
        self.permit_action(worker_id=worker.id)
        RequestService(binds=binds, pk=pk).add_monitoring_message(
            created_by=worker.id,
            message=validated_data.get('message'),
            save=True,
        )
        return JsonResponse(data={'data': 'success'})

    @action(detail=True, methods=['PATCH', 'DELETE'])
    def persons_in_charge(self, request, pk, *args, **kwargs):
        """
        Изменение Ответственных лиц в контроле заявки
        """
        validated_data = self.get_validated_data(request)
        binds, worker = self.handle_request()
        self.permit_action(worker_id=worker.id)
        obj = RequestService(binds=binds, pk=pk)
        if request.method == 'PATCH':
            obj.add_persons_in_charge(
                persons=validated_data.get('id'),
                save=True,
            )
        elif request.method == 'DELETE':
            obj.del_persons_in_charge(
                persons=validated_data.get('id'),
                save=True,
            )
        return JsonResponse(data={'data': 'success'})

    @action(detail=True, methods=['PATCH'])
    def review(self, request, pk, *args, **kwargs):
        """
        Управление фактом ознакомления с контролем заявки
        """
        binds, worker = self.handle_request()
        RequestService(binds=binds, pk=pk).review_monitoring(
            person_id=worker.id,
            save=True,
        )
        return JsonResponse(data={'data': 'success'})


class RequestAutoSelectExecutor(ModelViewSet):
    slug = 'requests_parsing'
    serializer_class = RequestAutoSelectSerializer

    def get_queryset(self):
        queryset = RequestAutoSelectExecutorBinds.objects.all()
        provider = RequestAuth(self.request).get_provider_id()
        return queryset.filter(provider=provider)

    def create(self, request: Request, *args, **kwargs) -> JsonResponse:
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        provider = RequestAuth(self.request).get_provider_id()
        result = RequestAutoSelectExecutorBinds(
            **data.validated_data,
            provider=provider,
        ).save()
        return JsonResponse(
            data=result.to_mongo(),
            json_dumps_params={'default': json_serializer},
            status=status.HTTP_201_CREATED
        )


class RequestBoundCallsViewSet(BaseLoggedViewSet):
    def retrieve(self, request, pk, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        request_object = RequestSelector.get_object(pk=pk, binds=binds)
        if not request_object:
            return Response(
                data={'data': None},
                status=status.HTTP_404_NOT_FOUND
            )
        related_calls = CallsSelector \
            .from_request(request_object) \
            .as_result
        return Response(
            RequestBoundCallSerializer(
                related_calls,
                many=True
            ).data,
            status=status.HTTP_200_OK
        )


class RequestContractingProvidersViewSet(BaseLoggedViewSet):
    """
    Получение списка провайдеров подрядных организаций.
    """
    http_method_names = ['get']

    def list(self, request):
        request_auth = RequestAuth(request)
        binds = request_auth.get_binds()
        providers = get_contracting_providers_for_request(binds)
        for provider in providers:
            provider['id'] = provider.pop('_id')
        return self.json_response(
            data={
                'results': providers,
            },
        )
