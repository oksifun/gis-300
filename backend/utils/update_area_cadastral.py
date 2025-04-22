import pymongo
from mongoengine.base.datastructures import BaseDict, BaseList

from app.area.models.area import Area
from utils.get_areas_cadastr import AreasCadastralInfo


def update_areas_cn():

    area_count = 0
    area_skipped = 0
    area_applied = 0

    while True:

        areas = AreasCadastralInfo.objects(address_data__objectCn__ne=None)

        try:

            for area_cn_data in areas:

                area = Area.objects.get(id=area_cn_data['area'])

                if not area.cadastral_number:

                    if isinstance(area_cn_data.address_data, BaseDict):
                        area.cadastral_number = area_cn_data.address_data[
                            'objectCn']
                    elif isinstance(area_cn_data.address_data, BaseList):
                        area.cadastral_number = area_cn_data.address_data[0][
                            'objectCn']

                    area_applied += 1
                    area.save()

                else:

                    area_skipped += 1

                area_count += 1
                if area_count % 10000 == 0:
                    print('areas processed: ' + str(area_count))
                    print('\tareas applied: ' + str(area_applied))
                    print('\tareas skipped: ' + str(area_skipped))
                    print()

            break

        except pymongo.errors.CursorNotFound:
            print('Mongo cursor revive: ' + str(area_count))
            areas = AreasCadastralInfo.objects(address_data__exists=True)[
                area_count:]


if __name__ == '__main__':
    update_areas_cn()



