from app.area.models.area import Area
from app.house.models.house import House
from processing.data_importers.gis.base import is_status_error, get_error_string
from processing.models.logging.gis_log import GisImportStatus
from .base import BaseGISDataImporter


class HousesPropertiesFields:
    ADDRESS = 'Адрес'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class HouseNonLivingAreasFields:
    ADDRESS = 'Адрес МКД, в котором расположено нежилое помещение'
    AREA_NUMBER = 'Номер помещения'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class HousePorchesFields:
    ADDRESS = 'Адрес МКД, в котором расположен подъезд'
    PORCH_NUMBER = 'Номер подъезда'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class HouseLivingAreasFields:
    ADDRESS = 'Адрес МКД, в котором расположено жилое помещение'
    AREA_NUMBER = 'Номер помещения'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class HouseRoomsFields:
    ADDRESS = 'Адрес МКД, в котором расположено жилое помещение'
    AREA_NUMBER = 'Номер помещения'
    ROOM_NUMBER = 'Номер комнаты'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class HousesDataImporter(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Характеристики МКД': {
            'entry_import_method': 'import_entry_house_properties',
            'title': 'Характеристики МКД',
            'start_row': 3,
            'columns': {
                HousesPropertiesFields.ADDRESS: 'A',
                HousesPropertiesFields.GIS_PROCESSING_STATUS: 'M',
            }
        },
        'Нежилые помещения': {
            'entry_import_method': 'import_entry_non_living_areas',
            'title': 'Нежилые помещения',
            'start_row': 3,
            'columns': {
                HouseNonLivingAreasFields.ADDRESS: 'A',
                HouseNonLivingAreasFields.AREA_NUMBER: 'B',
                HouseNonLivingAreasFields.GIS_PROCESSING_STATUS: 'G',
            }
        },
        'Подъезды': {
            'entry_import_method': 'import_entry_porches',
            'title': 'Подъезды',
            'start_row': 3,
            'columns': {
                HousePorchesFields.ADDRESS: 'A',
                HousePorchesFields.PORCH_NUMBER: 'B',
                HousePorchesFields.GIS_PROCESSING_STATUS: 'F',
            }
        },
        'Жилые помещения': {
            'entry_import_method': 'import_entry_living_areas',
            'title': 'Жилые помещения',
            'start_row': 3,
            'columns': {
                HouseLivingAreasFields.ADDRESS: 'A',
                HouseLivingAreasFields.AREA_NUMBER: 'B',
                HouseLivingAreasFields.GIS_PROCESSING_STATUS: 'I',
            }
        },
        'Комнаты': {
            'entry_import_method': 'import_entry_rooms',
            'title': 'Комнаты',
            'start_row': 3,
            'columns': {
                HouseRoomsFields.ADDRESS: 'A',
                HouseRoomsFields.AREA_NUMBER: 'B',
                HouseRoomsFields.ROOM_NUMBER: 'C',
                HouseRoomsFields.GIS_PROCESSING_STATUS: 'G',
            }
        },
    }

    def import_entry_house_properties(self, entry, import_task, links,
                                      ws_schema):
        house_address = entry[HousesPropertiesFields.ADDRESS]
        house = House.objects(address=house_address).first()

        if house:
            gis_processing_status = \
                entry[HousesPropertiesFields.GIS_PROCESSING_STATUS]

            # TODO добавить проверку полученного статуса на то, является ли он
            # уникальным номером ГИСа
            if not is_status_error(gis_processing_status):
                house.gis_uid = gis_processing_status
                house.save()

            status_log = GisImportStatus(
                status=gis_processing_status,
                task=import_task.parent.id,
            )
            if is_status_error(gis_processing_status):
                status_log.is_error = True
                status_log.description = get_error_string(gis_processing_status)
            status_log.save()

    def import_entry_non_living_areas(self, entry, import_task, links,
                                      ws_schema):
        house_address = entry[HouseNonLivingAreasFields.ADDRESS]
        house = House.objects(address=house_address).first()
        gis_processing_status = \
            entry[HouseNonLivingAreasFields.GIS_PROCESSING_STATUS]

        if house:
            non_living_area = Area.objects(
                _type='NotLivingArea',
                is_deleted__ne=True,
                house__id=house.id,
                str_number=entry[HouseNonLivingAreasFields.AREA_NUMBER]
            ).first()

            if non_living_area:

                # TODO добавить проверку полученного статуса на то, является ли
                # он уникальным номером ГИСа
                if not is_status_error(gis_processing_status):
                    non_living_area.gis_uid = gis_processing_status
                    non_living_area.save()

                status_log = GisImportStatus(
                    status=gis_processing_status,
                    task=import_task.parent.id,
                )
                if is_status_error(gis_processing_status):
                    status_log.is_error = True
                    status_log.description = get_error_string(
                        gis_processing_status)
                status_log.save()

    def import_entry_porches(self, entry, import_task, links, ws_schema):
        house_address = entry[HousePorchesFields.ADDRESS]
        house = House.objects(address=house_address).first()

        gis_processing_status = \
            entry[HousesPropertiesFields.GIS_PROCESSING_STATUS]

        if house:
            porches_by_number = [
                porch for porch in house.porches
                if porch.number == HousePorchesFields.PORCH_NUMBER
            ]

            for porch in porches_by_number[0] if porches_by_number else []:
                status_log = GisImportStatus(
                    status=gis_processing_status,
                    task=import_task.parent.id,
                )
                if is_status_error(gis_processing_status):
                    status_log.is_error = True
                    status_log.description = get_error_string(
                        gis_processing_status)
                status_log.save()

    def import_entry_living_areas(self, entry, import_task, links, ws_schema):
        house_address = entry[HouseLivingAreasFields.ADDRESS]
        house = House.objects(
            address=house_address,
            service_binds__provider=import_task.provider.id
        ).first()

        gis_processing_status = \
            entry[HouseLivingAreasFields.GIS_PROCESSING_STATUS]

        if house:
            living_area = Area.objects(
                _type='LivingArea',
                is_deleted__ne=True,
                house__id=house.id,
                str_number=entry[HouseLivingAreasFields.AREA_NUMBER]
            ).first()

            if living_area:
                # TODO добавить проверку полученного статуса на то, является ли
                # он уникальным номером ГИСа
                if not is_status_error(gis_processing_status):
                    living_area.gis_uid = gis_processing_status
                    living_area.save()

                status_log = GisImportStatus(
                    status=gis_processing_status,
                    task=import_task.parent.id,
                )
                if is_status_error(gis_processing_status):
                    status_log.is_error = True
                    status_log.description = get_error_string(
                        gis_processing_status)
                status_log.save()

    def import_entry_rooms(self, entry, import_task, links, ws_schema):
        house_address = entry[HouseRoomsFields.ADDRESS]
        house = House.objects(address=house_address).first()

        gis_processing_status = entry[HouseRoomsFields.GIS_PROCESSING_STATUS]

        if house:
            area = Area.objects(
                _type='LivingArea',
                is_deleted__ne=True,
                house__id=house.id,
                str_number=entry[HouseRoomsFields.AREA_NUMBER]
            ).first()

            if area:
                rooms = [
                    room for room in area.rooms
                    if room.number == entry[HouseRoomsFields.ROOM_NUMBER]
                ]
                if rooms:
                    room = rooms[0]
                    # TODO добавить проверку полученного статуса на то,
                    # является ли он уникальным номером ГИСа
                    if not is_status_error(gis_processing_status):
                        room.gis_uid = gis_processing_status
                        area.save()
                    status_log = GisImportStatus(
                        status=gis_processing_status,
                        task=import_task.parent.id,
                    )
                    if is_status_error(gis_processing_status):
                        status_log.is_error = True
                        status_log.description = get_error_string(
                            gis_processing_status)
                    status_log.save()

