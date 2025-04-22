from bson import ObjectId
from mongoengine import DoesNotExist

from processing.models.billing.account import Account
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.payment import Payment
from processing.models.billing.provider.main import Provider
from processing.models.billing.area_bind import AreaBind
from processing.models.billing.payment import PaymentDoc
from app.caching.models.current_tariffs_tree import TariffsFolder
from app.caching.models.filters import FilterCache


class Permissions:

    def __init__(self, provider, actor=None):
        if isinstance(provider, ObjectId):
            self.provider = Provider.objects.get(id=provider)
        else:
            self.provider = provider
        self.actor = actor
        self._area_binds = None
        self._cached_areas = None

    @classmethod
    def get_area_binds(cls, provider_id, areas_list_in=None):
        if areas_list_in is None:
            return AreaBind.objects.filter(
                provider=provider_id,
                closed=None
            ).distinct('area')
        else:
            return AreaBind.objects.filter(
                provider=provider_id,
                area__in=areas_list_in,
                closed=None
            ).distinct('area')

    def cut_areas_list(self, source_list, area_id_key='area_id'):
        a_list = [a[area_id_key] for a in source_list]
        if self._cached_areas is not None and (set(a_list) - self._cached_areas):
            self._area_binds = None
        if self._area_binds is None:
            self._cached_areas = set(a_list)
            self._area_binds = self._get_area_binds(a_list)
        return [a for a in source_list if a[area_id_key] in self._area_binds]

    def _get_area_binds(self, areas_list_in=None):
        return self.get_area_binds(self.provider.id, areas_list_in)

    @classmethod
    def check_account_permissions(cls, provider_id, account_id):
        account = Account.objects.as_pymongo().get(id=account_id)
        try:
            area_bind = AreaBind.objects.as_pymongo().get(
                provider=provider_id,
                area=account['area']['_id'],
                closed=None
            )
        except DoesNotExist:
            return False
        return area_bind is not None

    @classmethod
    def check_accounts_permissions(cls, provider_id, accounts_ids):
        areas = Account.objects.as_pymongo().filter(
            id__in=accounts_ids).distinct('area._id')
        area_binds = AreaBind.objects.as_pymongo().filter(
            provider=provider_id,
            area__in=areas,
            closed=None
        ).distinct('area')
        return len(areas) == len(area_binds)

    @classmethod
    def cut_accounts_by_permissions(cls, provider_id, accounts_ids):
        accounts = Account.objects.as_pymongo().filter(
            id__in=accounts_ids).only('id', 'area._id')
        area_binds = AreaBind.objects.as_pymongo().filter(
            provider=provider_id,
            area__in=[a['area']['_id'] for a in accounts],
            closed=None
        ).distinct('area')
        return [a['_id'] for a in accounts if a['area']['_id'] in area_binds]

    @classmethod
    def check_accrual_permissions(cls, provider_id, accrual_id=None, doc_id=None):
        try:
            if accrual_id:
                accrual = Accrual.objects.as_pymongo().get(
                    id=accrual_id,
                    owner=provider_id,
                )
            else:
                accrual = AccrualDoc.objects(
                    __raw__={
                        '_id': doc_id,
                        '$or': [
                            {'provider': provider_id},
                            {'sector_binds.provider': provider_id},
                        ],
                    },
                ).as_pymongo().first()
        except DoesNotExist:
            return False
        return accrual is not None

    @classmethod
    def check_payment_permissions(cls, provider_id, payment_id=None,
                                  doc_id=None):
        try:
            if payment_id:
                payment = Payment.objects.as_pymongo().get(
                    id=payment_id,
                    doc__provider=provider_id,
                )
            else:
                payment = PaymentDoc.objects(
                    id=doc_id,
                    provider=provider_id,
                ).as_pymongo().first()
        except DoesNotExist:
            return False
        return payment is not None

    @classmethod
    def check_payment_docs_permissions(cls, provider_id, doc_ids):
        docs = PaymentDoc.objects.as_pymongo().filter(
            id__in=doc_ids,
            provider=provider_id,
        ).distinct('_id')
        return len(doc_ids) == len(docs)

    @classmethod
    def check_tariffs_folder_permissions(cls, provider_id, folder_id):
        try:
            folder = TariffsFolder.objects.as_pymongo().get(
                folder_id=folder_id,
                provider=provider_id,
            )
        except DoesNotExist:
            return False
        return folder is not None

    @classmethod
    def check_filter_permissions(cls, provider_id, filter_id):
        try:
            folder = FilterCache.objects.as_pymongo().get(
                pk=filter_id,
                provider=provider_id,
            )
        except DoesNotExist:
            return False
        return folder is not None

