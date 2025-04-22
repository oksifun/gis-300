from processing.data_importers.gis.base import is_status_error, get_error_string
from processing.models.billing.account import Account
from processing.models.logging.gis_log import GisImportStatus

from .base import BaseGISDataImporter


class CoopMembersCommonFields:
    NUMBER = '№'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class CoopMembersOwnershipFields:
    
    NUMBER = '№ строки с листа "Общая информация"'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class CoopMembersDataImporter(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Общая информация': {
            'entry_import_method': 'import_entry_coop_members_common',
            'title': 'Общая информация',
            'start_row': 3,
            'columns': {
                CoopMembersCommonFields.NUMBER: 'A',
                CoopMembersCommonFields.GIS_PROCESSING_STATUS: 'W'
            }
        },
        'Информация о праве соб-ти': {
            'entry_import_method': 'import_entry_coop_members_ownership_info',
            'title': 'Информация о праве соб-ти',
            'start_row': 4,
            'columns': {
                CoopMembersOwnershipFields.NUMBER: 'A',
                CoopMembersOwnershipFields.GIS_PROCESSING_STATUS: 'J'
            }
        },
    }

    def import_entry_coop_members_common(self, entry, import_task, links,
                                         ws_schema):
        account_number = entry[CoopMembersCommonFields.NUMBER]
        account = Account.objects(number=account_number).first()
        gis_processing_status = \
            entry[CoopMembersCommonFields.GIS_PROCESSING_STATUS]
        if account:
            status_log = GisImportStatus(
                status=gis_processing_status,
                task=import_task.parent.id,
            )
            if is_status_error(gis_processing_status):
                status_log.is_error = True
                status_log.description = get_error_string(gis_processing_status)
            status_log.save()

    def import_entry_coop_members_ownership_info(self, entry, import_task,
                                                 links, ws_schema):
        account_number = entry[CoopMembersOwnershipFields.NUMBER]
        account = Account.objects(number=account_number).first()
        gis_processing_status = \
            entry[CoopMembersOwnershipFields.GIS_PROCESSING_STATUS]

        if account:
            status_log = GisImportStatus(
                status=gis_processing_status,
                task=import_task.parent.id,
            )
            if is_status_error(gis_processing_status):
                status_log.is_error = True
                status_log.description = get_error_string(gis_processing_status)
            status_log.save()
