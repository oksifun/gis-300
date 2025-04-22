from bson import ObjectId

from app.personnel.models.department import Department
from app.personnel.models.personnel import Worker
from processing.models.billing.provider.main import Provider
from app.admin.core.data_restore.base import DataRestore


class ProviderPersonnelDataRestore(DataRestore):
    _PIPELINE = [
        (Provider, '_id'),
        (Department, 'provider'),
        (Worker, 'provider._id'),
    ]


def restore_provider_personnel_data(provider_id, batch_size=None,
                                    host='10.1.1.221', logger=None):
    restorer = ProviderPersonnelDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(provider_id))
