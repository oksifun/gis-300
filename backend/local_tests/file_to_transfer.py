from datetime import datetime

from bson import ObjectId

from app.gis.services.house_management import HouseManagement
from app.gis.tasks.house import import_provider_period_meters, archive_provider_meters
from app.gis.utils.meters import get_house_meters
from mongoengine_connections import register_mongoengine_connections

register_mongoengine_connections()

provider_id = ObjectId('526234b4e0e34c47438221bc')
houses = [ObjectId('563a633bd9e1db001a0dcaf0'), ObjectId('61362415baa407000c7a367b'), ObjectId('6136241bbaa40700117d2a5f')]

for house_id in houses:
    archive_provider_meters.delay(provider_id=provider_id, house_id=house_id, update_existing=True)

    area_meters, house_meters = get_house_meters(house_id, only_closed=True)
    _export = HouseManagement.exportMeteringDeviceData(provider_id, house_id)
    _export(*area_meters)
