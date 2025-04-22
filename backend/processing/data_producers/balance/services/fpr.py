from lib.helpfull_tools import DateHelpFulls as dhf
from processing.data_producers.associated.services import PENALTY_SERVICE_TYPE
from processing.data_producers.balance.services.accounts import \
    AccountServicesBalance
from processing.models.billing.accrual import Accrual
from app.offsets.models.offset import Offset


class ServicesBalanceFprReport:
    """
    Методы рассчета Сальдо и оборотов по услугам по жителю
    для отчета 'Копия ФЛС'
    """

    def __init__(self,
                 date_from,
                 date_till,
                 tenant_id,
                 sectors: list,
                 account_types: list,
                 by_bank: bool,
                 area_types: list,
                 is_developer: bool,
                 binds=None):
        """
        :param date_from: начало рассчетного периода
        :param date_till: конец рассчетного периода
        :param tenant_id: id жителя
        :param sectors: направления
        """
        self.date_from = dhf.start_of_day(date_from)
        self.date_till = dhf.start_of_day(date_till)
        self.sectors = sectors
        self.tenant_id = tenant_id
        self.by_bank = by_bank
        self.area_types = area_types
        self.is_developer = is_developer
        self.account_types = account_types
        self.binds = binds
        self.balance = \
            AccountServicesBalance(binds, tenant_id, sectors, by_bank)

    def get_service_balance(self):
        """
        Получение начального сальдо по услугам на дату
        :return: dict: начисления по услугам для домов
        """
        return self.balance.get_balance(self.date_from)

    def get_service_debit(self):
        """
        Получение дебета для списка ЛС по услуге
        :return: dict: начисления по услуге для аккаунтов
        """
        # Получение положительных начислений за период отчета
        positive_accruals, viscera = self._get_service_accruals(period=True)
        # Получение возвратов
        repayments = self._get_service_refund_offsets()
        # Получаем Дебит вычитанием возвратов из начасленного
        debit = self.__operate_values(
            positive_accruals, repayments, subtract=False
        )
        return debit, viscera

    def get_service_credit(self):
        """
        Получение кредита для списка ЛС по услуге
        :return: list: начисления по услуге для аккаунтов
        """
        # Получение платежей с датой погашения, входящей в период отчета
        turnovers = self.balance.get_credit_turnovers(
            self.date_from,
            self.date_till,
        )
        return turnovers

    def _get_service_accruals(self, period: bool=False):
        """
        Получение итого положительных начислений для списка аккаунтов
        на дату или выбранный период
        :param: period: если True, значит будет поиск за период отчета
        :param: negative: если True, значит будет отрицательных начислений
        :return: dict: начисления по услуге для аккаунтов
        """
        match = {
                '$match': {
                    'is_deleted': {'$ne': True},
                    'doc.status': {'$in': ['ready', 'edit']},
                    'account._id': self.tenant_id,
                }
            }
        # Задаем критерии поиска в зависимости от условий (добавляем фильтры)
        match = self.base_accruals_filters(match, period)

        balance_filter = {
            '$cond': {
                'if': {'$gte': ['$value', 0]},
                'then': '$value',
                'else': {'$literal': 0},
            }
        }
        no_filter = '$value'

        query_pipeline = [
            match,
            {'$project': {
                'services': 1,
                'tariff_plan': 1,
                'doc.date': 1
            }},
            {'$sort': {'doc.date': 1}},
            {'$unwind': '$services'},
            {'$project': {
                'value': {'$add': [
                    '$services.value',
                    '$services.totals.shortfalls',
                    '$services.totals.privileges',
                    '$services.totals.recalculations'
                ]},
                'service_type': '$services.service_type',
                'shortfalls': '$services.totals.shortfalls',
                'privileges': '$services.totals.privileges',
                'recalculations': '$services.totals.recalculations',
                'tariff': '$services.tariff',
                'consumption': '$services.consumption',
                'norma': '$services.norma',
                'tariff_plan': 1
            }},
            {'$project': {
                'service_type': 1,
                'value_p': no_filter if period else balance_filter,
                'shortfalls': 1,
                'privileges': 1,
                'recalculations': 1,
                'tariff': 1,
                'consumption': 1,
                'norma': 1,
                'tariff_plan': 1
            }},
            {'$group': {
                '_id': '$service_type',
                'value_p': {'$sum': '$value_p'},
                'shortfalls': {'$sum': '$shortfalls'},
                'privileges': {'$sum': '$privileges'},
                'recalculations': {'$sum': '$recalculations'},
                'tariff': {'$last': '$tariff'},
                'consumption': {'$first': '$consumption'},
                'norma': {'$first': '$norma'},
                'tariff_plan': {'$addToSet': '$tariff_plan'}
                }}
        ]
        result = list(Accrual.objects.aggregate(*query_pipeline))
        penalty = self._get_service_penalties(period)
        if not period:
            result = {x['_id']: x['value_p'] for x in result if x['value_p']}
            if penalty:
                result[PENALTY_SERVICE_TYPE] = penalty
        else:
            result = (
                {x['_id']: x['value_p'] for x in result if x['value_p']},
                {x['_id']: x for x in result if x['value_p']}
            )
            if penalty:
                result[0][PENALTY_SERVICE_TYPE] = penalty
                result[1][PENALTY_SERVICE_TYPE] = {
                    'value_p': penalty,
                }
        return result

    def _get_service_penalties(self, period: bool=False):
        """
        Получение итого положительных начислений пени для списка аккаунтов
        на дату или выбранный период
        :param: period: если True, значит будет поиск за период отчета
        :param: negative: если True, значит будет отрицательных начислений
        :return: dict: начисления по услуге для аккаунтов
        """
        match = {
                '$match': {
                    'is_deleted': {'$ne': True},
                    'doc.status': {'$in': ['ready', 'edit']},
                    'account._id': self.tenant_id,
                }
            }
        # Задаем критерии поиска в зависимости от условий (добавляем фильтры)
        match = self.base_accruals_filters(match, period)

        balance_filter = {
            '$cond': {
                'if': {'$gte': ['$value', 0]},
                'then': '$value',
                'else': {'$literal': 0},
            }
        }
        no_filter = '$value'

        query_pipeline = [
            match,
            {'$project': {
                'value': '$totals.penalties',
            }},
            {'$project': {
                'value_p': no_filter if period else balance_filter,
            }},
            {'$group': {
                '_id': '',
                'value_p': {'$sum': '$value_p'},
            }}
        ]
        result = list(Accrual.objects.aggregate(*query_pipeline))
        return sum(x['value_p'] for x in result)

    def _get_offsets(self):
        """
        Поиск оффсетов
        :return: dict: оффсеты по услуге по лицевым счетам
        """
        match = {
            '$match': {
                    'accrual.date': {'$lt': self.date_from},
                    'refer.account._id': self.tenant_id,
                    'is_self_repaid': {'$ne': True}
                }
        }
        if self.by_bank:
            match['$match'].update({
                'refer.doc.date': {
                    '$lt': self.date_from
                },
            })
        else:
            match['$match'].update({
                'refer.date': {
                    '$lt': self.date_from
                },
            })
        # Задаем критерии поиска в зависимости от условий (добавляем фильтры)
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {
                '$project': {
                    'services': 1,
                }
            },
            {'$unwind': '$services'},
            {'$project': {
                'value': '$services.value',
                'service_type': '$services.service_type'
            }},
            {'$group': {
                '_id': '$service_type',
                'value': {'$sum': '$value'},
            }}
        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        return {x['_id']: x['value'] for x in result if x['value']}

    def _get_service_refund_offsets(self):
        """
        Получение возвратов, у которых дата погашения (refer.doc.date)
        находится в периоде отчета
        и больше или равна даты начисления (accrual.doc.date)
        и датой погашенного начисления в периоде отчета (accrual.doc.date)
        со значением "-"
        :return: list: возвраты по услуге для аккаунтов
        """
        return {k: -v for k, v in self._get_service_offsets('Refund').items()}

    def _get_service_repayment_offsets(self):
        """
        Получение оплат, у которых дата погашения (refer.doc.date)
        находится в периоде отчета
        и больше или равна даты погашенного начисления (accrual.doc.date)
        и датой погашенного начисления в периоде отчета (accrual.doc.date)
        со значением "+"
        :return: dict: возвраты по услуге для аккаунтов
        """
        return self._get_service_offsets('Repayment')

    def _get_service_offsets(self, offsets_type: str):
        match = {
            '$match': {
                '_type': offsets_type,
                'accrual.date': {'$lt': self.date_till},
                'refer.account._id': self.tenant_id,
                'is_self_repaid': {'$ne': True}
            }
        }
        if self.by_bank:
            match['$match'].update({
                'refer.doc.date': {
                    '$gte': self.date_from,
                    '$lt': self.date_till
                },
            })
        else:
            match['$match'].update({
                'refer.date': {
                    '$gte': self.date_from,
                    '$lt': self.date_till
                },
            })
        # Задаем критерии поиска в зависимости от условий (добавляем фильтры)
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {
                '$project': {
                    'services': {
                        '$cond': {
                            'if': {'$gte': ['$refer.date', '$accrual.date']},
                            'then': '$services',
                            'else': {'$literal': 0},
                        },
                    },
                }
            },
            {'$unwind': '$services'},
            {'$group': {
                '_id': '$services.service_type',
                'value': {'$sum': '$services.value'},
            }}

        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        return {x['_id']: x['value'] for x in result}

    def _get_service_repayment_advance(self):
        """
        Получение погашений аванса, у которых дата погешения (refer.doc.date)
        меньше конца периода отчета
        и меньше даты погашенного начисления (accrual.doc.date)
        и с датой погашенного начисления в периоде отчета (accrual.doc.date)
        :return: dict: возвраты по услуге для аккаунтов
        """
        match = {
            '$match': {
                'accrual.date': {'$lt': self.date_till, '$gt': self.date_from},
                'refer.account._id': self.tenant_id,
            }
        }
        # Задаем критерии поиска в зависимости от условий (добавляем фильтры)
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {'$project': {
                'services': {
                    '$cond': {
                        'if': {'$lt': ['$refer.doc.date', '$accrual.date']},
                        'then': '$services',
                        'else': {'$literal': 0},
                    },
                },
            }},
            {'$unwind': '$services'},
            {'$project': {
                'value': '$services.value',
                'service_type': '$services.service_type'
            }},
            {'$group': {
                '_id': '$service_type',
                'value': {'$sum': '$value'},
            }}
        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        return {x['_id']: x['value'] for x in result}

    def __operate_values(self,
                         accruals: dict,
                         offsets: dict,
                         subtract: bool):
        """
        Получение результирующей путем вычитания велечин
        из двух списков, но одной услуги
        :param accruals: начислния
        :param offsets: погашения, оплаты и т.д.
        :param subtract: вычитание
        :return: dict: результат для аккаунтов
                       {account_id: final_value, ...}
        """
        result = dict()
        all_services = list(set(accruals) | set(offsets))
        for service in all_services:
            if subtract:
                s_b = accruals.get(service, 0) - offsets.get(service, 0)
                if s_b:
                    result.update({service: s_b})
            else:
                result.update({
                    service: dict(
                        first=accruals.get(service, 0),
                        second=offsets.get(service, 0)
                    )
                })

        return result

    def base_offset_filters(self, match: dict):
        """
        Добавление базовых поисковых фильтров агрегации
        для коллекции Offset
        :param match: фильтр первого агрегационного запроса
        :return: модифицированный match
        """
        # Задаем критерии поиска в зависимости от условий
        if self.sectors:
            match['$match']['refer.sector_code'] = {'$in': self.sectors}
        if self.area_types:
            match['$match'].update(
                {'refer.account.area._type': {"$in": self.area_types}}
            )
        if self.is_developer:
            match['$match'].update({'refer.account.is_developer': True})
        elif self.is_developer is False:
            match['$match'].update(
                {'refer.account.is_developer': {'$ne': True}}
            )
        if self.account_types:
            match['$match'].update(
                {'refer.account._type': {"$in": self.account_types}}
            )
        if self.binds:
            match['$match'].update(Offset.get_binds_query(self.binds, raw=True))
        return match

    def base_accruals_filters(self, match: dict, period: bool=False):
        """
        Добавление базовых поисковых фильтров агрегации
        для коллекции Accruals
        :param period: если передан, значит будет поиск за период отчета
        :param match: фильтр первого агрегационного запроса
        :return: модифицированный match
        """
        if self.binds:
            match['$match'].update(
                Accrual.get_binds_query(self.binds, raw=True)
            )
        # Задаем критерии поиска в зависимости от условий
        if self.sectors:
            match['$match']['sector_code'] = {'$in': self.sectors}
        # если передана дата начала периода
        if period:
            match['$match']['doc.date'] = {'$lt': self.date_till,
                                           '$gte': self.date_from}
        else:
            match['$match']['doc.date'] = {'$lt': self.date_from}
        if self.area_types:
            match['$match'].update(
                {'account.area._type': {"$in": self.area_types}}
            )
        if self.is_developer:
            match['$match'].update({'account.is_developer': True})
        elif self.is_developer is False:
            match['$match'].update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match['$match'].update(
                {'account._type': {"$in": self.account_types}}
            )
        return match
