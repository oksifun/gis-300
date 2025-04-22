import datetime

from lib.dates import end_day_of_month
from processing.models.choices import AccrualDocumentType


def mass_create_accrual_doc(parent_task, house_id, **kwargs):
    from app.accruals.cipca.tasks.create_tasks import create_calculate_task
    from app.accruals.pipca.processing import create_empty_accrual_doc_for_calc
    new_doc_id = create_empty_accrual_doc_for_calc(
        document_type=AccrualDocumentType.MAIN,
        provider_id=parent_task.provider,
        house_id=house_id,
        date=parent_task.date or datetime.datetime.now(),
        date_from=parent_task.month,
        date_till=end_day_of_month(parent_task.month),
        sectors=[],
    )
    from processing.models.billing.provider.main import Provider
    provider = Provider.objects(pk=parent_task.provider).get()
    create_calculate_task(
        author_id=parent_task.author,
        doc_id=new_doc_id,
        subtask_name='create_accrual_doc',
        description='Создание нового документа начислений',
        month=parent_task.month,
        parent=parent_task.id,
        house_id=house_id,
        provider_id=provider.id,
        provider_name=provider.name,
        allow_empty_doc=False,
        autorun=False,
    )
    parent_task.set_house_processed(parent_task.id, 1)
    return 1


def mass_recalculate_services(parent_task, house_id, binds,
                              services_cache_codes=None, **kwargs):
    from app.accruals.cipca.tasks.create_tasks import create_calculate_task
    from app.accruals.pipca.processing import get_main_accrual_docs_for_calc
    docs = get_main_accrual_docs_for_calc(
        provider_id=parent_task.provider,
        house_id=house_id,
        month=parent_task.month,
        binds=binds,
    )
    if not docs:
        parent_task.cancel_house_tasks(house_id)
        return 1
    from processing.models.billing.provider.main import Provider
    provider = Provider.objects(pk=parent_task.provider).get()
    tasks_created = 0
    for doc in docs:
        for sector in [s.sector_code for s in doc.sector_binds]:
            create_calculate_task(
                author_id=parent_task.author,
                doc_id=doc.id,
                subtask_name='recalculate_accrual',
                description='Пересчёт по тарифам',
                services_cache_codes=services_cache_codes,
                sector=sector,
                parent=parent_task.id,
                house_id=house_id,
                provider_id=provider.id,
                provider_name=provider.name,
                autorun=False,
            )
    if tasks_created == 0:
        parent_task.cancel_house_tasks(house_id)
        return 1
    parent_task.set_house_processed(parent_task.id, tasks_created)
    return tasks_created


def mass_create_receipts(parent_task, house_id, binds,
                         sectors, print_bills_type, group_sectors,
                         print_params, **kwargs):
    from processing.models.tasks.receipt import create_receipt_task
    from app.accruals.pipca.processing import get_main_accrual_docs_for_receipts
    docs = get_main_accrual_docs_for_receipts(
        provider_id=parent_task.provider,
        house_id=house_id,
        month=parent_task.month,
        binds=binds,
    )
    from processing.models.billing.provider.main import Provider
    from app.accruals.billing.tools import set_receipt_filename
    provider = Provider.objects(pk=parent_task.provider).get()
    tasks_created = 0
    if not group_sectors:
        for doc in docs:
            # Берем только направления, существующие в документе
            confirmed_sectors = list(
                set(sector_bind.sector_code
                    for sector_bind
                    in doc.sector_binds)
                &
                set(sectors)
            )
            for sector in confirmed_sectors:
                file_name = set_receipt_filename(
                    [sector],
                    provider_name=provider.name,
                    address=doc.house.address,
                    description=doc.description,
                )
                create_receipt_task(
                    author_id=parent_task.author,
                    doc_id=doc.id,
                    subtask_name='run_creating_all_receipt',
                    description='Формирование счетов',
                    sectors=[sector],
                    parent=parent_task.id,
                    provider_id=provider.id,
                    provider_name=provider.name,
                    print_bills_type=print_bills_type,
                    file_name=file_name,
                    settings_params=print_params,
                    house_id=house_id,
                    autorun=False,
                )
                tasks_created += 1
    else:
        for doc in docs:
            confirmed_sectors = list(
                set(sector_bind.sector_code
                    for sector_bind
                    in doc.sector_binds)
                &
                set(sectors)
            )
            file_name = set_receipt_filename(
                confirmed_sectors,
                provider_name=provider.name,
                address=doc.house.address,
                description=doc.description,
            )
            create_receipt_task(
                author_id=parent_task.author,
                doc_id=doc.id,
                subtask_name='run_creating_all_receipt',
                description='Формирование счетов',
                sectors=confirmed_sectors,
                parent=parent_task.id,
                provider_id=provider.id,
                provider_name=provider.name,
                print_bills_type=print_bills_type,
                file_name=file_name,
                settings_params=print_params,
                house_id=house_id,
                autorun=False,
            )
            tasks_created += 1
    if tasks_created == 0:
        parent_task.cancel_house_tasks(house_id)
        return 1
    parent_task.set_house_processed(parent_task.id, tasks_created)
    return tasks_created


MASS_TASK_RUN_FUNCTIONS = {
    'mass_create_accrual_doc': mass_create_accrual_doc,
    'mass_recalculate_services': mass_recalculate_services,
    'mass_create_receipts': mass_create_receipts,
}
