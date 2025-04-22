import uuid
from datetime import datetime

from mongoengine import Q, ListField, ReferenceField, FileField, StringField, DateTimeField

from processing.data_importers.gis.capital_repair import CapitalRepairInfoDataImporter
from processing.data_producers.gis.capital_repair import CapitalRepairInfoDataProducer
from app.house.models.house import House
from processing.models.tasks.base import Task, TaskStatus, RequestTask
from processing.models.tasks.gis.base import GisBaseExportRequest, GisBaseImportTask, GisBaseImportRequest, GisBaseExportTask

from processing.data_producers.gis.houses import HousesDataProducer

from constants.common import MONTH_NAMES
from processing.models.tasks.gis.gis_filename_limiter import limit_xlsx_filename


class CapitalRepairInfoExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(GisBaseExportRequest, 'DESCRIPTION') + ': Кап. ремонт.'

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'Кап. ремонт'
        ]) + '.zip'

    def get_tasks(self):

        filename = ' '.join([
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1]
        ])

        filename = limit_xlsx_filename(filename=filename, doc_type='Кап. ремонт')

        return [self.create_child_task(CapitalRepairInfoExportTask, provider=self.provider, date=self.date, filename=filename)]


class CapitalRepairInfoExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': Кап. ремонт.'
    date = DateTimeField(required=True)
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)

    PRODUCER_CLS = CapitalRepairInfoDataProducer

    def get_entries(self):

        entries = {
            self.provider.id: {
                'provider': self.provider,
                'date': self.date
            }
        }

        return entries


class CapitalRepairInfoImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': Кап. ремонт'

    IMPORTER_CLS = CapitalRepairInfoDataImporter
    START_ROW = 3


class CapitalRepairInfoImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': Кап. ремонт'

    IMPORT_TASK_CLS = CapitalRepairInfoImportTask

