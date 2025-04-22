from mongoengine import ValidationError

from app.house.models.house import House
from processing.data_importers.gis.base import get_error_string, is_status_error
from processing.models.billing.account import Tenant
from processing.models.logging.gis_log import GisImportStatus

from .base import BaseGISDataImporter


class AccountsCommonFields:
    ENTRY_N = '№ записи'
    ACCOUNT_NUMBER = 'Номер ЛС (иной идентификатор потребителя)'
    HCS_UID = 'Идентификатор ЖКУ'
    GIS_ACCOUNT_UID = 'Единый лицевой счет'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class AccountsAreasFields:
    ENTRY_N = '№ записи лицевого счета'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class AccountsDataImporter(BaseGISDataImporter):
    XLSX_WORKSHEETS = {
        'Основные сведения': {
            'entry_import_method': 'import_entry_common',
            'title': 'Основные сведения',
            'start_row': 3,
            'columns': {
                AccountsCommonFields.ENTRY_N: 'A',
                AccountsCommonFields.ACCOUNT_NUMBER: 'B',
                AccountsCommonFields.HCS_UID: 'C',
                AccountsCommonFields.GIS_ACCOUNT_UID: 'V',
                AccountsCommonFields.GIS_PROCESSING_STATUS: 'W'
            }
        },
        'Помещения': {
            'entry_import_method': 'import_entry_areas',
            'title': 'Помещения',
            'start_row': 3,
            'columns': {
                AccountsAreasFields.ENTRY_N: 'A',
                AccountsAreasFields.GIS_PROCESSING_STATUS: 'I'
            },
            # 'links': {
            #     AccountsCommonFields.ACCOUNT_NUMBER: {
            #         'from_worksheet': 'Основные сведения',
            #         'if_match': {
            #             'target': AccountsAreasFields.ENTRY_N,
            #             'linked': AccountsCommonFields.ENTRY_N
            #         },
            #     }
            # }
        }
    }

    def import_entry_common(self, entry, import_task, links, ws_schema):

        account_number = entry[AccountsCommonFields.ACCOUNT_NUMBER]
        gis_uid = entry[AccountsCommonFields.GIS_ACCOUNT_UID]
        hcs_uid = entry[AccountsCommonFields.HCS_UID]
        gis_processing_status = \
            entry[AccountsCommonFields.GIS_PROCESSING_STATUS]

        account = Tenant.objects(
            number=account_number,
        ).only(
            'id',
            'gis_uid',
            'hcs_uid',
        ).as_pymongo().first()
        if account:
            Tenant.objects(
                pk=account['_id'],
            ).update(
                gis_uid=gis_uid,
                hcs_uid=hcs_uid,
            )

            status_log = GisImportStatus(
                status=gis_processing_status,
                task=import_task.parent.id,
            )
            if is_status_error(gis_processing_status):
                status_log.is_error = True
                status_log.description = get_error_string(gis_processing_status)
            status_log.save()

    def import_entry_areas(self, entry, import_task, links, ws_schema):

        # account_number = links[AccountsCommonFields.ACCOUNT_NUMBER]
        # номер записи подразумевает не номер лицевого счета, а номер записи на
        # листе 'Основные сведения', но связи сейчас работают очень медленно,
        # поэтому сейчас используем это как номер личевого счета
        # TODO вернуть обратно, когда связи будут работать нормально
        account_number = entry[AccountsAreasFields.ENTRY_N]
        gis_processing_status = entry[AccountsAreasFields.GIS_PROCESSING_STATUS]

        account = Tenant.objects(number=account_number).first()
        if account:
            status_log = GisImportStatus(
                status=gis_processing_status,
                task=import_task.parent.id,
            )
            if is_status_error(gis_processing_status):
                status_log.is_error = True
                status_log.description = get_error_string(gis_processing_status)
            status_log.save()


class AccountsIdsFields:
    ACCOUNT_NUMBER = 'Номер ЛС'
    GIS_ACCOUNT_UID = 'Номер ЕЛС в ГИС ЖКХ'
    HCS_UID = 'Идентификатор ЖКУ'
    AREA_UID = 'Уникальный номер дома / Уникальный номер помещения / ' \
               'Уникальный номер комнаты сформированный ГИС ЖКХ'
    ADDRESS = 'Адрес ОЖФ'


class AccountsIdsDataImporter(BaseGISDataImporter):
    XLSX_WORKSHEETS = {
        'Шаблон экспорта ЕЛС': {
            'entry_import_method': 'import_entry_common',
            'title': 'Шаблон экспорта ЕЛС',
            'start_row': 2,
            'columns': {
                AccountsIdsFields.ACCOUNT_NUMBER: 'A',
                AccountsIdsFields.GIS_ACCOUNT_UID: 'B',
                AccountsIdsFields.HCS_UID: 'C',
                AccountsIdsFields.AREA_UID: 'D',
                AccountsIdsFields.ADDRESS: 'E'
            },
        },
    }

    def import_entry_common(self, entry, import_task, links, ws_schema):

        account_number = entry[AccountsIdsFields.ACCOUNT_NUMBER]
        gis_uid = entry[AccountsIdsFields.GIS_ACCOUNT_UID]
        hcs_uid = entry[AccountsIdsFields.HCS_UID]
        account = Tenant.objects(number=account_number).first()
        if account:
            house = House.objects(
                pk=account.area.house.id,
                service_binds__provider=import_task.provider.id
            ).first()
            if house:
                account.gis_uid = gis_uid
                account.hcs_uid = hcs_uid
                try:
                    Tenant.objects(
                        pk=account.id,
                    ).update(
                        gis_uid=gis_uid,
                        hcs_uid=hcs_uid,
                    )
                    status_log = GisImportStatus(
                        status='успешно {}'.format(account_number),
                        task=import_task.parent.id,
                    )
                    status_log.save()
                except ValidationError as error:
                    msg = 'неудача {}: {}'.format(account_number, str(error))
                    status_log = GisImportStatus(
                        status='неудача',
                        task=import_task.parent.id,
                        is_error=True,
                        description=msg,
                    )
                    status_log.save()
            else:
                status_log = GisImportStatus(
                    status='неудача',
                    task=import_task.parent.id,
                    is_error=True,
                    description='{} нет доступа'.format(account_number),
                )
                status_log.save()
        else:
            status_log = GisImportStatus(
                status='неудача',
                task=import_task.parent.id,
                is_error=True,
                description='{} не найдено'.format(account_number),
            )
            status_log.save()
