import datetime

from bson import ObjectId
from mongoengine_connections import register_mongoengine_connections
from app.accruals.cipca.source_data.meters import get_meters
from app.area.models.area import Area


if __name__ == '__main__':
    register_mongoengine_connections()
    month = datetime.datetime(2018, 4, 1)
    mm = get_meters(
        Area.objects(__raw__={'house._id': ObjectId("589bf14df2f7b0004e11536c")}),
        month
    )
    print(mm)

