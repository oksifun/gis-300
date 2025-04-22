from datetime import datetime

from bson import ObjectId

from app.gis.services.bills import Bills

from mongoengine_connections import register_mongoengine_connections

register_mongoengine_connections()

provider_id = ObjectId('526234b4e0e34c4743822194')
house_id = ObjectId('5a7992ac5496870017fd3972')
period = datetime(2025, 1, 1)

_import = Bills.importPaymentDocumentData(
    provider_id=provider_id,
    house_id=house_id,
    # request_only=True
)

_import.periodic(period)  # начисления за период

