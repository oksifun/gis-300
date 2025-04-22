from bson import ObjectId

from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment, PaymentDoc
from app.offsets.models.offset import Offset
from app.accruals.models.accrual_document import AccrualDoc
from app.offsets.models.reversal import Reversal
from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.service_type import ServiceType
from processing.models.billing.settings import ProviderAccrualSettings
from app.admin.core.data_restore.base import DataRestore


class ProviderFinDataRestore(DataRestore):
    _PIPELINE = [
        (AccrualDoc, 'sector_binds.provider'),
        (PaymentDoc, 'provider'),
        (TariffPlan, 'provider'),
        (ServiceType, 'provider'),
        (ProviderAccrualSettings, 'provider'),
        (Accrual, 'owner'),
        (Payment, 'doc.provider'),
        (Offset, 'refer.doc.provider'),
        (Reversal, 'owner'),
    ]


class AccountFinDataRestore(DataRestore):
    _PIPELINE = [
        (Accrual, 'account._id'),
        (Payment, 'account._id'),
        (Offset, 'refer.account._id'),
    ]


class HouseFinDataRestore(DataRestore):
    _PIPELINE = [
        (Accrual, 'account.area.house._id'),
        (Payment, 'account.area.house._id'),
        (Offset, 'refer.account.area.house._id'),
        (AccrualDoc, 'house._id'),
    ]


def restore_offsets_by_provider(provider_id, batch_size=None,
                                host='10.1.1.221', logger=None,
                                pipline_ix=None):
    restorer = ProviderFinDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    if pipline_ix is None:
        restorer.restore_data(provider_id)
    else:
        restorer.restore_by_pipeline_ix(pipline_ix, provider_id)


def restore_offsets_by_account(account_id, batch_size=None,
                               host='10.1.1.221', logger=None):
    restorer = AccountFinDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(account_id))


def restore_offsets_by_house(house_id, batch_size=None,
                             host='10.1.1.221', logger=None):
    restorer = HouseFinDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(house_id))
