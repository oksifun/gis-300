from app.meters.models.meter import HouseMeter, AreaMeter
from processing.data_importers.gis.base import is_status_error, get_error_string
from processing.models.logging.gis_log import GisImportStatus

from .base import BaseGISDataImporter


class HouseMetersReadingsFields:
    GIS_UID = 'Номер ПУ в ГИС ЖКХ'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class AreaMeterReadingsFields:
    GIS_UID = 'Номер ПУ в ГИС ЖКХ'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class HouseMetersReadingsDataImporter(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Импорт показаний ОДПУ': {
            'entry_import_method': 'import_entry_house_meters_readings',
            'title': 'Импорт показаний ОДПУ',
            'start_row': 2,
            'columns': {
                HouseMetersReadingsFields.GIS_UID: 'B',
                HouseMetersReadingsFields.GIS_PROCESSING_STATUS: 'J'  # 13.1.3.1
            }
        },
    }

    def import_entry_house_meters_readings(self, entry, import_task, links,
                                           ws_schema):
        meter = HouseMeter.objects(
            gis_uid=entry[HouseMetersReadingsFields.GIS_UID],
            is_deleted__ne=True,
        ).order_by('-working_start_date').first()
        gis_processing_status = \
            entry[HouseMetersReadingsFields.GIS_PROCESSING_STATUS]
        status_log = GisImportStatus(
            status=gis_processing_status,
            task=import_task.parent.id,
        )
        if is_status_error(gis_processing_status):
            status_log.is_error = True
            status_log.description = get_error_string(
                gis_processing_status)
        status_log.save()


class AreaMetersReadingsDataImporter(BaseGISDataImporter):
    XLSX_WORKSHEETS = {
        'Импорт показаний ИПУ': {
            'entry_import_method': 'import_entry_area_meters_readings',
            'title': 'Импорт показаний ИПУ',
            'start_row': 2,
            'columns': {
                AreaMeterReadingsFields.GIS_UID: 'B',
                AreaMeterReadingsFields.GIS_PROCESSING_STATUS: 'J'  # 13.1.3.1
            }
        },
    }

    def import_entry_area_meters_readings(self, entry, import_task, links,
                                          ws_schema):
        meter = AreaMeter.objects(
            gis_uid=entry[AreaMeterReadingsFields.GIS_UID],
            is_deleted__ne=True,
        ).first()
        gis_processing_status = \
            entry[AreaMeterReadingsFields.GIS_PROCESSING_STATUS]
        status_log = GisImportStatus(
            status=gis_processing_status,
            task=import_task.parent.id,
        )
        if is_status_error(gis_processing_status):
            status_log.is_error = True
            status_log.description = get_error_string(
                gis_processing_status)
        status_log.save()


