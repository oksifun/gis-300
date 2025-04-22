from bson import ObjectId
from dateutil.parser import parse
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponse

from api.v4.authentication import RequestAuth
from api.v4.forms.base import ConstantsBaseViewSet
from api.v4.forms.tenant import BaseTenantInfoViewSet
from api.v4.serializers import json_serializer, PrimaryKeySerializer
from api.v4.utils import permission_validator
from api.v4.viewsets import BaseLoggedViewSet, PublicViewSet
from app.catalogue.models.choices import CATALOGUE_SERVICE_GROUPS_CHOICES, \
    CatalogueGroup
from app.personnel.models.personnel import Worker
from app.requests.api.v4.form.serializers import RequestControlSerializer, \
    TenantRequestPhonesSerializer
from app.requests.models.choices import REQUEST_STATUS_PUBLIC_CHOICES, \
    RequestStatus, REQUEST_PAYABLE_TYPE_CHOICES, RequestPayableType
from app.requests.models.request import Request
from lib.helpfull_tools import by_mongo_path
from processing.data_producers.forms.requests import get_executors_workload
from processing.data_producers.forms.tenant_info import \
    get_tenant_requests_statistic
from processing.models.billing.account import Tenant, OtherTenant
from processing.models.billing.log import History
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES, \
    AccrualsSectorType, AreaLocations, REQUEST_SAMPLES_TYPES_CHOICES, \
    RequestSamplesType, PHONE_TYPE_CHOICES, PhoneType
from processing.references.requests import KINDS_TYPES_TREE


class RequestsExecutorsWorkloadViewSet(BaseLoggedViewSet):
    slug = 'request_log'

    def list(self, request):
        try:
            date_from = parse(request.query_params['date_from'])
        except Exception:
            return HttpResponseBadRequest('Параметр date_start неверен!')
        try:
            executors = [
                ObjectId(x) for x in request.query_params.getlist('executors')
            ]
        except Exception:
            return HttpResponseBadRequest(
                'Параметр executors должен содержать список ID'
            )
        results = get_executors_workload(date_from, executors)
        return JsonResponse(
            data=dict(results=results),
            json_dumps_params={'default': json_serializer}
        )


class RequestsKindTreeViewSet(PublicViewSet):

    def list(self, request):
        return JsonResponse(
            data=dict(results=KINDS_TYPES_TREE),
            json_dumps_params={'default': json_serializer}
        )


class RequestsConstantsViewSet(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = (
        (ACCRUAL_SECTOR_TYPE_CHOICES, AccrualsSectorType),
        (AreaLocations.CHOICES, AreaLocations),
        (REQUEST_SAMPLES_TYPES_CHOICES, RequestSamplesType),
        (CATALOGUE_SERVICE_GROUPS_CHOICES, CatalogueGroup),
        (REQUEST_STATUS_PUBLIC_CHOICES, RequestStatus),
        (PHONE_TYPE_CHOICES, PhoneType),
        (REQUEST_PAYABLE_TYPE_CHOICES, RequestPayableType),
    )


class RequestsHistoryViewSet(BaseLoggedViewSet):
    slug = 'request_log'

    @permission_validator
    def retrieve(self, request, pk):
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        query = dict(ref_id=pk, ref_model='Request')
        history = History.objects(**query).exclude(
            'fast_kinds').as_pymongo().first()
        if not history:
            return self.json_response(data={})
        accounts = self._get_accounts(history)
        for category in (x for x in history.values() if isinstance(x, list)):
            for action in category:
                acc_id = (action.get('master_session') or {}).get('account')
                action['str_name'] = accounts.get(acc_id, '')

        return self.json_response(data=dict(results=history))

    def _get_accounts(self, history):
        accounts = {
            y['master_session']['account']
            for x in history.values() if isinstance(x, list)
            for y in x if by_mongo_path(y, 'master_session.account')
        }
        return dict(
            Worker.objects(
                id__in=list(accounts),
                is_super__ne=True
            ).scalar('id', 'str_name')
        )


class RequestsHistoryConstantsViewSet(BaseLoggedViewSet):

    def list(self, request):
        """ Получение констант HistoryField """

        results = {
            x.name: getattr(x, 'verbose_name', '')
            for x in Request._fields.values()
        }
        # Скрываем от глаз некоторые поля
        exclude_fields = ('id', '_binds', '_type')
        for field in exclude_fields:
            del results[field]

        return JsonResponse(
            data=dict(results=results),
            json_dumps_params={'default': json_serializer}
        )


class RequestControlViewSet(BaseLoggedViewSet):
    serializer_class = RequestControlSerializer
    slug = 'request_log'

    def partial_update(self, request, pk):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        account = request_auth.get_account()
        worker = Worker.objects(pk=account.id).get()
        instance = Request.objects(
            Request.get_binds_query(binds),
            is_deleted__ne=True,
            pk=pk,
        ).get()
        serializer.validated_data['worker'] = account.id
        serializer.validated_data['worker_short_name'] = worker.short_name
        serializer.validated_data['position'] = worker.position.id
        serializer.validated_data['position_name'] = worker.position.name
        serializer.partial_update(instance, serializer.validated_data)
        return HttpResponse()


class TenantContactsUpdateViewSet(BaseLoggedViewSet):
    slug = 'request_log'

    def get_object(self, pk, binds):
        tenant = Tenant.objects(
            Tenant.get_binds_query(binds),
            pk=pk,
            _type__ne='OtherTenant',
        ).first()
        if not tenant:
            tenant = OtherTenant.objects(
                OtherTenant.get_binds_query(binds),
                pk=pk,
                _type='OtherTenant',
            ).first()
        return tenant

    @permission_validator
    def partial_update(self, request, pk):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        instance = self.get_object(pk, binds)
        if not instance:
            return HttpResponse()
        serializer = TenantRequestPhonesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('request'):
            requests = list(
                Request.objects(pk=serializer.validated_data['request']).all(),
            )
        else:
            requests = None
        instance.update_contacts(
            serializer.validated_data['phones'],
            serializer.validated_data.get('email'),
            denormalize_to=requests,
        )
        return JsonResponse(data=serializer.data)


class TenantRequestsInfoViewSet(BaseTenantInfoViewSet):
    slug = 'request_log'

    @staticmethod
    def make_query(*args, **kwargs):
        return get_tenant_requests_statistic(*args, **kwargs)
