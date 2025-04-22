import uuid
from datetime import datetime

from mongoengine import Q, ListField, ReferenceField, FileField, StringField
from mongoengine.fields import DateTimeField

from processing.data_importers.gis.houses import HousesDataImporter
from app.house.models.house import House
from processing.models.tasks.base import Task, TaskStatus, RequestTask
from processing.models.tasks.gis.base import GisBaseExportRequest, GisBaseImportTask, GisBaseImportRequest, GisBaseExportTask

from processing.data_producers.gis.houses import HousesDataProducer

from constants.common import MONTH_NAMES
from processing.models.tasks.gis.gis_filename_limiter import limit_xlsx_filename


class HousesExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(GisBaseExportRequest, 'DESCRIPTION') + ': МКД'

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'МКД'
        ]) + '.zip'

    def get_tasks(self):

        # TODO Возможно вместо определения по привязкам дома к провайдеру
        # стоит составлять список домов по наличию документов начислений за конкретный период
        query = {
            'service_binds': {
                '$elemMatch': {
                    'provider': self.provider.id,
                    'date_start': {'$lt': self.date},
                    '$or': [
                        {'date_end': {'$gt': self.date}},
                        {'date_end': None}
                    ],
                    'is_active': True,
                },
            }
        }

        houses = list(House.objects(__raw__=query))

        # CRUTCH REFERENCE FIX
        for house in houses:
            house.pk = house.id
        # CRUTCH END

        filename = ' '.join([
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1]
        ])

        filename = limit_xlsx_filename(filename=filename, doc_type='МКД')

        return [self.create_child_task(HousesExportTask, houses=houses, filename=filename, provider=self.provider, date=self.date)]


class HousesExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': МКД'

    houses = ListField(ReferenceField('app.house.models.house.House', verbose_name="Дом"))
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)
    date = DateTimeField()

    PRODUCER_CLS = HousesDataProducer

    def get_entries(self):

        entries = {
            house.id: {
                'house': house,
                'provider': self.provider,
                'date': self.date,
            } for house in self.houses
        }

        return entries


class HousesImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': МКД'

    IMPORTER_CLS = HousesDataImporter
    START_ROW = 3


class HousesImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': МКД'

    IMPORT_TASK_CLS = HousesImportTask
