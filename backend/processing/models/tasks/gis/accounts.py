import itertools
import logging
from logging import warning

from mongoengine import ListField, ReferenceField, DateTimeField, StringField

from app.area.models.area import Area
from constants.common import MONTH_NAMES
from processing.data_importers.gis.accounts import (
    AccountsDataImporter, AccountsIdsDataImporter
)
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.account import Tenant
from processing.models.choices import AccrualsSectorType, AccrualDocumentStatus
from processing.models.tasks.gis.base import (
    GisBaseExportRequest, GisBaseImportRequest,
    GisBaseImportTask, GisBaseExportTask
)

from processing.data_producers.gis.accounts import AccountsDataProducer
from processing.models.tasks.gis.gis_filename_limiter import limit_xlsx_filename


logger = logging.getLogger('c300')


class AccountType:
    MANAGEMENT = 'УО'
    SUPPLY = 'РСО'
    CAPITAL_REPAIR = 'КР'


# TODO перепроверить привязки!
sector_code_to_account_type = {
    AccrualsSectorType.RENT: AccountType.MANAGEMENT,
    AccrualsSectorType.SOCIAL_RENT: AccountType.MANAGEMENT,
    AccrualsSectorType.CAPITAL_REPAIR: AccountType.CAPITAL_REPAIR,
    AccrualsSectorType.HEAT_SUPPLY: AccountType.SUPPLY,
    AccrualsSectorType.WATER_SUPPLY: AccountType.SUPPLY,
    AccrualsSectorType.WASTE_WATER: AccountType.SUPPLY,
    AccrualsSectorType.CABLE_TV: AccountType.SUPPLY,
    AccrualsSectorType.GARBAGE: AccountType.SUPPLY,
    AccrualsSectorType.TARGET_FEE: AccountType.MANAGEMENT,
    AccrualsSectorType.LEASE: AccountType.MANAGEMENT,
    AccrualsSectorType.COMMERCIAL: AccountType.MANAGEMENT,
    AccrualsSectorType.COMMUNAL: AccountType.SUPPLY,
}


class AccountsExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(GisBaseExportRequest, 'DESCRIPTION') + ': ЛС'

    def get_accrual_docs(self):

        period = self.date.date().replace(day=1)

        return list(AccrualDoc.objects(
            sector_binds__provider=self.provider.id,
            status=AccrualDocumentStatus.READY,
            date_from=period,
        ))

    def get_tasks(self):

        accrual_docs = self.get_accrual_docs()

        tasks = [self.create_child_task(AccountsExportTask, **task) for task in self.accrual_docs_to_house_tasks(accrual_docs)]

        if not tasks:
            raise ValueError('Nothing to export for provider {} on date {}'.format(self.provider.id, self.date))

        return tasks

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'Лицевые счета'
        ]) + '.zip'

    def merge_house_tasks(self, house_tasks):
        merged_tasks = {}
        for house_task in house_tasks:
            merge_key = ''.join([house_task['account_type'], str(house_task['provider'].id)])

            if merge_key in merged_tasks:
                merged_tasks[merge_key]['accrual_docs'] += [house_task['accrual_doc']]
            else:
                house_task['accrual_docs'] = [house_task['accrual_doc']]
                merged_tasks[merge_key] = house_task

        for merged_task in merged_tasks.values():
            del merged_task['accrual_doc']

        return list(merged_tasks.values())

    def accrual_docs_to_house_tasks(self, accrual_docs):

        doc_tasks = []
        for accrual_doc in accrual_docs:
            provider_binds = [b for b in accrual_doc.sector_binds if b.provider == self.provider.id]

            for provider_bind in provider_binds:
                filename = ' '.join([
                    sector_code_to_account_type[provider_bind.sector_code],
                    self.provider.str_name[0: 50],
                    str(self.date.year),
                    MONTH_NAMES[self.date.month - 1]
                ])
                filename = limit_xlsx_filename(filename=filename,
                                               some_id=str(accrual_doc.id),
                                               address=accrual_doc.house.address,
                                               doc_type='Лицевые счета')

                doc_tasks.append({
                    'filename': filename,
                    'account_type': sector_code_to_account_type[provider_bind.sector_code],
                    'date': self.date,
                    'provider': self.provider,
                    'accrual_doc': accrual_doc
                })

        tasks_by_houses = {}
        for task in doc_tasks:
            tasks_by_houses.setdefault(task['accrual_doc'].house.id, []).append(task)

        tasks = itertools.chain(*[self.merge_house_tasks(house_tasks) for house_tasks in tasks_by_houses.values()])

        return tasks


class AccountsExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': ЛС'

    account_type = StringField()
    date = DateTimeField(verbose_name="Дата, на которую экспортируются данные")
    house = ReferenceField(
        'app.house.models.house.House',
        verbose_name="Дом",
    )
    accrual_docs = ListField(
        ReferenceField(
            'processing.models.billing.accrual_document.AccrualDoc',
            verbose_name="Документ начислений",
        ),
    )

    PRODUCER_CLS = AccountsDataProducer

    def get_entries(self):
        logger.info(
            'Task %s entered "%s.get_entries"',
            self.id,
            self.__class__.__name__,
        )
        entries = {}
        if self.accrual_docs:
            accrual_doc = self.accrual_docs[0]
            accruals = Accrual.objects(
                doc__id__in=[a.id for a in self.accrual_docs],
            ).only(
                'account',
            ).as_pymongo()
            num = accruals.count()
            logger.info('Task %s found %s entries to procccess', self.id, num)
            for ix, accrual in enumerate(accruals, start=1):
                if ix % 1000 == 0:
                    logger.info(
                        'Task %s processed %s of %s entries',
                        self.id, ix, num,
                    )
                if accrual['account']['_id'] in entries:
                    continue
                account = Tenant.objects(
                    id=accrual['account']['_id'],
                ).first()
                area = Area.objects(
                    id=accrual['account']['area']['_id'],
                ).first()

                if account and area:
                    entries[accrual['account']['_id']] = {
                        'account': account,
                        'account_type': self.account_type,
                        'house': self.house,
                        'area': area,
                        'date': accrual_doc.date_from
                    }

                else:
                    if not account:
                        invalid_item = (
                            'account',
                            accrual['account']['_id'],
                        )
                    else:
                        invalid_item = (
                            'area',
                            accrual['account']['area']['_id'],
                        )
                    logger.warning(
                        'Unknown %s(%s) in accrual %s',
                        invalid_item[0],
                        invalid_item[1],
                        accrual['_id'],
                    )
        logger.info(
            'Task %s left "%s.get_entries"',
            self.id,
            self.__class__.__name__,
        )
        return entries


class AccountsImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': ЛС'

    IMPORTER_CLS = AccountsDataImporter
    START_ROW = 3


class AccountsImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': ЛС'

    IMPORT_TASK_CLS = AccountsImportTask


class AccountsIdsImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': ЛС'

    IMPORTER_CLS = AccountsIdsDataImporter
    START_ROW = 3


class AccountsIdsImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': ЛС'

    IMPORT_TASK_CLS = AccountsIdsImportTask

