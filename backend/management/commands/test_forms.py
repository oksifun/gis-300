import datetime

from bson import ObjectId

from mongoengine_connections import register_mongoengine_connections
from processing.data_producers.export.privilege import AccrualsExport


if __name__ == '__main__':
    register_mongoengine_connections()
    ex = AccrualsExport(
        ObjectId("54d9e6e4f3b7d439807a2de1"),
        datetime.datetime(2018, 7, 1),
        ['rent'],
        'Целина'
    )
    result = ex.export()
    print(result)

