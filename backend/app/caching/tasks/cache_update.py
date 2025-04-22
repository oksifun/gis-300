from datetime import datetime

import settings
from app.caching.core.accruals import get_house_accruals
from app.caching.core.references import PREPARE_FUNCS
from app.caching.models.filters import FilterCache
from app.celery_admin.workers.config import celery_app
from lib.dates import total_seconds, start_of_month
from app.personnel.models.personnel import Worker
from processing.models.billing.tariff_plan import TariffsTree
from app.caching.models.cache_lock import CacheLock
from app.caching.models.house_accruals import HouseAccrualsCached, \
    HouseServiceAccrualsCached
from app.caching.models.fias_tree import AccountFiasTree, \
    FiasTreeAccountError
from app.caching.core.metabase import get_stat


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=60)
)
def update_tariffs_cache(self, provider_id):
    if not _lock_cache_use(model='TariffsTree', obj=provider_id):
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=round(self.soft_time_limit / (self.max_retries - 1)))
    tree = TariffsTree.objects.get(provider=provider_id)
    tree.update_cache()
    return 'success'


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=180),
    default_retry_delay=30,
)
def update_house_accruals_cache(self, provider_id, house_id, month, sector):
    # заблокируем использование кэша по дому
    if self and not _lock_cache_use(model='HouseAccrualsCached', obj=house_id):
        if self.request.retries < self.max_retries:
            raise self.retry()
    try:
        accruals = get_house_accruals(provider_id, house_id, month, sector)
        # сохраняем новый кэш
        for filter_name, data in accruals.items():
            services_cache = []
            for s_type, values in data['services'].items():
                services_cache.append(
                    HouseServiceAccrualsCached(
                        service=s_type,
                        total=values['t'],
                        debt=values['d'],
                        value=values['v'],
                        recalculations=values['r'],
                        shortfalls=values['s'],
                        privileges=values['p'],
                        consumption=values['c'],
                        tariff=values['tar'],
                    ),
                )
            HouseAccrualsCached.objects(
                provider=provider_id,
                house=house_id,
                sector=sector,
                accounts_filter=filter_name,
                month=month,
            ).upsert_one(
                services=services_cache,
                penalties=data['penalties'],
            )
    finally:
        if self:
            _unlock_cache_use(model='HouseAccrualsCached', obj=house_id)
    return 'success v{}'.format(settings.RELEASE)


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=120),
)
def create_fias_tree_cache(self, provider_id, account_id=None):
    """
    Создание дерева ФИАСа по следующим триггерам:
        1. Добавление/удаление дома в правах сотрудника.
        2. Добавление/удаление привязки организации к дому.
    """
    query = (
        dict(provider=provider_id, account=account_id)
        if account_id
        else dict(provider=provider_id)
    )
    acc_tree = AccountFiasTree.objects(**query).first()
    try:
        if acc_tree:
            # Если уже есть
            acc_tree.save()
        else:
            # Если нет
            AccountFiasTree(**query).save()
    except FiasTreeAccountError:
        return 'permissions error'
    return 'success'


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=60),
)
def create_provider_fias_tree_cache(self, provider_id):
    """
    Создание дерева ФИАСа по следующим триггерам:
        1. Добавление/удаление дома в правах сотрудника.
        2. Добавление/удаление привязки организации к дому.
    """
    # Строим дерево для организации
    prov_tree = AccountFiasTree.objects(
        provider=provider_id,
        account__exists=False
    ).first()
    if prov_tree:
        # Если уже есть
        prov_tree.save()
    else:
        # Если нет
        AccountFiasTree(provider=provider_id, account=None).save()
    # пересчитать сотрудников
    workers = Worker.objects(
        provider__id=provider_id,
        _type='Worker',
        has_access=True,
        is_deleted__ne=True,
    ).distinct('id')
    for worker in workers:
        create_fias_tree_cache.delay(provider_id, worker)
    return 'success'


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=180),
    default_retry_delay=30,
)
def prepare_filter_cache(self, filter_id):
    filt = FilterCache.objects(pk=filter_id).only('id', 'purpose').get()
    if filt.purpose and filt.purpose in PREPARE_FUNCS:
        for func in PREPARE_FUNCS[filt.purpose]:
            func.delay(filter_id)


def _lock_cache_use(model, obj):
    existing_lock = CacheLock.objects(model=model, obj=obj).as_pymongo().first()
    if existing_lock:
        return False
    else:
        CacheLock(model=model, obj=obj).save()
        return True


def _unlock_cache_use(model, obj):
    CacheLock.objects(model=model, obj=obj).delete()


@celery_app.task(
    soft_time_limit=60 * 5,
    bind=True
)
def non_sber_registry_stat(self, provider_id):
    """
    Подстчет статистики по организациям без реестров Сбер
    """
    date_till = datetime.now()
    date_from = start_of_month(date_till)
    get_stat(date_from, date_till)
    return 'success'
