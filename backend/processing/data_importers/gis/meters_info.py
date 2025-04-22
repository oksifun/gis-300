from app.area.models.area import Area
from app.house.models.house import House
from app.meters.models.meter import AreaMeter, HouseMeter
from processing.data_importers.gis.base import is_status_error, get_error_string

from processing.models.logging.gis_log import GisImportStatus
from .base import BaseGISDataImporter


METERS_TYPE = {
            'Холодная вода': [
                'ColdWaterAreaMeter',
                'ColdWaterHouseMeter'
            ],
            'Горячая вода': [
                'HotWaterAreaMeter',
                'HotWaterHouseMeter'
            ],
            'Электрическая энергия': [
                'ElectricOneRateAreaMeter',
                'ElectricThreeRateAreaMeter',
                'ElectricTwoRateAreaMeter',
                'ElectricOneRateHouseMeter',
                'ElectricThreeRateHouseMeter',
                'ElectricTwoRateHouseMeter'
            ],
            'Тепловая энергия': [
                'HeatAreaMeter',
                'HeatDistributorAreaMeter',
                'HeatHouseMeter'
            ],
            'Газ': [
                'GasHouseMeter',
                'GasAreaMeter'
            ]
        }


class MetersInfoFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    HOUSE_UID = 'Уникальный номер дома. Обязательно для заполнения, если Тип ' \
                'ПУ =  Коллективный (общедомовой) или Индивидуальный ПУ в ЖД'
    AREA_UID = 'Уникальный номер помещения. Обязательно для заполнения, если ' \
               'Тип ПУ = Индивидуальный / Общий (квартирный)'
    ROOM_UID = 'Уникальный номер комнаты. Обязательно для заполнения, если ' \
               'Тип ПУ = Комнатный'
    ACCOUNT_ID = 'Номер лицевого счета/Единый лицевой счет. Обязательно для ' \
                 'всех типов ПУ, кроме типа Коллективный (Общедомовой)'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class MetersInfoExtraServicesFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class MetersInfoExtraAccountsFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class MetersInfoExtraRoomsFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class MetersInfoFields_2:
    
    METER_TYPE = 'Вид ПУ'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    METER_BRAND = 'Марка ПУ'
    METER_MODEL = 'Модель ПУ'
    METER_GIS_UID = 'Номер прибора учета в ГИС ЖКХ'
    HOUSE_GIS_UID = 'Уникальный номер дома'
    AREA_GIS_UID = 'Уникальный номер помещения'
    ROOM_GIS_UID = 'Уникальный номер комнаты'
    ACCOUNT_GIS_UID = 'Уникальный номер лицевого счета, присвоенный ГИС ЖКХ'
    IS_REMOTE = 'Наличие возможности дистанционного снятия показаний'
    REMOTE_SYSTEM_INFO = 'Информация о наличии возможности дистанционноо ' \
                         'снятия показаний ПУ указанием наименования ' \
                         'установленной системы'
    IS_CHECK_REQUIRED = 'Признак обязательности поверки'
    INSTALLATION_DATE = 'Дата установки'
    SERVICE_DATE = 'Дата ввода в эксплуатацию'
    FIRST_CHECK_DATE = 'Дата первичной поверки'
    SEALING_DATE = 'Дата опломбирования ПУ заводом-изготовителем'
    CHECK_INTERVAL = 'Межповерочный интервал'
    NEXT_CHECK_DATE = 'Плановая дата поверки'
    HAS_TEMP_SENSOR = 'Наличие датчиков температуры'
    TEMP_SENSOR_INFO = 'Информация о наличии датчиков температуры с ' \
                       'указанием их местоположения на узле учета'
    HAS_PRESSURE_SENSOR = 'Наличие датчиков давления'
    PRESSURE_SENSOR_INFO = 'Информация о наличии датчиков давления с ' \
                           'указанием их местоположения на узле учета'
    METER_STATUS = 'Статус ПУ'
    SERVICE_TYPE = 'Вид коммунального ресурса'
    METER_RATE = 'Вид ПУ по количеству тарифов'
    METER_VALUE_1 = 'Базовое показание (Т1)'
    METER_VALUE_2 = 'Базовое показание (Т2)'
    METER_VALUE_3 = 'Базовое показание (Т3)'
    METER_UNIT = 'Единица измерения показания'
    METER_RATIO = 'Коэффициент трансформации'


