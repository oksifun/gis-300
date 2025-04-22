from bson import ObjectId
from dateutil.relativedelta import relativedelta
from rest_framework.exceptions import ValidationError, NotFound

from api.v4.serializers import PrimaryKeySerializer
from app.tenants.api.v4.serializers import (
    TenantCoefficientImportSerializer, _IMPORT_READINGS_FILE_EXTENSIONS,
    TenantListCoefficientSerializer, TenantCoefficientSerializer,
    TenantCoefficientsSerializer
)
from app.tenants.tasks.update_tenants_coefs import (
    update_tenants, TENANTS_COEFS_HEADER
)
from lib.gridfs import put_file_to_gridfs
from processing.data_producers.associated.tenants import \
    get_responsibles_by_house
from processing.data_producers.forms.tenant import (
    tenant_is_archive, get_tenant_coefs_on_date
)
from rest_framework.response import Response

from api.v4.authentication import RequestAuth
from api.v4.utils import permission_validator
from api.v4.viewsets import BaseLoggedViewSet
from processing.models.billing.account import Tenant
from processing.models.billing.coefficient import Coefficient
from processing.models.billing.account import CoefReason, Coef


class TenantCoefficientMixin:
    @staticmethod
    def get_coefs(binds, coef_id):
        coefs = Coefficient.objects(
            Coefficient.get_binds_query(binds), id=coef_id
        ).as_pymongo()
        return {x['_id']: x for x in coefs}


class TenantCoefficientImportViewSet(BaseLoggedViewSet, TenantCoefficientMixin):
    """
    Квартирные коэффициенты: импорт из csv.
    """
    slug = 'tenants'

    @permission_validator
    def create(self, request):
        serializer = TenantCoefficientImportSerializer(data=request.data)
        auth = RequestAuth(request)
        binds, provider, account = \
            auth.get_binds(), auth.get_provider_id(), auth.get_super_account()
        data = serializer.validated_data
        file, coef_id, period = data['file'], data['coef'], data['period']
        self._check_file_extension(file)
        coefs = self.get_coefs(binds, coef_id)
        if not coefs:
            raise ValidationError('Нет такого коэффициента.')
        file_id, _ = put_file_to_gridfs(
            'TenantCoefficient', account.id, file.read(), filename=file.name,
        )
        update_tenants.delay(
            file_id, provider, coef_id, coefs, period, account.id, file.name
        )
        return self.json_response(dict(results='running...'))

    @staticmethod
    def _check_file_extension(file):
        try:
            extension = file.name.split('.')[-1] or None
            if extension not in _IMPORT_READINGS_FILE_EXTENSIONS:
                raise ValidationError('Неизвестный тип файла')
        except Exception:
            raise ValidationError('Неизвестный тип файла')


