from bson import ObjectId

from app.meters.models.meter import AreaMeter
from app.area.models.area import Area
from processing.models.billing.account import Tenant
from processing.models.billing.area_bind import AreaBind
from app.admin.core.data_restore.base import DataRestore
from processing.models.billing.responsibility import Responsibility


class AreaDataRestore(DataRestore):
    _PIPELINE = [
        (Area, '_id'),
        (Tenant, 'area._id'),
        (AreaMeter, 'area._id'),
        (AreaBind, 'area'),
        (Responsibility, 'account.area._id'),
    ]


def restore_area_data(area_id, batch_size=None, host='10.1.1.221', logger=None):
    restorer = AreaDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(area_id))