class MetersInfoDataImporter(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Сведения о ПУ': {
            'entry_import_method': 'import_entry_meters_info',
            'title': 'Сведения о ПУ',
            'start_row': 2,
            'columns': {
                MetersInfoFields.ADDRESS: 'A',
                MetersInfoFields.SERIAL_NUMBER: 'B',
                MetersInfoFields.HOUSE_UID: 'F',
                MetersInfoFields.AREA_UID: 'G',
                MetersInfoFields.ROOM_UID: 'H',
                MetersInfoFields.ACCOUNT_ID: 'I',
                MetersInfoFields.GIS_PROCESSING_STATUS: 'AE',
            }
        },
        'Доп. комм. ресурсы': {
            'entry_import_method': 'import_entry_meters_extra_services',
            'title': 'Доп. комм. ресурсы',
            'start_row': 2,
            'columns': {
                MetersInfoExtraServicesFields.ADDRESS: 'A',
                MetersInfoExtraServicesFields.SERIAL_NUMBER: 'B',
                MetersInfoFields.GIS_PROCESSING_STATUS: 'G',
            }
        },
        'Доп. лицевые счета ПУ': {
            'entry_import_method': 'import_entry_meters_extra_accounts',
            'title': 'Доп. лицевые счета ПУ',
            'start_row': 2,
            'columns': {
                MetersInfoExtraAccountsFields.ADDRESS: 'A',
                MetersInfoExtraAccountsFields.SERIAL_NUMBER: 'B',
                MetersInfoFields.GIS_PROCESSING_STATUS: 'F',
            }
        },
        'Доп. комнаты ПУ': {
            'entry_import_method': 'import_entry_meters_extra_rooms',
            'title': 'Доп. комнаты ПУ',
            'start_row': 2,
            'columns': {
                MetersInfoExtraRoomsFields.ADDRESS: 'A',
                MetersInfoExtraRoomsFields.SERIAL_NUMBER: 'B',
                MetersInfoFields.GIS_PROCESSING_STATUS: 'F',
            }
        },
    }

    def import_entry_meters_info(self, entry, import_task, links, ws_schema):

        room_gis_uid = entry[MetersInfoFields.ROOM_UID]
        area_gis_uid = entry[MetersInfoFields.AREA_UID]
        house_gis_uid = entry[MetersInfoFields.HOUSE_UID]

        gis_processing_status = entry[MetersInfoFields.GIS_PROCESSING_STATUS]

        if area_gis_uid:
            area = Area.objects(gis_uid=area_gis_uid).first()
            meter = AreaMeter.objects(area__id=area.id).first()

            if not is_status_error(gis_processing_status):
                meter.gis_uid = gis_processing_status
                meter.save()

        elif house_gis_uid:
            house = House.objects(gis_uid=house_gis_uid).first()
            meter = HouseMeter.objects(house__id=house.id).first()

            if not is_status_error(gis_processing_status):
                meter.gis_uid = gis_processing_status
                meter.save()

        status_log = GisImportStatus(
            status=gis_processing_status,
            task=import_task.parent.id,
        )
        if is_status_error(gis_processing_status):
            status_log.is_error = True
            status_log.description = get_error_string(gis_processing_status)
        status_log.save()

    def import_entry_meters_extra_services(self, entry, import_task, links,
                                           ws_schema):
        gis_processing_status = entry[MetersInfoFields.GIS_PROCESSING_STATUS]
        status_log = GisImportStatus(
            status=gis_processing_status,
            task=import_task.parent.id,
        )
        if is_status_error(gis_processing_status):
            status_log.is_error = True
            status_log.description = get_error_string(gis_processing_status)
        status_log.save()

    def import_entry_meters_extra_accounts(self, entry, import_task, links,
                                           ws_schema):
        gis_processing_status = entry[MetersInfoFields.GIS_PROCESSING_STATUS]
        status_log = GisImportStatus(
            status=gis_processing_status,
            task=import_task.parent.id,
        )
        if is_status_error(gis_processing_status):
            status_log.is_error = True
            status_log.description = get_error_string(gis_processing_status)
        status_log.save()

    def import_entry_meters_extra_rooms(self, entry, import_task, links,
                                        ws_schema):
        gis_processing_status = entry[MetersInfoFields.GIS_PROCESSING_STATUS]
        status_log = GisImportStatus(
            status=gis_processing_status,
            task=import_task.parent.id,
        )
        if is_status_error(gis_processing_status):
            status_log.is_error = True
            status_log.description = get_error_string(gis_processing_status)
        status_log.save()


