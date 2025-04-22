

from app.gis.models.gis_record import GisRecord
from app.gis.services.house_management import HouseManagement
from app.gis.tasks.bills import import_pd

from app.gis.utils.meters import get_house_meters
from app.meters.models.meter import AreaMeter, HouseMeter



# region ДАННЫЕ METER_DATA
# record = GisRecord.objects.get(pk=ObjectId('6746cbfd829027000d43ccd5'))
# # provider_id = record.provider_id
# # house_id = record.house_id
# object_ids = record.object_ids
# # period = record.period
#
# provider_id = ObjectId('526234b3e0e34c4743821fbd')
# house_id = ObjectId('576bfd470ce661001f316d16')
# # object_ids = [ObjectId('6746c771bfa41fb6af94b36b')]
# period = datetime(2024, 10, 1)
# # endregion ДАННЫЕ METER_DATA
#
#
# _import = HouseManagement.importMeteringDeviceData(  # выгружаем
#     provider_id, house_id,  # приборы учета
#     # request_only=True,
#     # update_existing=True  # отсутствующие (без идентификаторов)
# )
# _import(*object_ids)


from bson import ObjectId
from mongoengine_connections import register_mongoengine_connections
register_mongoengine_connections()
from datetime import datetime

# # import_provider_meters(
# #     provider_id,
# #     house_id,
# #     # request_only=True
# # )
# #
from bson import ObjectId
provider_id = ObjectId('526234b3e0e34c4743822028')
houses = [ObjectId('60eeb0a2ddbb1d005353d183'), ObjectId('61642e92fc812200133b72f7'), ObjectId('61e004303ac2a20012b2be7b'), ObjectId('6229e29b5bf792001a4a1767'), ObjectId('6229e2f9087c91001901c682'), ObjectId('625441174d197f001897b4e9'), ObjectId('62c7ef86d4fcb2001a09d9b3'), ObjectId('631713c9a29fdd001161002e'), ObjectId('6424121e7da2fb00336ba5de'), ObjectId('64461d2769a1a20038bce10e'), ObjectId('647f489c672c1e001a519d89'), ObjectId('64db6f40c9e68500188aa626'), ObjectId('655dfb4910d5330013357f74'), ObjectId('65bbb0ece2e69b860b8df4f9'), ObjectId('65dc599ffadf38e2fa2acdd3'), ObjectId('65ddcf45f9800932640b6b4e'), ObjectId('66471fac8e79e2f146a6d708'), ObjectId('66ac8c4b007512bb5691a08c'), ObjectId('66f12b0e4e92ec6ed13f9a51'), ObjectId('66f1741e30ee758713011119')]

for house_id in houses:
    # archive_provider_meters.delay(provider_id=provider_id, house_id=house_id, update_existing=True)


    area_meters, house_meters = get_house_meters(house_id, only_closed=True)

    _export = HouseManagement.exportMeteringDeviceData(provider_id, house_id)
# _export.house_meters()  # загружаем данные ПУ (помещений) дома операции
    _export(*area_meters)


# from app.gis.tasks.house import import_provider_period_meters

#
# register_mongoengine_connections()
#
# provider_id = ObjectId('5bbccde8d7e0e8001e13fb26')
# house_id = ObjectId('5e73350ea4ae5e000fb3cf02')
# date_from= datetime(2019,1,1)
# date_till= datetime(2020,1,1)
#
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id, date_from=date_from, date_till=date_till)


# provider_id = ObjectId('526234b3e0e34c4743821fbd')
# house_id = ObjectId('576bfd470ce661001f316d16')
# period = datetime(2024,11,1)
#
# import_pd(provider_id, house_id, period, request_onl=True)


from bson import ObjectId
from app.gis.tasks.house import import_house_tenants
from mongoengine_connections import register_mongoengine_connections


register_mongoengine_connections()

provider_id = ObjectId('526234b3e0e34c4743821fac')
houses = [ObjectId('610012fe2b9e8b0013daed84')]
for house_id in houses:
    import_house_tenants.delay(provider_id, house_id)