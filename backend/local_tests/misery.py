from datetime import datetime
from pprint import pprint

from bson import ObjectId
from app.gis.tasks.house import archive_provider_meters, import_house_tenants, \
    import_provider_period_meters, export_provider_meters
from app.gis.services.house_management import HouseManagement
from app.gis.utils.meters import get_house_meters
from app.gis.utils.services import get_tariff_plan_services
from app.meters.models.meter import AreaMeter, Meter
from mongoengine_connections import register_mongoengine_connections
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual

register_mongoengine_connections()

provider_id = ObjectId('5a8ab85a60bdd000305f0ac5')

houses = get_binded_houses(provider_id)
# print(houses)

# houses = [ObjectId('642d7eac8a90b40037778cfb'),ObjectId('64f6c719af6d24001a82dc62')]
for house_id in houses:
    archive_provider_meters.delay(provider_id=provider_id, house_id=house_id, update_existing=True)



    area_meters, house_meters = get_house_meters(house_id, only_closed=True)
    _export = HouseManagement.exportMeteringDeviceData(provider_id, house_id)
    _export(*area_meters)







# export_provider_meters(provider_id, house_id, update_existing=True)

# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2025,1,1), date_till=datetime(2026,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2024,1,1), date_till=datetime(2025,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2023,1,1), date_till=datetime(2024,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2022,1,1), date_till=datetime(2023,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2021,1,1), date_till=datetime(2022,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2020,1,1), date_till=datetime(2021,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2019,1,1), date_till=datetime(2020,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2018,1,1), date_till=datetime(2019,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2017,1,1), date_till=datetime(2018,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2016,1,1), date_till=datetime(2017,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2015,1,1), date_till=datetime(2016,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2014,1,1), date_till=datetime(2015,2,1))
# import_provider_period_meters.delay(provider_id=provider_id, house_id=house_id,date_from=datetime(2013,1,1), date_till=datetime(2014,2,1))


# houses = [ObjectId('610012fe2b9e8b0013daed84')]

# tp_id = ObjectId('678c01b2769dbb371948a257')
# tariff_services: list = get_tariff_plan_services(tp_id)
# pprint('tariff_services')
# pprint(tariff_services)
#
# tpc = TariffPlanClient()
# tpp = '678c01b2769dbb371948a257'
# services = tpc.get_by_id(tpp).json()
# pprint('services')
# pprint(services)