from app.house.models.house import House
from processing.data_importers.gis.base import get_error_string, is_status_error
from processing.models.logging.gis_log import GisImportStatus

from .base import BaseGISDataImporter


class CapitalRepairInfoFields:
    ADDRESS = 'Адрес дома'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class CapitalRepairInfoDataImporter(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Способ формирования фонда КР': {
            'entry_import_method': 'import_entry_capital_repair_info',
            'title': 'Способ формирования фонда КР',
            'start_row': 3,
            'columns': {
                CapitalRepairInfoFields.ADDRESS: 'A',
                CapitalRepairInfoFields.GIS_PROCESSING_STATUS: 'K'
            }
        },
    }

    def import_entry_capital_repair_info(self, entry, import_task, links,
                                         ws_schema):
        house_address = entry[CapitalRepairInfoFields.ADDRESS]
        house = House.objects(address=house_address).first()
        gis_processing_status = \
            entry[CapitalRepairInfoFields.GIS_PROCESSING_STATUS]

        if house:
            status_log = GisImportStatus(
                status=gis_processing_status,
                task=import_task.parent.id,
            )
            if is_status_error(gis_processing_status):
                status_log.is_error = True
                status_log.description = get_error_string(gis_processing_status)
            status_log.save()

