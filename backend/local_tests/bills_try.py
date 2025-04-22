from datetime import datetime
from pprint import pprint

from bson import ObjectId

from app.gis.services.bills import Bills
from app.gis.utils.services import get_services_tree
from app.personnel.models.personnel import Worker
from mongoengine_connections import register_mongoengine_connections


register_mongoengine_connections()

# service_tree = get_services_tree()
# pprint('service_tree1')
# print(service_tree)

provider_id = ObjectId('526234b4e0e34c474382225d')
house_id = ObjectId('56828afa65939b0021710d36')
period = datetime(2025,1,1)
# period = datetime(2025,2,1)
# period = datetime(2025,3,1)
# period = datetime(2025,4,1)

Bills.importPaymentDocumentData(
    provider_id, house_id
).periodic(period)  # начисления за период