class TenantCoefficientViewSet(BaseLoggedViewSet, TenantCoefficientMixin):
    """
    Квартирные коэффициенты: экспорт в csv, получение csv-файла,
    общий список, патч коэффициента жителя.
    """
    slug = 'tenants'

    @permission_validator
    def create(self, request):
        """Экспорт в csv."""
        serializer = TenantListCoefficientSerializer(data=request.data)
        auth = RequestAuth(request)
        binds, provider = auth.get_binds(), auth.get_provider_id()
        data = serializer.validated_data
        coef_id, date, house, show_null = \
            data['coef'], data['date'], data['house'], data['show_null']
        coefs = self.get_coefs(binds, coef_id)
        if not coefs:
            raise NotFound('Нет такого коэффициента.')
        title = coefs[coef_id]['title']
        tenants = self._get_tenants_coefficients(
            binds=binds,
            provider_id=provider,
            date=date,
            house=house,
            coefs=coefs
        )
        if not tenants:
            raise NotFound('Жителей не найдено.')
        csv_data = self._get_csv_data(tenants, show_null)
        file = '\n'.join(csv_data).encode('cp1251')
        filename = f"{title}_{date.year}{date.month}.csv"
        file_id, uuid = put_file_to_gridfs(
            resource_name=None,
            resource_id=None,
            file_bytes=file,
            filename=filename,
        )
        return self.json_response(dict(results=file_id))

    @permission_validator
    def retrieve(self, request, pk):
        """Получение csv-файла."""
        return super().file_response(ObjectId(pk), clear=True)

    @permission_validator
    def list(self, request):
        """Общий список."""
        serializer = TenantListCoefficientSerializer(data=request.query_params)
        auth = RequestAuth(request)
        binds = auth.get_binds()
        provider = auth.get_provider_id()
        account = auth.get_super_account()
        data = serializer.validated_data
        coefs = self.get_coefs(binds, data['coef'])
        results = self._get_tenants_coefficients(
            binds=binds,
            provider_id=provider,
            date=data['date'],
            house=data['house'],
            coefs=coefs
        )
        return self.json_response(dict(results=results))

    @permission_validator
    def partial_update(self, request, pk):
        """Патч коэффициента жителя."""
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        serializer = TenantCoefficientSerializer(data=request.data)
        self._save_coefficient_to_tenant(pk, **serializer.validated_data)
        return Response()

    def _get_tenants_coefficients(self, binds, provider_id, date, house, coefs):
        tenants = self._get_tenants_by_house(house, binds, provider_id, date)
        self._add_extra_to_tenants(tenants, coefs, date)
        return sorted(tenants, key=lambda x: x['area']['order'])

    @staticmethod
    def _get_csv_data(tenants, show_null):
        data = [';'.join(TENANTS_COEFS_HEADER)]
        for tenant in tenants:
            coef = tenant['current_coefs'][0]
            if not show_null and not float(coef['value']):
                continue
            value = str(float(coef['value'])).replace('.', ',')
            reason = coef.get('reason')
            if reason:
                reason_csv = f"{reason.get('number', '') or ''};" \
                             f"{str(reason.get('datetime', '')) or ''};" \
                             f"{reason.get('comment', '') or ''}"
            else:
                reason_csv = ";;"
            data.append(
                f"{tenant['area']['str_number']};"
                f"{tenant['short_name']};"
                f"{value};"
                f"{reason_csv};"
                f"{tenant['area']['house']['address']}"
            )
        return data

    @staticmethod
    def _save_coefficient_to_tenant(tenant, coef, period, value, reason):
        tenant = Tenant.objects.get(pk=tenant)
        for cf in tenant.coefs:
            if cf.coef == coef and cf.period == period:
                cf.value = value
                if reason:
                    cf.reason = CoefReason(**reason)
                tenant.save()
                return

        tenant.coefs.append(
            Coef(
                coef=coef,
                period=period,
                value=value,
                reason=CoefReason(**reason)
            )
        )
        tenant.save()

    def _get_tenants_by_house(self, house_id, binds, provider_id, date):
        date_on = date
        date_till = date_on + relativedelta(months=1)
        responsible = get_responsibles_by_house(provider_id,
                                                house_id,
                                                date_on,
                                                date_till)
        tenants = Tenant.objects(
            Tenant.get_binds_query(binds),
            area__house__id=house_id,
            id__in=responsible,
            _type__ne='OtherTenant',
            is_deleted__ne=True
        ).only(
            'id',
            'area.str_number',
            'area.order',
            'area.str_number_full',
            'area.house.address',
            'short_name',
            'coefs',
            'statuses',
            '_type'
        ).as_pymongo()
        return tenants

    @staticmethod
    def _filter_archive_tenants(tenants, dtn):
        for tenant in tenants:
            if not tenant_is_archive(tenant, dtn):
                del tenant['statuses']
                yield tenant

    @staticmethod
    def _add_extra_to_tenants(tenants, coefs, date):
        for tenant in tenants:
            tenant_coefs = get_tenant_coefs_on_date(tenant, coefs, date)
            for cf in coefs.values():
                if cf['_id'] not in tenant_coefs:
                    tenant_coefs[cf['_id']] = {
                        'coef': cf['_id'],
                        'value': cf['default'],
                        # 'title': cf['title'],
                    }
            tenant['current_coefs'] = list(tenant_coefs.values())
            try:
                del tenant['coefs']
            except KeyError:
                pass


class TenantCoefficientsViewSet(BaseLoggedViewSet):
    """
    Квартирные коэффициенты жителя - список
    """
    slug = 'tenants'

    @permission_validator
    def list(self, request):
        """Общий список."""
        serializer = TenantCoefficientsSerializer(data=request.query_params)
        auth = RequestAuth(request)
        binds = auth.get_binds()
        serializer.is_valid(raise_exception=True)
        tenant = Tenant.objects(
            Tenant.get_binds_query(binds),
            pk=serializer.validated_data['tenant'],
        ).get()
        results = self._get_coefs_titles_dict(tenant, binds)
        self._update_coefs_by_tenant_values(
            results,
            tenant,
            serializer.validated_data['month'],
        )
        return self.json_response(
            {
                'results': sorted(
                    list(results.values()),
                    key=lambda i: i['title'],
                ),
            },
        )

    @staticmethod
    def _get_coefs_titles_dict(tenant, binds):
        coef_ids = {c.coef for c in tenant.coefs}
        coefs = Coefficient.objects(
            Coefficient.get_binds_query(binds),
            pk__in=coef_ids,
        ).only(
            'id',
            'title',
            'is_once',
            'is_feat',
            'default',
        ).as_pymongo()
        return {c['_id']: c for c in coefs}

    @staticmethod
    def _update_coefs_by_tenant_values(coefs_dict, tenant, month):
        for coef in coefs_dict.values():
            coef['value'] = coef.pop('default')
            coef['reason'] = None
        sorted_coefs = sorted(
            tenant.coefs,
            key=lambda i: i.period,
        )
        for coef in sorted_coefs:
            if coef.coef not in coefs_dict:
                continue
            if coefs_dict[coef.coef].get('is_once'):
                if coef.period == month and coef.reason is not None:
                    coefs_dict[coef.coef]['value'] = coef.value
                    coefs_dict[coef.coef]['reason'] = coef.reason.to_mongo()
            else:
                if coef.period <= month and coef.reason is not None:
                    coefs_dict[coef.coef]['value'] = coef.value
                    coefs_dict[coef.coef]['reason'] = coef.reason.to_mongo()