# Разбор файла 'Экспорт сведений о приборах учета'
class MetersInfoDataImporter_2(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Сведения о ПУ': {
            'entry_import_method': 'import_entry_meters_info',
            'title': 'Сведения о ПУ',
            'start_row': 3,
            'columns': {
                MetersInfoFields_2.SERIAL_NUMBER: 'B',
                MetersInfoFields_2.METER_GIS_UID: 'E',
                MetersInfoFields_2.HOUSE_GIS_UID: 'Q',
                MetersInfoFields_2.AREA_GIS_UID: 'T',
                MetersInfoFields_2.ROOM_GIS_UID: 'V',
            }
        },
    }

    def import_entry_meters_info(self, entry, import_task, links, ws_schema, meter_type):

        meters_type = METERS_TYPE.get(meter_type)
        room_gis_uid = entry[MetersInfoFields_2.ROOM_GIS_UID]
        area_gis_uid = entry[MetersInfoFields_2.AREA_GIS_UID]
        house_gis_uid = entry[MetersInfoFields_2.HOUSE_GIS_UID]

        meter_serial_number = entry[MetersInfoFields_2.SERIAL_NUMBER]
        meter_gis_uid = entry[MetersInfoFields_2.METER_GIS_UID]

        if area_gis_uid:
            area = Area.objects(
                Area.get_binds_query(
                    import_task.provider._binds_permissions,
                ),
                gis_uid=area_gis_uid,
            ).first()
            if area:
                meters = list(
                    AreaMeter.objects(
                        AreaMeter.get_binds_query(
                            import_task.provider._binds_permissions,
                        ),
                        serial_number=meter_serial_number,
                        area__id=area.id,
                        is_deleted__ne=True,
                        **(dict(_type__in=meters_type) if meters_type else {})
                    ).order_by(
                        '-working_start_date',
                        '-working_finish_date',
                    ),
                )
                meter = None
                for m in meters:
                    if not m.working_finish_date:
                        meter = m
                        break
                if not meter:
                    meter = meters[0] if meters else None
                if meter and meter_gis_uid:
                    meter.gis_uid = meter_gis_uid
                    meter.save(ignore_meter_validation=True)
                    status_log = GisImportStatus(
                        status='успешно',
                        task=import_task.parent.id,
                        description='Успешно импортирован индивидуальный '
                                    'счетчик({}); помещение {}'.format(
                            meter_gis_uid,
                            area_gis_uid
                        )
                    )
                    status_log.save()
                    return

        elif house_gis_uid:
            house = House.objects(
                House.get_binds_query(
                    import_task.provider._binds_permissions,
                ),
                gis_uid=house_gis_uid,
            ).first()

            if house:
                meters = list(
                    HouseMeter.objects(
                        HouseMeter.get_binds_query(
                            import_task.provider._binds_permissions,
                        ),
                        serial_number=meter_serial_number,
                        house__id=house.id,
                        is_deleted__ne=True,
                        **(dict(_type__in=meters_type) if meters_type else {}),
                    ).order_by(
                        "working_start_date",
                    ),
                )
                current_meters = []
                for meter in meters:
                    if not meter.working_finish_date:
                        current_meters.append(meter)
                meters.extend(current_meters)
                meter = meters[-1] if meters else None
                if meter and meter_gis_uid:
                    meter.gis_uid = meter_gis_uid
                    meter.save(ignore_meter_validation=True)
                    status_log = GisImportStatus(
                        status='успешно',
                        task=import_task.parent.id,
                        description='Успешно импортирован общедомовой '
                                    'счетчик({}); дом {}'.format(
                            meter_gis_uid,
                            house_gis_uid
                        )
                    )
                    status_log.save()
                    return

        status_log = GisImportStatus(
            status='неудача',
            task=import_task.parent.id,
            description='Неверные данные (квартира/дом/серийный номер): '
                        '{}/{}/{}'.format(
                area_gis_uid,
                house_gis_uid,
                meter_serial_number
            )
        )
        status_log.save()
