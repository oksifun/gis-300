import datetime
import logging
from copy import copy

from app.accruals.models.cache import AccrualHouseServiceCacheMethod, \
    AccrualHouseServiceCache
from lib.dates import start_of_month
from processing.data_producers.balance.services.base import ServicesBalanceBase

logger = logging.getLogger('c300')


class HousesServicesBalance(ServicesBalanceBase):
    """Методы рассчета Сальдо и оборотов по услугам по домам"""

    def __init__(self,
                 binds,
                 houses_ids: list,
                 account_types=None,
                 area_types=None,
                 is_developer=False,
                 sectors=None,
                 by_bank=True):
        """
        :param houses_ids: список домов
        :param account_types: необязательно, типы собственников
        :param area_types: необязательно, типы помещений
        :param is_developer: необязательно, признак застройщика
        """
        super().__init__(
            binds=binds,
            sectors=sectors,
            by_bank=by_bank,
        )
        self.houses = houses_ids
        self.account_types = account_types
        self.area_types = area_types
        self.is_developer = is_developer

    def _get_custom_accruals_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Accrual по домам
        """
        match = {
            'account.area.house._id': {'$in': self.houses},
        }
        if self.area_types:
            match.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'account.is_developer': True})
        elif self.is_developer is False:
            match.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'account._type': self.account_types})
        return match

    def _get_custom_offsets_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Offsets по домам
        """
        match = {
            'refer.account.area.house._id': {'$in': self.houses},
        }
        if self.area_types:
            match.update({'refer.account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'refer.account.is_developer': True})
        elif self.is_developer is False:
            match.update({'refer.account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'refer.account._type': self.account_types})
        return match

    def _get_custom_payments_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Payment по домам
        """
        match = {
            'account.area.house._id': {'$in': self.houses},
        }
        if self.area_types:
            match.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'account.is_developer': True})
        elif self.is_developer is False:
            match.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'account._type': self.account_types})
        return match

    def _get_service_accruals(self, match):
        cache_match = self._convert_accrual_match_to_house_cache(match)
        if not cache_match:
            return super()._get_service_accruals(match)
        data = self._get_service_accruals_by_cache(cache_match)
        if data:
            if len(data[2]) == len(cache_match['house']['$in']):
                if cache_match['month'] != match['doc.date']['$lt']:
                    return self._update_cache_data_by_inmonth_data(data, match)
                return data[0], data[1], {}
            else:
                self._house_cache_update(
                    set(cache_match['house']['$in']) - data[2],
                    cache_match['month'],
                )
        else:
            self._house_cache_update(
                cache_match['house']['$in'],
                cache_match['month'],
            )
        return super()._get_service_accruals(match)

    def _update_cache_data_by_inmonth_data(self, cache_data, match):
        inmonth_match = copy(match)
        inmonth_match['doc.date'] = {
            '$gte': start_of_month(match['doc.date']['$lt']),
            '$lt': match['doc.date']['$lt'],
        }
        inmonth_data = super()._get_service_accruals(inmonth_match)
        pos_accruals = cache_data[0]
        neg_accruals = cache_data[1]
        for key, value in inmonth_data[0].items():
            pos_accruals.setdefault(key, 0)
            pos_accruals[key] += value
        for key, value in inmonth_data[1].items():
            neg_accruals.setdefault(key, 0)
            neg_accruals[key] += value
        return pos_accruals, neg_accruals, inmonth_data[2]

    @staticmethod
    def _house_cache_update(houses, month):
        from app.accruals.tasks.cache.house_service import \
            init_house_service_cache_update
        for house in houses:
            init_house_service_cache_update(
                house,
                month,
            )

    def _get_service_accruals_by_cache(self, match):
        date = datetime.datetime.now()
        query = self._get_accruals_cache_query(match)
        result = list(
            query.aggregate(
                *self._get_accruals_cache_aggregation_pipeline(),
            ),
        )
        data = {d['_id']: (d['debt'], d['value'] - d['debt']) for d in result}
        if not data:
            return None
        logger.debug(
            '=========  AccrualHouseServiceCache.aggregate %s',
            datetime.datetime.now() - date,
        )
        houses = {h for d in result for h in d['houses']}
        positive_accruals = {k: v[0] for k, v in data.items() if v[0]}
        self._change_penalty_service_types(positive_accruals)
        negative_accruals = {k: v[1] for k, v in data.items() if v[1]}
        self._change_penalty_service_types(negative_accruals)
        return positive_accruals, negative_accruals, houses

    @staticmethod
    def _get_accruals_cache_aggregation_pipeline():
        return [
            {
                '$group': {
                    '_id': '$service',
                    'value': {'$sum': '$value'},
                    'debt': {'$sum': '$debt'},
                    'houses': {'$addToSet': '$house'},
                },
            },
        ]

    @staticmethod
    def _get_accruals_cache_query(match):
        return AccrualHouseServiceCache.objects(__raw__=match)

    @staticmethod
    def _convert_accrual_match_to_house_cache(match):
        result = {}
        for key, value in match.items():
            if 'doc.date' in key:
                if '$gte' in value:
                    return None
                result['month'] = start_of_month(value['$lt'])
                result['method'] = AccrualHouseServiceCacheMethod.BY_DOC_DATE
            elif 'house._id' in key:
                result['house'] = value
            elif 'account.area._type' in key:
                result['area_type'] = value
            elif 'account.is_developer' in key:
                result['is_developer'] = value
            elif 'account._type' in key:
                result['account_type'] = value
            elif 'sector_code' in key:
                result['sector'] = value
            elif '_binds.pr' in key:
                result['_binds.pr'] = value
            elif key in ['is_deleted', 'doc.status']:
                pass
            else:
                return None
        return result
