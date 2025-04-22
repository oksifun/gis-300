from bson import ObjectId

from app.house.models.house import House
from app.area.models.area import Area, AreaEmbeddedRoom

from app.gis.models.guid import GUID
from app.gis.models.choices import GisObjectType

from processing.models.logging.gis_log import GisImportStatus
from processing.data_importers.gis.base import BaseGISDataImporter
from processing.models.tasks.gis.base import GisBaseImportTask


class AreasFields:
    HOUSE_GUID = 'HOUSEGUID (Идентификационный код дома в ГИС ЖКХ)'
    FIAS = 'HOUSEGUID (Глобальный уникальный идентификатор дома по ФИАС)'
    FIAS_PARENT = 'AOGUID (Идентификационный код родительского объекта в ФИАС/ГИС ЖКХ)'
    LIVING_AREA_NUMBER = 'Номер жилого помещения'
    NOT_LIVING_AREA_NUMBER = 'Номер нежилого помещения'
    ROOM_NUMBER = 'Номер комнаты'
    HOUSE_UID = 'Уникальный номер дома'
    AREA_UID = 'Уникальный номер помещения'
    ROOM_UID = 'Уникальный номер комнаты'
    CADASTRAL_NUMBER = 'Кадастровый номер'
    GIS_GUID = 'Глобальный уникальный идентификатор объекта жилищного фонда'
    ANNULMENT_DATE = 'Дата аннулирования объекта'
    DEMOLISH_DATE = 'Дата сноса объекта'


class Storage:

    _instances: dict = {}

    def __new__(cls, fias_guid: str, provider_id: ObjectId):  # singleton

        if fias_guid in cls._instances:
            return cls._instances[fias_guid]

        cls._instances[fias_guid] = instance = super().__new__(cls)
        instance.provider_id = provider_id

        # print('LOADING FIAS', fias_guid, 'HOUSE DATA...', 'PLEASE WAIT!')
        house: House = House.objects(__raw__={'$or':[
            {'fias_house_guid': fias_guid},
            {'gis_fias': fias_guid},
        ], 'is_deleted': {'$ne': True},
        }).first()
        instance.house = house  # или None

        if house is None:
            return instance
        elif provider_id not in house.provider_binds(
            is_active=True, is_started=True, is_not_finished=True
        ):
            instance.house = None
            return instance

        instance.house_guid = GUID.objects(__raw__={
            'tag': GisObjectType.HOUSE,
            'object_id': house.id,  # без provider_id
        }).first()  # или None

        # print('LOADING PROVIDER', provider_id,
        #     'HOUSE', house.id, 'AREAS DATA...', 'PLEASE WAIT!')
        instance.living_areas = {area['str_number']: area
            for area in Area.objects(__raw__={
                'house._id': house.id,
                '_type': 'LivingArea',
                'is_deleted': {'$ne': True},
            })}  # без only - подлежит сохранению
        instance.not_living_areas = {area['str_number']: area
            for area in Area.objects(__raw__={
                'house._id': house.id,
                '_type': 'NotLivingArea',
                'is_deleted': {'$ne': True},
            })}  # без only - подлежит сохранению

        area_ids: list = [area.id for area in instance.living_areas.values()] \
            + [area.id for area in instance.not_living_areas.values()]

        # print('LOADING', len(area_ids),
        #     'AREA GUIDS DATA...', 'PLEASE WAIT!')
        instance.area_guids = {guid['object_id']: guid
            for guid in GUID.objects(__raw__={
                'tag': GisObjectType.AREA,
                'provider_id': provider_id,
                'object_id': {'$in':area_ids},
            })}

        return instance


