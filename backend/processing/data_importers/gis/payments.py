import datetime

from processing.data_importers.gis.base import BaseGISDataImporter
from processing.models.billing.service_type import ServiceTypeGisName


class PD_Section_1_2:
    DOC_NUMBER = 'Номер платежного документа'

    PAYMENT_ID_BY_GIS = 'Идентификатор платежного документа'
    TO_PAY_TOTAL_BY_GIS = '(РАССЧИТАНО ГИС ЖКХ)  Итого к оплате за расчетный период'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class PD_Section_3_6:
    DOC_NUMBER = 'Номер платежного документа'
    SERVICE = 'Услуга'

    ACCRUED_BY_GIS_TOTAL = '(РАССЧИТАНО ГИС ЖКХ) Всего начислено за расчетный период (без перерасчетов и льгот), руб.'
    TO_PAY_BY_GIS_TOTAL = '(РАССЧИТАНО ГИС ЖКХ) Итого к оплате за расчетный период, руб. - Всего'

    PROCESSING_STATUS = 'Статус обработки'


class PaymentsDPDFields:
    DOC_NUMBER = 'Номер платежного документа'
    SERVICE = 'Услуга'

    PROCESSING_STATUS = 'Статус обработки'


class PaymentsCourtFields:
    DOC_NUMBER = 'Номер платежного документа'

    PROCESSING_STATUS = 'Статус обработки'


class PaymentsServicesFields:
    REFERENCE_NAME = 'Наименование справочника'
    REFERENCE_NUMBER = 'Реестровый номер справочника'
    POSITION_NAME = 'Наименование позиции справочника'
    POSITION_NUMBER = 'Реестровый номер позиции'


class PaymentsDataImporter(BaseGISDataImporter):

    XLSX_WORKSHEETS = {
        'Раздел 1': {
            'entry_import_method': 'import_entry_payments_section_1',
            'title': 'Раздел 1',
            'start_row': 4,
            'columns': {
                PD_Section_1_2.DOC_NUMBER: 'C',

                PD_Section_1_2.PAYMENT_ID_BY_GIS: 'T',
                PD_Section_1_2.TO_PAY_TOTAL_BY_GIS: 'W',
                PD_Section_1_2.GIS_PROCESSING_STATUS: 'X',

            }
        },
        'Разделы 3-6': {
            'entry_import_method': 'import_entry_payments_section_3_6',
            'title': 'Разделы 3-6',
            'start_row': 5,
            'columns': {
                PD_Section_3_6.DOC_NUMBER: 'A',
                PD_Section_3_6.SERVICE: 'B',

                PD_Section_3_6.ACCRUED_BY_GIS_TOTAL: 'AD',
                PD_Section_3_6.TO_PAY_BY_GIS_TOTAL: 'AE',

                PD_Section_3_6.PROCESSING_STATUS: 'AF',

            }
        },
        'ДПД': {
            'entry_import_method': 'import_entry_payments_section_dpd',
            'title': 'ДПД',
            'start_row': 2,
            'columns': {
                PaymentsDPDFields.DOC_NUMBER: 'A',
                PaymentsDPDFields.SERVICE: 'B',

                PaymentsDPDFields.PROCESSING_STATUS: 'E',
            }
        },
        'Неустойки и судебные расходы': {
            'entry_import_method': 'import_entry_payments_section_court',
            'title': 'Неустойки и судебные расходы',
            'start_row': 2,
            'columns': {
                PaymentsCourtFields.DOC_NUMBER: 'A',

                PaymentsCourtFields.PROCESSING_STATUS: 'E',
            }
        },
        'Услуги исполнителя': {
            'entry_import_method': 'import_entry_payments_section_services',
            'title': 'Услуги исполнителя',
            'start_row': 2,
            'columns': {
                PaymentsServicesFields.REFERENCE_NAME: 'A',
                PaymentsServicesFields.REFERENCE_NUMBER: 'B',
                PaymentsServicesFields.POSITION_NAME: 'C',
                PaymentsServicesFields.POSITION_NUMBER: 'D',
            }
        },
    }

    def import_entry_payments_section_1(self, entry, import_task, links,
                                          ws_schema):
        pass

    def import_entry_payments_section_3_6(self, entry, import_task, links,
                                          ws_schema):
        pass

    def import_entry_payments_section_dpd(self, entry, import_task, links,
                                          ws_schema):
        pass

    def import_entry_payments_section_court(self, entry, import_task, links,
                                            ws_schema):
        pass

    def import_entry_payments_section_services(self, entry, import_task, links,
                                               ws_schema):
        service_gis_name = entry[PaymentsServicesFields.POSITION_NAME]
        provider_id = import_task.provider.id
        bind = ServiceTypeGisName.objects(
            provider=provider_id,
            gis_title=service_gis_name,
            closed=None,
        )
        if not bind:
            ServiceTypeGisName(
                provider=provider_id,
                gis_title=service_gis_name,
                created=datetime.datetime.now(),
                reference_name=entry[PaymentsServicesFields.REFERENCE_NAME],
                reference_number=entry[PaymentsServicesFields.REFERENCE_NUMBER],
                position_number=entry[PaymentsServicesFields.POSITION_NUMBER],
            ).save()

