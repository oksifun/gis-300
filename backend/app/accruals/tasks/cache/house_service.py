import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.accruals.models.accrual_document import AccrualDoc
from app.accruals.models.cache import (
    AccrualHouseServiceCache,
    AccrualHouseServiceCacheMethod,
    ACCRUAL_HOUSE_SERVICE_CACHE_METHODS_CHOICES, AccrualHouseServiceCacheTask,
)
from app.celery_admin.workers.config import celery_app
from lib.dates import start_of_month
from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.accrual import Accrual
from settings import CELERY_SOFT_TIME_MODIFIER


_OLD_PENALTY_SERVICE_TYPE = ObjectId('0' * 24)


def init_house_service_cache_update(house_id, month_from,
                                    provider_id=None,
                                    direct_update=False):
    clean_house_services_cache(house_id, month_from, provider_id)
    if direct_update:
        update_house_services_cache(house_id, month_from, provider_id)
    else:
        AccrualHouseServiceCacheTask.add_task(
            house_id,
            month_from,
            provider_id,
        )


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 12 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30,
)
def run_house_services_cache_tasks(self):
    tasks = AccrualHouseServiceCacheTask.objects.all()
    for task in tasks:
        update_house_services_cache.delay(task.house, task.month, task.provider)
        task.delete()


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 12 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30,
)
def update_house_services_cache(self, house_id, month_from, provider_id=None):
    try:
        if datetime.datetime.now().hour > 7:
            raise Exception('Out of time')
        _update_house_services_cache(house_id, month_from, provider_id)
    except Exception as exc:
        AccrualHouseServiceCacheTask.add_task(
            house_id,
            month_from,
            provider_id,
        )
        raise exc


def _update_house_services_cache(house_id, month_from, provider_id=None):
    if provider_id:
        providers = [provider_id]
    else:
        providers = AccrualDoc.objects(
            house__id=house_id,
        ).distinct(
            'sector_binds.provider',
        )
    for provider in providers:
        calculator = HouseServiceCacheCalculator(
            provider_id=provider,
            house_id=house_id,
            month_from=start_of_month(month_from),
        )
        calculator.set_up()
        calculator.calculate()
    return 'success'


def clean_house_services_cache(house_id, month_from,
                               provider_id=None, method=None):
    queryset = AccrualHouseServiceCache.objects(
        house=house_id,
        month__gte=month_from,
    )
    if method:
        queryset = queryset.filter(method=method)
    if provider_id:
        queryset = queryset.filter(owner=provider_id)
    queryset.delete()


