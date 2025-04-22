from app.accruals.cipca.caching.doc_sevice_groups import \
    SERVICE_GROUP_CACHE_FUNCS, get_service_groups_by_pipca
from app.accruals.models.cache import (
    ReceiptAccrualCache,
    ReceiptsStatisticsCache,
)
from app.accruals.pipca.document import PipcaDocument
from app.celery_admin.workers.config import celery_app
from lib.dates import start_of_month
from app.accruals.cipca.calculator.tariffs import get_groups_list
from app.accruals.models.accrual_document import AccrualDoc
from settings import CELERY_SOFT_TIME_MODIFIER
from app.caching.tasks.cache_update import update_house_accruals_cache


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 5 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30
)
def update_accrual_doc_cache(self, doc_id, parent_task_id=None):
    AccrualDoc.objects(
        pk=doc_id,
    ).update(
        caching_wip=True,
    )
    doc = PipcaDocument.load_doc(doc_id)
    accruals = [d.doc_m for d in doc.debts]
    st_groups = get_service_groups_by_pipca(doc)
    cache_services = {
        'housing': 0,
        'other': 0,
        'communal': 0,
        'capital_repair': 0,
        'cold_water': 0,
        'hot_water': 0,
        'heat_water_other': 0,
        'heat': 0,
        'electricity': 0,
        'cold_water_public': 0,
        'hot_water_public': 0,
        'electricity_public': 0,
        'waste_water': 0,
        'gas': 0,
        'communal_other_services': 0,
        'penalties': 0,
    }
    services_funcs = SERVICE_GROUP_CACHE_FUNCS
    cache_service_ids = {
        'cold_water': services_funcs['cold_water'](doc),
        'hot_water': services_funcs['hot_water'](doc),
        'heat_water_other': services_funcs['heat_water'](doc),
        'heat': services_funcs['heat'](doc),
        'electricity': services_funcs['electricity'](doc),
        'cold_water_public': services_funcs['cold_water_public'](doc),
        'hot_water_public': services_funcs['hot_water_public'](doc),
        'electricity_public': services_funcs['electricity_public'](doc),
        'waste_water': services_funcs['waste_water'](doc),
        'gas': services_funcs['gas'](doc),
    }
    communal_services = doc.get_services_by_head_type('communal_services')
    cache_groups = {
        'housing': get_groups_list(0),
        'communal': get_groups_list(1),
        'other': get_groups_list(2),
        'capital_repair': get_groups_list(3),
    }
    all_communal = 0
    for debt in accruals:
        cache_services['penalties'] += debt['totals']['penalties']
        for service in debt['services']:
            # TODO: Удалить после миграции поля result
            if 'result' not in service:
                service['result'] = (
                        service['value']
                        + service['totals']['recalculations']
                        + service['totals']['shortfalls']
                        + service['totals']['privileges']
                )

            for cache_name, service_ids in cache_service_ids.items():
                if service['service_type'] in service_ids:
                    cache_services[cache_name] += service['result']
            for cache_name, groups in cache_groups.items():
                if st_groups.get(service['service_type'], 2) in groups:
                    cache_services[cache_name] += service['result']
            if service['service_type'] in communal_services:
                all_communal += service['result']
    cache_services['communal_other_services'] = (
            cache_services['communal']
            - all_communal
    )
    cache_services['heat_water_other'] = (
            cache_services['heat_water_other']
            - cache_services['hot_water']
            - cache_services['hot_water_public']
    )
    AccrualDoc.objects(
        pk=doc_id,
    ).update(
        cache_services=cache_services,
        caching_wip=False,
    )
    if parent_task_id:
        from app.accruals.models.tasks import HousesCalculateTask
        HousesCalculateTask.check_caching_state(parent_task_id)
    resum_services(doc_id)
    for bind in doc.doc_m.sector_binds:
        update_house_accruals_cache.delay(
            provider_id=bind.provider,
            house_id=doc.doc_m.house.id,
            month=start_of_month(doc.doc_m.date_from),
            sector=bind.sector_code,
        )


def resum_services(doc_id):
    """
    Пересчитывает кэшированные суммарные данные квитанций.
    На самом деле просто удаляет, чтобы они потом сами пересчитались
    """
    ReceiptAccrualCache.objects(
        accrual_doc=doc_id,
    ).update(
        values=[],
    )


def create_count_task(
        doc_id, count_type, print_type, filter_id=None, house_id=None
):
    cache_task = ReceiptsStatisticsCache.objects(
        doc_id=doc_id,
        count_type=count_type,
    ).first()
    if not cache_task:
        cache_task = ReceiptsStatisticsCache(
            doc_id=doc_id,
            count_type=count_type,
        )
    if print_type:
        cache_task.print_type = print_type
    if filter_id:
        cache_task.filter_id = filter_id
    if house_id:
        cache_task.house_id = house_id
    cache_task.state = 'new'
    cache_task.save()
    count_receipts_statistics.delay(task_id=cache_task.id)
    return cache_task.id


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 5 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30
)
def count_receipts_statistics(self, task_id):
    statistics = ReceiptsStatisticsCache.objects.get(id=task_id)
    try:
        statistics.count_statistics()
    except Exception as error:
        statistics.error_message = str(error)
        statistics.state = 'failed'
        statistics.save()
    return statistics.state