class AreasIdsDataImporter(BaseGISDataImporter):

    USE_OPENPYXL = True

    XLSX_WORKSHEETS = {
        'Идентификаторы помещений ГИСЖКХ': {
            'entry_import_method': 'import_entry_areas',
            'title': 'Помещения дома',
            'start_row': 3,
            'columns': {
                AreasFields.HOUSE_GUID: 'B',
                AreasFields.FIAS: 'C',
                AreasFields.FIAS_PARENT: 'D',
                AreasFields.LIVING_AREA_NUMBER: 'N',
                AreasFields.NOT_LIVING_AREA_NUMBER: 'P',
                AreasFields.ROOM_NUMBER: 'O',
                AreasFields.HOUSE_UID: 'S',
                AreasFields.AREA_UID: 'T',
                AreasFields.ROOM_UID: 'U',
                AreasFields.CADASTRAL_NUMBER: 'V',
                AreasFields.GIS_GUID: 'Z',
                AreasFields.ANNULMENT_DATE: 'AA',
                AreasFields.DEMOLISH_DATE: 'AB',
            }
        },
    }

    def import_entry_areas(self, entry, task: GisBaseImportTask, links, schema):

        if entry[AreasFields.ANNULMENT_DATE] is not None or \
                entry[AreasFields.DEMOLISH_DATE] is not None:
            # print('SKIPPED', entry[AreasFields.GIS_GUID],
            #     'ANNULLED', entry[AreasFields.ANNULMENT_DATE])
            return  # аннулирован или снесен

        fias_guid: str = entry[AreasFields.FIAS]
        house_uid: str = entry[AreasFields.HOUSE_UID]
        cadastral_number: str = entry[AreasFields.CADASTRAL_NUMBER]
        has_cadastral: bool = cadastral_number and cadastral_number != 'нет'

        living_number: str = entry[AreasFields.LIVING_AREA_NUMBER]
        not_living_number: str = entry[AreasFields.NOT_LIVING_AREA_NUMBER]
        room_number: str = entry[AreasFields.ROOM_NUMBER]

        gis_guid: str = entry[AreasFields.GIS_GUID]

        storage: Storage = Storage(fias_guid, task.provider.id)
        if storage is None or storage.house is None:
            status_log = GisImportStatus(
                status='неудача',
                task=task.parent.id,
                is_error=True,
                description=f"нет доступа к дому {fias_guid}",
            )
            status_log.save()
            return
        elif not living_number and not not_living_number and not room_number:
            assert isinstance(storage.house, House)
            if has_cadastral:
                storage.house.cadastral_number = cadastral_number
            storage.house.gis_uid = house_uid
            storage.house.save()
            # print('SAVED HOUSE', fias_guid, 'ID', storage.house.id)

            if isinstance(storage.house_guid, GUID):
                storage.house_guid.unmap()  # отвязываем от операции
            else:
                storage.house_guid = GUID(
                    # WARN без provider_id и premises_id
                    tag=GisObjectType.HOUSE, object_id=storage.house.id,
                    number=storage.house.number, desc=storage.house.address,
                    # status и saved формируются при сохранении
                )

            storage.house_guid.gis = gis_guid
            storage.house_guid.unique = house_uid
            storage.house_guid.save()
            return

        area_uid: str = entry[AreasFields.AREA_UID]

        if living_number:
            area = storage.living_areas.get(living_number)
        elif not_living_number:
            area = storage.not_living_areas.get(not_living_number) or \
                storage.not_living_areas.get(not_living_number.replace('-', ''))
        else:
            area = None

        if isinstance(area, Area):
            # print('AREA', area.str_number, 'ID', area.id)
            status = []
            if area.gis_uid != area_uid:
                area.gis_uid = area_uid
                status.append("уникальный номер изменен")

            if has_cadastral and area.cadastral_number != cadastral_number:
                area.cadastral_number = cadastral_number
                status.append("кадастровый номер изменен")

            if room_number and area.rooms:
                room_uid: str = entry[AreasFields.ROOM_UID]
                found = False
                for room in area.rooms:
                    assert isinstance(room, AreaEmbeddedRoom)
                    if room.number == room_number:
                        found = True
                        if room.gis_uid != room_uid:
                            room.gis_uid = room_uid
                            status.append(f"комната {room_number} изменена")
                        # TODO GUID(GisObjectType.ROOM)
                        break
                if not found:
                    status.append(f"комната {room_number} не найдена")

            area.save()  # TODO только при наличии изменений?
            # print('SAVED AREA', area.str_number, 'ID', area.id)

            area_guid: GUID = storage.area_guids.get(area.id)
            if isinstance(area_guid, GUID):
                area_guid.unmap()
            else:
                area_guid = GUID(
                    tag=GisObjectType.AREA, object_id=area.id,
                    provider_id=storage.provider_id,
                    number=area.str_number, desc=area.str_number_full,
                )

            area_guid.premises_id = storage.house.id
            area_guid.gis = gis_guid
            area_guid.unique = area_uid
            area_guid.save()

            status_log = GisImportStatus(
                status='успешно {}'.format(area_uid),
                task=task.parent.id,
                description=','.join(status),
            )
            status_log.save()
        else:
            # print('AREA', living_number or not_living_number, 'NOT FOUND')
            status_log = GisImportStatus(
                status='неудача',
                task=task.parent.id,
                is_error=True,
                description=f"помещение {area_uid} не найдено",
            )
            status_log.save()
