from bson import ObjectId

from app.meters.models.meter import HouseMeter, AreaMeter
from processing.data_producers.associated.base import get_binded_houses
from app.house.models.house import House
from app.area.models.area import Area
from processing.models.billing.account import Tenant
from processing.models.billing.house_group import HouseGroup
from app.admin.core.data_restore.base import DataRestore
from processing.models.billing.responsibility import Responsibility


class HouseDataRestore(DataRestore):
    _PIPELINE = [
        (House, '_id'),
        (HouseMeter, 'house._id'),
        (Area, 'house._id'),
        (Tenant, 'area.house._id'),
        (Responsibility, 'account.area.house._id'),
        (AreaMeter, 'area.house._id'),
    ]


class HouseGroupsDataRestore(DataRestore):
    _PIPELINE = [
        (HouseGroup, 'provider'),
    ]


def restore_house_data(house_id, batch_size=None, host='10.1.1.221'):
    restorer = HouseDataRestore(
        host,
        batch_size=batch_size,
    )
    restorer.restore_data(ObjectId(house_id))


def restore_provider_houses_data(provider_id, batch_size=None,
                                 host='10.1.1.221', logger=None):
    restorer = HouseGroupsDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(provider_id))
    restorer = HouseDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    houses = get_binded_houses(ObjectId(provider_id))
    for house in houses:
        print(house)
        restorer.restore_data(house)