class HouseServiceCacheCalculator:

    def __init__(self, provider_id, house_id, month_from):
        self.provider = provider_id
        self.house = house_id
        self.month_from = month_from
        self.months = []
        self.prev_month_data = {}
        self._start_month = None

    def set_up(self):
        self.months = self._get_months_to_recache()
        self.prev_month_data = self._get_prev_month_data(self.months[0])
        if self.prev_month_data:
            self._start_month = self.months[0]

    def calculate(self):
        month_from = self._start_month
        for month in self.months:
            self._calculate_month(month, month_from)
            month_from = month

    def _calculate_month(self, month, month_from):
        for method, _name in ACCRUAL_HOUSE_SERVICE_CACHE_METHODS_CHOICES:
            date_match = self._get_date_match(method, month, month_from)
            accruals = self._get_accruals(date_match, method)
            self._update_data_by_prev_cache(accruals, method)
            self._clean_month(month, method)
            self._save_cache_data(month, accruals)
            self._save_data_as_prev_cache(accruals, method)

    def _clean_month(self, month, method):
        clean_house_services_cache(self.house, month, self.provider, method)

    def _save_cache_data(self, month, accrual_data):
        for key, data in accrual_data.items():
            doc = AccrualHouseServiceCache.objects(
                owner=self.provider,
                house=self.house,
                month=month,
                sector=key[0],
                service=key[1],
                area_type=key[2],
                is_developer=key[3],
                account_type=key[4],
                method=key[5],
            ).upsert_one(
                value=data[0],
                debt=data[1],
            )
            if not doc.has_binds():
                doc.save()

    def _update_data_by_prev_cache(self, accruals_data, method):
        for key, data in self.prev_month_data.items():
            if key[5] != method:
                continue
            accruals_data.setdefault(key, [0, 0])
            accruals_data[key][0] += data[0]
            accruals_data[key][1] += data[1]

    def _save_data_as_prev_cache(self, accruals_data, method):
        for key, data in accruals_data.items():
            key_prev = (
                key[0],
                key[1],
                key[2],
                key[3],
                key[4],
                method,
            )
            self.prev_month_data[key_prev] = data

    _METHOD_DATE_KEYS = {
        AccrualHouseServiceCacheMethod.BY_MONTH: 'month',
        AccrualHouseServiceCacheMethod.BY_DOC_DATE: 'doc.date',
    }

    def _get_date_match(self, method, month, month_from=None):
        key = self._METHOD_DATE_KEYS[method]
        result = {key: {'$lt': month}}
        if month_from:
            result[key]['$gte'] = month_from
        return result

    def _get_prev_month_data(self, month):
        prev_cache = AccrualHouseServiceCache.objects(
            house=self.house,
            owner=self.provider,
            month=month - relativedelta(months=1),
        ).as_pymongo()
        result = {}
        for data in prev_cache:
            key = (
                data['sector'],
                data['service'],
                data['area_type'],
                data['is_developer'],
                data['account_type'],
                data['method'],
            )
            result[key] = [data['value'], data['debt']]
        return result

    def _get_months_to_recache(self):
        months = AccrualHouseServiceCache.objects(
            house=self.house,
            month__gte=self.month_from,
            owner=self.provider,
            last_used__gt=datetime.datetime.now() - relativedelta(months=1),
        ).distinct('month')
        current_months = start_of_month(datetime.datetime.now())
        near_months = {
            current_months,
            current_months - relativedelta(months=1),
        }
        months = list(set(months) | near_months)
        months.sort()
        return months

    def _get_accruals(self, date_match, method):
        match = {
            'owner': self.provider,
            'account.area.house._id': self.house,
            'is_deleted': {'$ne': True},
            'doc.status': {'$in': CONDUCTED_STATUSES},
            **date_match,
        }
        queryset = Accrual.objects(__raw__=match)
        services_queryset = self._aggregate_services(queryset)
        result = {}
        for data in services_queryset:
            key = (
                data['_id']['sector'],
                data['_id']['service'],
                data['_id']['area_type'],
                data['_id']['is_developer'],
                data['_id']['account_type'],
                method,
            )
            result[key] = [data['value_p'] + data['value_n'], data['value_p']]
        penalties_queryset = self._aggregate_penalties(queryset)
        for data in penalties_queryset:
            key = (
                data['_id']['sector'],
                _OLD_PENALTY_SERVICE_TYPE,
                data['_id']['area_type'],
                data['_id']['is_developer'],
                data['_id']['account_type'],
                method,
            )
            result[key] = [data['value_p'] + data['value_n'], data['value_p']]
        return result

    @staticmethod
    def _aggregate_services(queryset):
        return queryset.aggregate(
            {
                '$project': {
                    'area_type': {'$arrayElemAt': ["$account.area._type", 0]},
                    'account_type': {'$arrayElemAt': ["$account._type", 0]},
                    'is_developer': "$account.is_developer",
                    'services': 1,
                    'sector_code': 1,
                },
            },
            {
                '$unwind': '$services',
            },
            {
                '$project': {
                    'value': {
                        '$add': [
                            '$services.value',
                            '$services.totals.shortfalls',
                            '$services.totals.privileges',
                            '$services.totals.recalculations'
                        ],
                    },
                    'service': '$services.service_type',
                    'sector_code': 1,
                    'area_type': {
                        '$cond': [
                            {'$eq': ['$area_type', 'CommunalArea']},
                            'LivingArea',
                            '$area_type',
                        ],
                    },
                    'account_type': 1,
                    'is_developer': 1,
                },
            },
            {
                '$project': {
                    'service': 1,
                    'sector_code': 1,
                    'area_type': 1,
                    'account_type': 1,
                    'is_developer': {'$ifNull': ['$is_developer', False]},
                    'value_p': {
                        '$cond': {
                            'if': {'$gte': ['$value', 0]},
                            'then': '$value',
                            'else': {'$literal': 0},
                        },
                    },
                    'value_n': {
                        '$cond': {
                            'if': {'$lt': ['$value', 0]},
                            'then': '$value',
                            'else': {'$literal': 0},
                        },
                    },
                },
            },
            {
                '$group': {
                    '_id': {
                        'service': '$service',
                        'sector': '$sector_code',
                        'area_type': '$area_type',
                        'account_type': '$account_type',
                        'is_developer': '$is_developer',
                    },
                    'value_p': {'$sum': '$value_p'},
                    'value_n': {'$sum': '$value_n'},
                },
            },
        )

    @staticmethod
    def _aggregate_penalties(queryset):
        return queryset.aggregate(
            {
                '$project': {
                    'area_type': {'$arrayElemAt': ["$account.area._type", 0]},
                    'account_type': {'$arrayElemAt': ["$account._type", 0]},
                    'is_developer': "$account.is_developer",
                    'services': 1,
                    'sector_code': 1,
                    'totals.penalties': 1,
                },
            },
            {
                '$project': {
                    'sector_code': 1,
                    'area_type': 1,
                    'account_type': 1,
                    'is_developer': {'$ifNull': ['$is_developer', False]},
                    'value_p': {
                        '$cond': {
                            'if': {
                                '$gte': ['$totals.penalties', 0]
                            },
                            'then': '$totals.penalties',
                            'else': {'$literal': 0},
                        },
                    },
                    'value_n': {
                        '$cond': {
                            'if': {
                                '$lt': ['$totals.penalties', 0]
                            },
                            'then': '$totals.penalties',
                            'else': {'$literal': 0},
                        },
                    },
                },
            },
            {
                '$group': {
                    '_id': {
                        'sector': '$sector_code',
                        'area_type': '$area_type',
                        'account_type': '$account_type',
                        'is_developer': '$is_developer',
                    },
                    'value_p': {'$sum': '$value_p'},
                    'value_n': {'$sum': '$value_n'},
                },
            },
        )
