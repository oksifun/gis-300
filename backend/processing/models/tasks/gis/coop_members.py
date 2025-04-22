from mongoengine import Q, ListField, ReferenceField

from processing.data_importers.gis.coop_member import CoopMembersDataImporter
from processing.data_producers.gis.coop_member import CoopMembersDataProducer
from app.house.models.house import House
from processing.models.billing.account import Tenant
from processing.models.tasks.gis.base import GisBaseExportRequest, \
    GisBaseImportTask, GisBaseImportRequest, GisBaseExportTask

from constants.common import MONTH_NAMES
from processing.models.tasks.gis.gis_filename_limiter import limit_xlsx_filename


class CoopMembersInfoExportRequest(GisBaseExportRequest):
    DESCRIPTION = '{}: Члены ТСЖ/ЖСК'.format(
        getattr(GisBaseExportRequest, 'DESCRIPTION'),
    )

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'Члены',
            self.provider.legal_form
        ]) + '.zip'

    def get_tasks(self):

        # if self.provider.legal_form not in {'ТСЖ', 'ЖСК', 'ТСН'}:
        #     raise ValueError('Невозможно сформировать список членов '
        #                      'для организации не являющейся ТСЖ, ЖСК или ТСН')

        provider_bind = Q(service_binds__provider=self.provider.id)
        actual_bind = (
                Q(service_binds__date_start__lt=self.date)
                & (
                        Q(service_binds__date_end=None)
                        | Q(service_binds__date_end__gte=self.date)
                )
        )
        active_bind = Q(service_binds__is_active=True)

        houses = House.objects(provider_bind & actual_bind & active_bind)

        # CRUTCH REFERENCE FIX
        for house in houses:
            house.pk = house.id
        # CRUTCH END

        filename = ' '.join([
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            self.provider.legal_form
        ])

        filename = limit_xlsx_filename(filename=filename, doc_type='Члены')

        return [
            self.create_child_task(
                CoopMembersInfoExportTask,
                houses=houses,
                filename=filename,
            ),
        ]


class CoopMembersInfoExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': Члены ТСЖ/ЖСК'

    houses = ListField(
        ReferenceField(
            'app.house.models.house.House',
            verbose_name="Дом",
        ),
    )

    PRODUCER_CLS = CoopMembersDataProducer

    def get_entries(self):

        entries = {
            account.id: {
                'account': account
            } for account in Tenant.objects(
                is_coop_member=True,
                area__house__id__in=[house.id for house in self.houses]
            )
        }

        return entries


class CoopMembersInfoImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': Члены ТСЖ/ЖСК'

    IMPORTER_CLS = CoopMembersDataImporter
    START_ROW = 3


class CoopMembersInfoImportRequest(GisBaseImportRequest):
    DESCRIPTION = '{}: Члены ТСЖ/ЖСК'.format(
        getattr(GisBaseImportRequest, 'DESCRIPTION'),
    )

    IMPORT_TASK_CLS = CoopMembersInfoImportTask

