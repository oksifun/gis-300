from mongoengine.fields import DateTimeField, ReferenceField

from constants.common import MONTH_NAMES
from processing.data_importers.gis.payments import PaymentsDataImporter
from processing.data_producers.gis.payments import PaymentsDataProducer
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.choices import AccrualDocumentStatus
from processing.models.tasks.gis.base import GisBaseExportRequest, \
    GisBaseExportTask, \
    GisBaseImportTask, GisBaseImportRequest
from processing.models.tasks.gis.gis_filename_limiter import limit_xlsx_filename


class PaymentsExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(GisBaseExportRequest, 'DESCRIPTION') + ': ПД'

    def get_accrual_docs(self):

        period = self.date.date().replace(day=1)

        return list(
            AccrualDoc.objects(
                sector_binds__provider=self.provider.id,
                status=AccrualDocumentStatus.READY,
                date_from=period,
            )
        )

    def get_tasks(self):

        tasks = [
            self.create_child_task(
                PaymentsExportTask,
                filename=limit_xlsx_filename(
                    filename=' '.join([
                        str(self.date.year), MONTH_NAMES[self.date.month - 1]
                    ]),
                    some_id=str(accrual_doc.id),
                    address=accrual_doc.house.address,
                    doc_type='ПД'
                ),
                accrual_doc=accrual_doc,
                date=self.date,
            )
            for accrual_doc in self.get_accrual_docs()
        ]

        if not tasks:
            raise ValueError(
                f'Nothing to export for provider {self.provider.id} '
                f'on date {self.date}'
            )

        return tasks

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'ПД'
        ]) + '.zip'


class PaymentsExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': ПД'

    date = DateTimeField(verbose_name="Дата, на которую экспортируются данные")
    accrual_doc = ReferenceField(
        'processing.models.billing.accrual_document.AccrualDoc'
    )

    PRODUCER_CLS = PaymentsDataProducer

    def get_entries(self):

        entries = {}
        for accrual in Accrual.objects(
                doc__id=self.accrual_doc.id,
                owner=self.provider.id
        ):
            group = entries.setdefault(
                accrual.account.id,
                {'accruals': [], 'date': self.accrual_doc.date_from}
            )
            group['accruals'].append(accrual)

        return entries


class PaymentsImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': ПД'

    IMPORTER_CLS = PaymentsDataImporter
    START_ROW = 3


class PaymentsImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': ПД'

    IMPORT_TASK_CLS = PaymentsImportTask
