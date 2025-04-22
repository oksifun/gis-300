from bson import ObjectId

from app.gis.services.house_management import HouseManagement
from processing.models.billing.provider.main import BankProvider

from app.gis.tasks.house import export_specific_tenants
from mongoengine_connections import register_mongoengine_connections


register_mongoengine_connections()

provider_id = ObjectId('526234b3e0e34c4743821fbd')
house_id = ObjectId('576bfd470ce661001f316d16')
tenant_ids = [
    # ObjectId('576c14bd64b8590001202fed'),
    # ObjectId('576c14bd64b8590001202ff9'),
    # ObjectId('576c14be64b8590001203000'),
    # ObjectId('6671a54771f42a37944731a1'),
    # ObjectId('67d9a033557a85906684a142'),

    ObjectId('5d0fc654ef9c310042f8b143'),
    ObjectId('5d2efc059d89ec005063f420'),
    # ObjectId('5d2efbf003a0ac002e6a7177'),
]

# export_specific_tenants(provider_id, house_id, *tenant_ids, request_only=True, update_existing=True)

_export = HouseManagement.importAccountData(provider_id, house_id, update_existing=True)
_export(*tenant_ids)  # по всем направлениям платежа (начислений)