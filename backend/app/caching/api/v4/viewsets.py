from datetime import datetime

from api.v4.authentication import RequestAuth
from api.v4.serializers import PrimaryKeySerializer
from app.caching.core.accounts_filter import filter_accounts
from api.v4.viewsets import BaseLoggedViewSet
from app.caching.api.v4.serializers import AccrualFilterSerializer
from app.caching.models.filters import FilterCache
from app.caching.tasks.cache_update import prepare_filter_cache
from processing.models.billing.accrual import Accrual
from processing.models.billing.account import Tenant
from processing.models.choices import FilterPurpose


class AccrualFilterViewSet(BaseLoggedViewSet):
    def create(self, request):
        serializer = AccrualFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        house_id = serializer.validated_data['house']
        del serializer.validated_data['house']
        request_auth = RequestAuth(request)
        binds = request_auth.get_binds()
        filtered_accounts = filter_accounts(
            accounts_ids=None,
            house_id=house_id,
            filter_params=serializer.validated_data,
            binds=binds,
        )
        filtered_accounts = [x.get('_id') for x in filtered_accounts]
        if serializer.validated_data.get('accrual_doc'):
            filtered_accounts = self._cut_by_accruals(
                filtered_accounts,
                serializer.validated_data.get('accrual_doc'),
            )
        purpose = serializer.validated_data.get('purpose')
        if purpose == FilterPurpose.ACCRUAL_DOC_VIEW:
            extra_keys = {
                'doc_id': serializer.validated_data.get('accrual_doc'),
            }
        else:
            purpose = ''
            extra_keys = {}
        request_auth = RequestAuth(request)
        filter_cache = FilterCache(
            provider=request_auth.get_provider_id(),
            objs=filtered_accounts,
            purpose=purpose,
            extra=extra_keys,
            used=datetime.now(),
        )
        filter_cache.save()
        if purpose:
            prepare_filter_cache.delay(filter_cache.pk)
        return self.json_response(
            {
                'filter_id': filter_cache.pk,
                'count': len(filtered_accounts),
            },
        )

    def retrieve(self, request, pk):
        filter_id = PrimaryKeySerializer.get_validated_pk(pk)
        filter_cache = FilterCache.objects(pk=filter_id).get()
        request_auth = RequestAuth(request)
        binds = request_auth.get_binds()
        tenants = Tenant.objects(
            Tenant.get_binds_query(binds),
            pk__in=filter_cache.objs,
        ).distinct('id')
        return self.json_response(data={'results': tenants})

    @staticmethod
    def _cut_by_accruals(accounts, accrual_doc_id):
        return Accrual.objects(
            doc__id=accrual_doc_id,
            account__id__in=accounts,
        ).distinct(
            'account.id',
        )
