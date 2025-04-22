import copy
import datetime
import logging

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from processing.data_producers.associated.services import ADVANCE_SERVICE_TYPE, \
    PENALTY_SERVICE_TYPE
from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.accrual import Accrual
from processing.models.billing.account import Account
from app.offsets.models.offset import Offset, OffsetOperationAccount, \
    REFUND_OFFSET_OPERATIONS, CORRECTION_OFFSET_OPERATIONS, \
    ADVANCE_REPAYMENT_OFFSET_OPERATIONS, PAYMENT_OFFSET_OPERATIONS
from processing.models.billing.payment import Payment
from processing.models.billing.area_bind import AreaBind

_OLD_PENALTY_SERVICE_TYPE = ObjectId('0' * 24)
_USER_PENALTY_SERVICE_TYPE = ObjectId("526234c0e0e34c4743822339")
_PENALTY_SERVICE_TYPES_CHANGE = {
    _OLD_PENALTY_SERVICE_TYPE,
    _USER_PENALTY_SERVICE_TYPE,
}
_OLD_ADVANCE_SERVICE_TYPE = ObjectId('1' * 24)
logger = logging.getLogger('c300')


class ServiceBalance:
    """Методы рассчета Сальдо и оборотов по услуге"""

    def __init__(self,
                 date_from,
                 date_on,
                 account_ids: list,
                 service_type,
                 house_id=None,
                 sectors=None,
                 binds=None):
        """
        :param date_from: начало рассчетного периода
        :param date_on: конец рассчетного периода
        :param service_type: id услуги
        :param account_ids: список id лицевых счетов
        :param house_id: id дома (если передан, то документы ищутся по нему)
        :param sectors: направления
        """
        self.date_from = date_from
        self.date_on = date_on
        self.account_ids = account_ids
        self.service_type = service_type
        self.sectors = sectors
        self.binds = binds
        # Определение алгоритма поиска (по дому или ЛС ids)
        # Если не по дому, house_id станет None
        self.house_id = self.__select_algorithm(house_id)

    @staticmethod
    def get_house_accounts(provider_id, house_id, fields: list = None):
        """
        Метод получения списка всех лицевых
        счетов организации по определенному дому
        :param provider_id: организация
        :param house_id: дом
        :param fields: список необходимых полей
        :return: list
        """
        provider_areas = AreaBind.objects(provider=provider_id).distinct('area')
        if fields:
            accounts = Account.objects(
                area__house__id=house_id, area__id__in=provider_areas
            ).only(*fields).as_pymongo()
        else:
            accounts = Account.objects(
                area__house__id=house_id, area__id__in=provider_areas
            ).as_pymongo()
        return accounts

    def _get_house_accounts_count(self, house_id):
        """Определение количества ЛС по дому навскидку"""
        return Account.objects(area__house__id=house_id).count()

    def get_service_balance(self):
        """
        Получение начального сальдо по услуге на дату
        :return: dict: начисления по услуге для аккаунтов
                       {account_id: сальдо, ...}
        """
        # Получение всех положительных начислений с датой раньше даты отчета
        accruals = self._get_service_accruals()
        # Получение всех офсетов с датой погашения и начисления
        # раньше даты отчета
        offsets = self._get_offsets()
        # Получение сальдо
        result_dict = self.__operate_values(accruals, offsets, subtract=True)

        return result_dict

    def get_service_debit(self):
        """
        Получение дебета для списка ЛС по услуге
        :return: list: начисления по услуге для аккаунтов
        """
        # Получение положительных начислений за период отчета
        accruals = self._get_service_accruals(date_from=self.date_from,
                                              for_debit=True)
        # Получение возвратов
        repayments = self._get_service_repayments()

        # Получаем Дебит вычитанием возвратов из начасленного
        debit = self.__operate_values(accruals, repayments, subtract=False)
        return debit

    def get_service_credit(self):
        """
        Получение кредита для списка ЛС по услуге
        :return: list: начисления по услуге для аккаунтов
        """
        # Получение платежей с датой погашения, входящей в период отчета
        payments = self._get_service_payment_offsets()
        # Получение погашений авансов
        repayments_advance = self._get_service_repayment_advance()

        # Получаем Дебит вычитанием возвратов из начасленного
        credit = self.__operate_values(
            payments, repayments_advance, subtract=False
        )
        return credit

    def _get_service_accruals(self, date_from=None, for_debit=False):
        """
        Получение итого положительных начислений для списка аккаунтов
        на дату или выбранный период
        :param: date_from: если передан, значит будет поиск за период отчета
        :return: list: начисления по услуге для аккаунтов
        """
        match = {
            '$match': {
                'doc.date': {'$lt': self.date_from},
                'is_deleted': {'$ne': True},
                'doc.status': {'$in': ['ready', 'edit']},
            }
        }
        # Задаем критерии поиска в зависимости от условий
        if self.binds:
            match['$match'].update(
                Accrual.get_binds_query(self.binds, raw=True)
            )
        if self.house_id:
            match['$match']['account.area.house._id'] = self.house_id
        else:
            match['$match']['account._id'] = {'$in': self.account_ids}
        if self.sectors:
            match['$match']['sector_code'] = {'$in': self.sectors}
        # если передана дата начала периода
        if date_from:
            match['$match']['doc.date'] = {
                '$lt': self.date_on + relativedelta(days=1),
                '$gte': self.date_from,
            }

        query_pipeline = [
            match,
            {
                '$project': {
                    'doc_date': '$doc.date',
                    'month': 1,
                    'account': '$account._id',
                    'services': 1,
                }
            },
            {'$unwind': '$services'},
            {'$project': {
                'doc_date': 1,
                'month': 1,
                'account': 1,
                'value': {'$add': [
                    '$services.value',
                    '$services.totals.shortfalls',
                    '$services.totals.privileges',
                    '$services.totals.recalculations'
                ]},
                'service_type': '$services.service_type'
            }},
            {'$match': {'service_type': self.service_type}},
            {'$project': {
                'doc_date': 1,
                'month': 1,
                'account': 1,
                'value': 1,
            }},
            {'$group': {
                '_id': '$account',
                'detail': {'$push': {
                    'month': '$month',
                    'doc_date': '$doc_date',
                    'sub_value': '$value'}},
                'value': {'$sum': '$value'},
            }}
        ]

        result = list(
            Accrual.objects.aggregate(*query_pipeline, allowDiskUse=True))

        # Нужно отфильтровать ЛС, если поиск был по дому
        if self.house_id:
            result = {x['_id']: x for x in result}
            result = [result[x] for x in self.account_ids if result.get(x)]

        return result

    def _get_offsets(self):
        """
        Поиск оффсетов
        :return: list: оффсеты по услуге по лицевым счетам
        """
        match = {
            '$match': {
                'accrual.date': {'$lt': self.date_from},
                'refer.doc.date': {'$lt': self.date_from},
            }
        }
        # Задаем критерии поиска в зависимости от условий
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {
                '$project': {
                    'account': '$refer.account._id',
                    'services': 1,
                }
            },
            {'$unwind': '$services'},
            {'$project': {
                'account': 1,
                'value': '$services.value',
                'service_type': '$services.service_type'
            }},
            {'$match': {'service_type': self.service_type}},
            {'$group': {
                '_id': '$account',
                'value': {'$sum': '$value'},
            }}

        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        # Нужно отфильтровать ЛС, если поиск был по дому
        if self.house_id:
            result = {x['_id']: x for x in result}
            result = [result[x] for x in self.account_ids if result.get(x)]
        return result

    def _get_service_repayments(self):
        """
        Получение возвратов, у которых дата погешения (refer.doc.date)
        находится в периоде отчета
        и больше или равна даты начисления (accrual.doc.date)
        и датой погашенного начисления в периоде отчета (accrual.doc.date)
        со значением "-"
        :return: list: возвраты по услуге для аккаунтов
        """
        match = {
            '$match': {
                'accrual.date': {'$lt': self.date_on + relativedelta(days=1),
                                 '$gte': self.date_from},
                'refer.doc.date': {'$lt': self.date_on + relativedelta(days=1),
                                   '$gte': self.date_from}
            }
        }
        # Задаем критерии поиска в зависимости от условий
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {
                '$project': {
                    'doc_date': '$accrual.date',
                    'month': '$accrual.month',
                    'account': '$refer.account._id',
                    'services': {
                        '$cond': {
                            'if': {
                                '$gte': ['$refer.doc.date', '$accrual.date'],
                            },
                            'then': '$services',
                            'else': {'$literal': 0}
                        },
                    },
                }
            },
            {'$unwind': '$services'},
            {'$project': {
                'doc_date': 1,
                'month': 1,
                'account': 1,
                'value': {
                    '$cond': {
                        'if': {'$lt': ['$services.value', 0]},
                        'then': '$services.value',
                        'else': {'$literal': 0},
                    },
                },
                'service_type': '$services.service_type'
            }},
            {'$match': {'service_type': self.service_type}},
            {'$group': {
                '_id': '$account',
                'detail': {'$push': {
                    'month': '$month',
                    'doc_date': '$doc_date',
                    'sub_value': '$value'}},
                'value': {'$sum': '$value'},
            }}

        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        # Нужно отфильтровать ЛС, если поиск был по дому
        if self.house_id:
            result = {x['_id']: x for x in result}
            result = [result[x] for x in self.account_ids if result.get(x)]
        return result

    def _get_service_payment_offsets(self):
        """
        Получение оплат, у которых дата погашения (refer.doc.date)
        находится в периоде отчета
        и больше или равна даты погашенного начисления (accrual.doc.date)
        и датой погашенного начисления в периоде отчета (accrual.doc.date)
        со значением "+"
        :return: list: возвраты по услуге для аккаунтов
        """
        match = {
            '$match': {
                'accrual.date': {
                    '$lt': self.date_on + relativedelta(days=1)
                },
                'refer.doc.date': {
                    '$gte': self.date_from,
                    '$lt': self.date_on + relativedelta(days=1),
                }
            }
        }
        # Задаем критерии поиска в зависимости от условий
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {
                '$project': {
                    'doc_date': '$accrual.date',
                    'month': '$accrual.month',
                    'account': '$refer.account._id',
                    'services': {
                        '$cond': {
                            'if': {
                                '$gte': ['$refer.doc.date', '$accrual.date'],
                            },
                            'then': '$services',
                            'else': {'$literal': 0},
                        }
                    },
                }
            },
            {'$unwind': '$services'},
            {'$project': {
                'doc_date': 1,
                'month': 1,
                'account': 1,
                'value': '$services.value',
                'service_type': '$services.service_type'
            }},
            {'$match': {'service_type': self.service_type}},
            {'$group': {
                '_id': '$account',
                'detail': {'$push': {
                    'month': '$month',
                    'doc_date': '$doc_date',
                    'sub_value': '$value'}},
                'value': {'$sum': '$value'},
            }}

        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        # Нужно отфильтровать ЛС, если поиск был по дому
        if self.house_id:
            result = {x['_id']: x for x in result}
            result = [result[x] for x in self.account_ids if result.get(x)]
        return result

    def _get_service_repayment_advance(self):
        """
        Получение погашений аванса, у которых дата погешения (refer.doc.date)
        меньше конца периода отчета
        и меньше даты погашенного начисления (accrual.doc.date)
        и с датой погашенного начисления в периоде отчета (accrual.doc.date)
        :return: list: возвраты по услуге для аккаунтов
        """
        match = {
            '$match': {
                'accrual.date': {'$lt': self.date_on + relativedelta(days=1),
                                 '$gte': self.date_from},
                'refer.doc.date': {'$lt': self.date_on + relativedelta(days=1)}
            }
        }
        # Задаем критерии поиска в зависимости от условий
        match = self.base_offset_filters(match)

        query_pipeline = [
            match,
            {
                '$project': {
                    'doc_date': '$accrual.date',
                    'month': '$accrual.month',
                    'account': '$refer.account._id',
                    'services': {
                        '$cond': {
                            'if': {'$lt': ['$refer.doc.date', '$accrual.date']},
                            'then': '$services',
                            'else': {'$literal': 0},
                        },
                    },
                }
            },
            {'$unwind': '$services'},
            {'$project': {
                'doc_date': 1,
                'month': 1,
                'account': 1,
                'value': '$services.value',
                'service_type': '$services.service_type'
            }},
            {'$match': {'service_type': self.service_type}},
            {'$group': {
                '_id': '$account',
                'detail': {'$push': {
                    'month': '$month',
                    'doc_date': '$doc_date',
                    'sub_value': '$value'}},
                'value': {'$sum': '$value'},
            }}

        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        # Нужно отфильтровать ЛС, если поиск был по дому
        if self.house_id:
            result = {x['_id']: x for x in result}
            result = [result[x] for x in self.account_ids if result.get(x)]
        return result

    def __select_algorithm(self, house_id):
        """
        Определение алгоритма поиска (по дому или ЛС ids)
        :return: id дома, если нужно искать по нему, None - если нет
        """
        if house_id:
            accounts_count = self._get_house_accounts_count(house_id)
            # Если список переданных ЛС не больше половины всех ЛС дома,
            # то ищем по списку ЛС
            if not accounts_count / 2 <= len(self.account_ids):
                return
            return house_id
        else:
            return

    def __operate_values(self,
                         accruals: list,
                         offsets: list,
                         subtract: bool):
        """
        Получение результирующей путем вычитания велечин
        из двух список, но одного аккаунта в каждом
        :param accruals: начислния
        :param offsets: погашения, оплаты и т.д.
        :param subtract: вычитание
        :return: dict: результат для аккаунтов
                       {account_id: final_value, ...}
        """
        result = dict()
        for account in accruals + offsets:
            temp = result.setdefault(account['_id'], None)
            # Если ключ только создан - добавим начисление
            if temp is None:
                result[account['_id']] = dict(**account)
            # Складываем/Вычитыаем результаты и выпадающие результаты
            else:
                if subtract:
                    # Для сальдо
                    temp['value'] -= account['value']
                else:
                    temp['value'] += account['value']
                    # Выпадающий список
                    if account['detail']:
                        sub_result = {}
                        # Суммирумем значения по их датам
                        for row in temp['detail'] + account['detail']:
                            sub_temp = sub_result.setdefault(
                                row['doc_date'],
                                dict(
                                    month=row['month'],
                                    sub_value=0,
                                )
                            )
                            sub_temp['sub_value'] += row['sub_value']
                        # Формирование нового выпадающего листа
                        new_detail = [
                            {'doc_date': k,
                             'month': v['month'],
                             'sub_value': v['sub_value']}
                            for k, v in sub_result.items()
                        ]
                        # Замена новым просуммированным листом
                        new_detail.sort(key=lambda x: x['month'], reverse=True)
                        temp['detail'] = new_detail
        return result

    def base_offset_filters(self, match: dict):
        """
        Добавление базовых поисковых фильтров агрегации
        для коллекции Offset
        :param match: фильтр первого агрегационного запроса
        :return: модифицированный match
        """
        # Задаем критерии поиска в зависимости от условий
        if self.house_id:
            match['$match']['refer.account.area.house._id'] = self.house_id
        else:
            match['$match']['refer.account._id'] = {'$in': self.account_ids}
        if self.sectors:
            match['$match']['refer.sector_code'] = {'$in': self.sectors}
        if self.binds:
            match['$match'].update(Offset.get_binds_query(self.binds, raw=True))
        return match


class ServicesBalanceBase:
    """Методы рассчета Сальдо и оборотов по услугам по домам"""

    ADVANCE_KEY = ADVANCE_SERVICE_TYPE

    def __init__(self,
                 binds=None,
                 sectors=None,
                 by_bank=True):
        """
        :param date_from: начало рассчетного периода
        :param date_till: конец рассчетного периода
        :param house_ids: id дома (если передан, то документы ищутся по нему)
        :param sectors: направления
        """
        self.sectors = sectors
        self.by_bank = by_bank
        self.binds = binds
        self.old_method = False
        self.payments_collate = False

    def get_balance(self, date_on, return_tariff_plans=False, advance=True,
                    last_debt_month=None):
        return self._get_balance_by_filter(
            date_on,
            self._get_custom_accruals_filter(),
            self._get_custom_offsets_filter(),
            self._get_custom_payments_filter(),
            return_tariff_plans=return_tariff_plans,
            advance=advance,
            month_till=last_debt_month,
        )

    def get_trial_balance(self, date_from, date_till,
                          return_tariff_plans=False):
        # начальное сальдо
        d = datetime.datetime.now()
        balance_in = self.get_balance(
            date_from,
            return_tariff_plans=False,
        )
        logger.debug('======  get_balance %s', datetime.datetime.now() - d)
        # обороты по дебету
        d = datetime.datetime.now()
        turnovers_debit, t_plans = self.get_debit_turnovers(
            date_from,
            date_till,
            return_tariff_plans=True,
        )
        logger.debug(
            '======  get_debit_turnovers %s',
            datetime.datetime.now() - d,
        )
        # обороты по кредиту
        d = datetime.datetime.now()
        turnovers_credit = self.get_credit_turnovers(
            date_from,
            date_till,
        )
        logger.debug(
            '======  get_credit_turnovers %s',
            datetime.datetime.now() - d,
        )
        # компонуем всё вместе
        d = datetime.datetime.now()
        result = self._link_trial_balance(
            balance_in,
            turnovers_debit,
            turnovers_credit,
        )
        logger.debug(
            '======  _link_trial_balance %s',
            datetime.datetime.now() - d,
        )
        if return_tariff_plans:
            return result, t_plans
        else:
            return result

    def get_debit_turnovers(self,
                            date_from,
                            date_till,
                            return_tariff_plans=False):
        """
        Получение дебета для списка ЛС по услуге
        :return: dict: начисления по услуге для аккаунтов
        """
        return self._get_debit_by_filter(
            date_from,
            date_till,
            self._get_custom_accruals_filter(),
            self._get_custom_offsets_filter(),
            return_tariff_plans=return_tariff_plans,
        )

    def get_credit_turnovers(self, date_from, date_till):
        """
        Получение дебета для списка ЛС по услуге
        :return: dict: начисления по услуге для аккаунтов
        """
        return self._get_credit_by_filter(
            date_from,
            date_till,
            self._get_custom_offsets_filter(),
            self._get_custom_payments_filter(),
        )

    def _link_trial_balance(self,
                            balance_in,
                            turnovers_debit,
                            turnovers_credit):
        result = {}
        services = (
                set(balance_in)
                | set(turnovers_debit)
                | set(turnovers_credit)
        )
        for s_id in services:
            credit = turnovers_credit.get(s_id, {})
            service_summary = dict(
                service_id=s_id,
                # Сальдо
                balance_in=balance_in.get(s_id, 0),
                # Дебет
                accruals=turnovers_debit.get(s_id, {}).get('accruals', 0),
                refund=turnovers_debit.get(s_id, {}).get('refund', 0),
                # Кредит
                payment=credit.get('payment', 0),
                corrections=credit.get('corrections', 0),
                advance_storno=credit.get('advance_storno', 0),
            )
            service_summary['balance_out'] = (
                    service_summary['balance_in']
                    + service_summary['accruals']
                    + service_summary['refund']
                    - service_summary['payment']
                    - service_summary['corrections']
                    - service_summary['advance_storno']
            )
            result[s_id] = service_summary
        return result

    def _get_balance_by_filter(self,
                               date_on,
                               accruals_match,
                               offsets_match,
                               payments_match,
                               return_tariff_plans,
                               advance=True,
                               month_till=None):
        # начисления для сальдо
        accruals_match.update(
            self._get_base_accruals_filter(
                date_on,
                month_till=month_till,
            ),
        )

        d = datetime.datetime.now()
        pos_accruals, neg_accruals, t_plans = \
            self._get_service_accruals(accruals_match)
        logger.debug(
            '========  _get_service_accruals %s',
            datetime.datetime.now() - d,
        )

        # офсеты для сальдо
        storno_match = copy.deepcopy(offsets_match)
        offsets_match.update(
            self._get_balance_offsets_filter(
                date_on,
                month_till=month_till,
            ),
        )

        d = datetime.datetime.now()
        offsets = self._get_balance_offsets(offsets_match)
        logger.debug(
            '========  _get_balance_offsets %s',
            datetime.datetime.now() - d,
        )

        # добавим в офсеты аванс
        if advance:
            accruals = pos_accruals
            if self.old_method:
                payments_match.update(self._get_base_payments_filter(date_on))

                d = datetime.datetime.now()
                payments = self._get_payments(payments_match)
                logger.debug(
                    '========  _get_payments %s',
                    datetime.datetime.now() - d,
                )

                self._update_balance_offsets_by_advance(
                    offsets,
                    payments,
                    neg_accruals,
                )
            else:
                # Получение погашений авансов
                storno_match.update(
                    self._get_base_storno_filter(
                        date_on,
                        month_till=month_till,
                    ),
                )

                d = datetime.datetime.now()
                advance_storno = self._get_storno_offsets(storno_match)
                logger.debug(
                    '========  _get_storno_offsets %s',
                    datetime.datetime.now() - d,
                )

                self._update_balance_accruals_by_advance(
                    accruals,
                    self._get_storno_advance_update_data(
                        storno_match,
                        advance_storno,
                    ),
                )
                if self.payments_collate:
                    payments_match.update(
                        self._get_base_payments_filter(date_on),
                    )

                    d = datetime.datetime.now()
                    payments = self._get_payments(payments_match)
                    logger.debug(
                        '========  _get_payments %s',
                        datetime.datetime.now() - d,
                    )

                    self._update_balance_offsets_by_advance(
                        offsets,
                        payments,
                        neg_accruals,
                    )
        else:
            accruals = self._operate_values(
                pos_accruals,
                {k: -v for k, v in neg_accruals.items()},
                subtract=True,
            )

        # Получение сальдо
        result_dict = self._operate_values(
            accruals,
            offsets,
            subtract=True,
        )
        if return_tariff_plans:
            return result_dict, t_plans
        return result_dict

    def _get_debit_by_filter(self,
                             date_from, date_till,
                             accruals_match,
                             offsets_match,
                             return_tariff_plans):
        """
        Получение дебета для списка ЛС по услуге
        :return: dict: начисления по услуге для аккаунтов
        """
        # начисления для оборотов
        accruals_match.update(
            self._get_base_accruals_filter(
                date_on=date_till + relativedelta(days=1),
                date_from=date_from,
            ),
        )
        pos_accruals, neg_accruals, t_plans = \
            self._get_service_accruals(accruals_match)

        # офсеты-возвраты для оборотов
        offsets_match.update(
            self._get_base_refund_filter(
                date_on=date_till + relativedelta(days=1),
                date_from=date_from,
            ),
        )
        refund = {
            k: -v
            for k, v in self._get_turnovers_offsets(offsets_match).items()
        }

        # добавим в офсеты аванс
        if self.old_method:
            self._update_refund_by_advance(refund, neg_accruals)

        # Получаем Дебит вычитанием возвратов из начасленного
        services = list(set(pos_accruals) | set(refund))
        debit = {
            s: {
                'accruals': pos_accruals.get(s, 0),
                'refund': refund.get(s, 0),
            }
            for s in services
        }
        if return_tariff_plans:
            return debit, t_plans
        return debit

    def _get_credit_by_filter(self,
                              date_from, date_till,
                              offsets_match,
                              payments_match):
        """
        Получение кредита для списка ЛС по услуге
        :return: list: начисления по услуге для аккаунтов
        """
        storno_match = copy.deepcopy(offsets_match)
        corrections_match = copy.deepcopy(offsets_match)
        # офсеты-оплаты для оборотов
        offsets_match.update(
            self._get_base_repayment_filter(
                date_on=date_till + relativedelta(days=1),
                date_from=date_from,
            ),
        )
        repayment = self._get_turnovers_offsets(offsets_match)

        # офсеты-возвраты для оборотов
        if not self.old_method:
            corrections_match.update(
                self._get_base_corrections_filter(
                    date_on=date_till + relativedelta(days=1),
                    date_from=date_from,
                ),
            )
            offsets = self._get_turnovers_offsets(corrections_match)
            corrections = {k: v for k, v in offsets.items()}
        else:
            corrections = {}

        # добавим в офсеты аванс
        if self.old_method:
            payments_match.update(
                self._get_base_payments_filter(
                    date_on=date_till + relativedelta(days=1),
                    date_from=date_from,
                ),
            )
            payments = self._get_payments(payments_match)
            self._update_repayment_by_advance(repayment, payments)
            storno_match.update(
                self._get_base_storno_filter(
                    date_from=date_from,
                    date_on=date_till + relativedelta(days=1),
                ),
            )
            advance_storno = self._get_storno_offsets(storno_match)
            self._update_advance_storno_by_advance(
                advance_storno,
                advance_storno,
            )
        else:
            storno_match.update(
                self._get_base_storno_filter(
                    date_from=date_from,
                    date_on=date_till + relativedelta(days=1),
                ),
            )
            advance_storno = self._get_storno_offsets(storno_match)
            self._update_advance_storno_by_advance(
                advance_storno,
                self._get_storno_advance_update_data(
                    storno_match,
                    advance_storno,
                ),
            )
            if self.payments_collate:
                payments_match.update(
                    self._get_base_payments_filter(
                        date_on=date_till + relativedelta(days=1),
                        date_from=date_from,
                    ),
                )
                payments = self._get_payments(payments_match)
                self._update_repayment_by_advance(repayment, payments)
        # Получаем Дебит вычитанием возвратов из начасленного
        services = list(set(repayment) | set(corrections) | set(advance_storno))
        credit = {
            s: {
                'payment': repayment.get(s, 0),
                'advance_storno': advance_storno.get(s, 0),
                'corrections': corrections.get(s, 0),
            }
            for s in services
        }
        return credit

    def _update_repayment_by_advance(self, repayment, payments):
        repayment.setdefault(self.ADVANCE_KEY, 0)
        repayment[self.ADVANCE_KEY] += payments - sum(repayment.values())

    def _update_advance_storno_by_advance(self, advance_storno,
                                          advance_storno_summary):
        advance_storno.update(
            {
                self.ADVANCE_KEY: -sum(advance_storno_summary.values())
            },
        )

    def _update_refund_by_advance(self, refund, neg_accruals):
        refund.update(
            {
                self.ADVANCE_KEY: (
                        sum(neg_accruals.values())
                        - sum(refund.values())
                ),
            },
        )

    def _update_balance_offsets_by_advance(self, offsets, payments,
                                           neg_accruals):
        offsets.setdefault(self.ADVANCE_KEY, 0)
        offsets[self.ADVANCE_KEY] += (
                payments - sum(neg_accruals.values())
                - sum(offsets.values())
        )

    def _update_balance_accruals_by_advance(self, accruals, advance_storno):
        accruals.update(
            {
                self.ADVANCE_KEY: sum(advance_storno.values()),
            },
        )

    def _get_service_accruals(self, match):
        """
        Получение положительных и отрицательных начислений в соответствии с
        переданным фильтром (включает пени)
        :param: match: фильтр для Accrual
        :return: dict: начисления по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$project': {
                    'services': 1,
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
                    'service_type': '$services.service_type',
                    'tariff_plan': 1,
                },
            },
            {
                '$project': {
                    'service_type': 1,
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
                    'tariff_plan': 1,
                },
            },
            {
                '$group': {
                    '_id': '$service_type',
                    'value_p': {'$sum': '$value_p'},
                    'value_n': {'$sum': '$value_n'},
                    't_plans': {'$addToSet': '$tariff_plan'},
                },
            },
        ]

        def make_result(key):
            id_dict = {x['_id']: x[key] for x in result if x[key]}
            self._change_penalty_service_types(id_dict)
            return id_dict

        d = datetime.datetime.now()
        result = list(Accrual.objects.aggregate(*query_pipeline))
        logger.debug(
            '=========  Accrual.aggregate %s',
            datetime.datetime.now() - d,
        )

        positive_accruals = make_result('value_p')
        negative_accruals = make_result('value_n')
        tariff_plans = make_result('t_plans')

        # добавим пени
        d = datetime.datetime.now()
        pos_penalties, neg_penalties = self._get_penalties_accruals(match)
        logger.debug(
            '==========  _get_penalties_accruals %s',
            datetime.datetime.now() - d,
        )

        for key, value in pos_penalties.items():
            positive_accruals.setdefault(key, 0)
            positive_accruals[key] += value
        for key, value in neg_penalties.items():
            negative_accruals.setdefault(key, 0)
            negative_accruals[key] += value

        return positive_accruals, negative_accruals, tariff_plans

    def _get_penalties_accruals(self, match):
        """
        Получение положительных и отрицательных пеней в соответствии с
        переданным фильтром
        :param: match: фильтр для Accrual
        :return: dict: начисления по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$project': {
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
                    '_id': 0,
                    'p_p': {'$sum': '$value_p'},
                    'p_n': {'$sum': '$value_n'},
                },
            },
        ]

        # Приведение к нужному виду
        def make_result(key):
            return {PENALTY_SERVICE_TYPE: result[0][key] if result else 0}

        result = list(Accrual.objects.aggregate(*query_pipeline))
        positive_penalties = make_result('p_p')
        negative_penalties = make_result('p_n')
        return positive_penalties, negative_penalties

    def _get_balance_offsets(self, match):
        """
        Поиск оффсетов
        :return: dict: оффсеты по услуге по лицевым счетам
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$project': {
                    'services': 1,
                },
            },
            {
                '$unwind': '$services',
            },
            {
                '$project': {
                    'value': '$services.value',
                    'service_type': '$services.service_type',
                },
            },
            {
                '$group': {
                    '_id': '$service_type',
                    'value': {'$sum': '$value'},
                },
            }
        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_turnovers_offsets(self, match):
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$unwind': '$services',
            },
            {
                '$group': {
                    '_id': '$services.service_type',
                    'value': {'$sum': '$services.value'},
                },
            },
        ]
        if self.old_method:
            query_pipeline.insert(
                1,
                {
                    '$project': {
                        'services': {
                            '$cond': {
                                'if': {
                                    '$gte': ['$refer.date', '$accrual.date'],
                                },
                                'then': '$services',
                                'else': {'$literal': 0},
                            },
                        },
                    }
                },
            )
        result = list(Offset.objects.aggregate(*query_pipeline))
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_storno_advance_update_data(self, storno_match, storno_result):
        return storno_result

    def _get_storno_offsets(self, match):
        """
        Получение погашений аванса, у которых дата погешения (refer.doc.date)
        меньше конца периода отчета
        и меньше даты погашенного начисления (accrual.doc.date)
        и с датой погашенного начисления в периоде отчета (accrual.doc.date)
        :return: dict: возвраты по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$unwind': '$services',
            },
            {
                '$project': {
                    'value': '$services.value',
                    'service_type': '$services.service_type',
                },
            },
            {
                '$group': {
                    '_id': '$service_type',
                    'value': {'$sum': '$value'},
                },
            },
        ]
        if self.old_method:
            query_pipeline.insert(
                1,
                {
                    '$project': {
                        'services': {
                            '$cond': {
                                'if': {'$lt': ['$refer.date', '$accrual.date']},
                                'then': '$services',
                                'else': {'$literal': 0},
                            },
                        },
                    }
                },
            )
        result = list(Offset.objects.aggregate(*query_pipeline))
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        return result

    def _get_payments(self, match):
        """
        Оплаты для рассчета аванса для сальдо
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$group': {
                    '_id': 0,
                    'value': {'$sum': '$value'},
                },
            },
        ]
        result = list(Payment.objects.aggregate(*query_pipeline))
        return result[0]['value'] if result else 0

    @staticmethod
    def _change_penalty_service_types(data):
        for key in (_USER_PENALTY_SERVICE_TYPE, _OLD_PENALTY_SERVICE_TYPE):
            if key in data:
                data.setdefault(PENALTY_SERVICE_TYPE, 0)
                data[PENALTY_SERVICE_TYPE] += data.pop(key)

    @staticmethod
    def _change_advance_service_types(data):
        key = _OLD_ADVANCE_SERVICE_TYPE
        if key in data:
            data.setdefault(ADVANCE_SERVICE_TYPE, 0)
            data[ADVANCE_SERVICE_TYPE] += data.pop(key)

    def _operate_values(self,
                        accruals: dict,
                        offsets: dict,
                        subtract: bool,
                        add: bool = False):
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
            elif add:
                s_b = accruals.get(service, 0) + offsets.get(service, 0)
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

    def _get_base_accruals_filter(self, date_on, date_from=None,
                                  month_till=None):
        """
        Возвращает базовый поисковый фильтр агрегации для коллекции Accruals
        :param date_on: дата, на которую искать начисления (начисления ищутся
        раньше этой даты)
        :param date_from: необязательно, для поиска оборотов (берутся только
        начисления, начиная с этой даты)
        :return: словарь с фильтром
        """
        match = {
            'is_deleted': {'$ne': True},
            'doc.status': {'$in': CONDUCTED_STATUSES},
            'doc.date': {'$lt': date_on},
        }
        if self.binds:
            match.update(
                Accrual.get_binds_query(self.binds, raw=True)
            )
        # Задаем критерии поиска в зависимости от условий
        if self.sectors:
            match['sector_code'] = {'$in': self.sectors}
        if month_till:
            match['month'] = {'$lte': month_till}
        # если передана дата начала периода
        if date_from:
            match['doc.date'].update({'$gte': date_from})
        return match

    def _get_base_offsets_filter(self,
                                 date_on,
                                 date_from=None,
                                 offsets_types=None,
                                 month_till=None):
        if self.old_method:
            match = {'accrual.date': {'$lt': date_on}}
            if offsets_types:
                match['_type'] = {'$in': offsets_types}
        else:
            storno_op = [
                OffsetOperationAccount.ADVANCE_PAYMENT,
                OffsetOperationAccount.ADVANCE_REFUND,
            ]
            match = {
                '$or': [
                    {
                        '_type': {'$ne': 'AdvanceRepayment'},
                    },
                    {
                        '_type': 'Advance',
                    },
                    {
                        'op_debit': {'$nin': storno_op},
                        'op_credit': {'$nin': storno_op},
                    },
                ],
            }
        if self.by_bank:
            match['refer.doc.date'] = {'$lt': date_on}
            if date_from:
                match['refer.doc.date'].update({'$gte': date_from})
        else:
            match['refer.date'] = {'$lt': date_on}
            if date_from:
                match['refer.date'].update({'$gte': date_from})
        if self.sectors:
            match['refer.sector_code'] = {'$in': self.sectors}
        if month_till:
            match['accrual.month'] = {'$lte': month_till}
        if self.binds:
            match.update(Offset.get_binds_query(self.binds, raw=True))
        return match

    def _get_balance_offsets_filter(self, date_on, month_till=None):
        if self.old_method:
            return self._get_base_offsets_filter(date_on, None, month_till)
        date_key = 'doc_date' if self.by_bank else 'date'
        match = {
            date_key: {'$lt': date_on},
        }
        if self.sectors:
            match['refer.sector_code'] = {'$in': self.sectors}
        if month_till:
            match['accrual.month'] = {'$lte': month_till}
        if self.binds:
            match.update(Offset.get_binds_query(self.binds, raw=True))
        return match

    def _get_base_repayment_filter(self, date_on, date_from=None,
                                   month_till=None):
        if self.old_method:
            return self._get_base_offsets_filter(
                date_on,
                date_from=date_from,
                offsets_types=['Repayment'],
                month_till=month_till,
            )
        return self._get_offset_operations_filter(
            PAYMENT_OFFSET_OPERATIONS,
            date_on,
            date_from=date_from,
            month_till=month_till,
        )

    def _get_base_refund_filter(self, date_on, date_from=None, month_till=None):
        if self.old_method:
            return self._get_base_offsets_filter(
                date_on,
                date_from=date_from,
                offsets_types=['Refund'],
                month_till=month_till,
            )
        return self._get_offset_operations_filter(
            REFUND_OFFSET_OPERATIONS,
            date_on,
            date_from=date_from,
            month_till=month_till,
        )

    def _get_base_storno_filter(self, date_on, date_from=None, month_till=None):
        if self.old_method:
            return self._get_depricated_storno_filter(
                date_on,
                date_from=date_from,
                month_till=month_till,
            )
        return self._get_offset_operations_filter(
            ADVANCE_REPAYMENT_OFFSET_OPERATIONS,
            date_on,
            date_from=date_from,
            month_till=month_till,
        )

    def _get_depricated_storno_filter(self, date_on, date_from=None,
                                      month_till=None):
        match = {'accrual.date': {'$gte': date_from, '$lt': date_on}}
        if self.by_bank:
            match['refer.doc.date'] = {'$lt': date_on}
        else:
            match['refer.date'] = {'$lt': date_on}
        if self.sectors:
            match['refer.sector_code'] = {'$in': self.sectors}
        if month_till:
            match['accrual.month'] = {'$lte': month_till}
        if self.binds:
            match.update(Offset.get_binds_query(self.binds, raw=True))
        return match

    def _get_base_corrections_filter(self, date_on, date_from=None,
                                     month_till=None):
        return self._get_offset_operations_filter(
            CORRECTION_OFFSET_OPERATIONS,
            date_on,
            date_from=date_from,
            month_till=month_till,
        )

    def _get_offset_operations_filter(self, operations, date_on, date_from=None,
                                      month_till=None):
        date_key = 'doc_date' if self.by_bank else 'date'
        match = {
            date_key: {'$lt': date_on},
        }
        if date_from:
            match[date_key]['$gte'] = date_from
        match['$or'] = []
        for operation in operations:
            match['$or'].append(
                {
                    'op_debit': operation[0],
                    'op_credit': operation[1],
                },
            )
        if self.sectors:
            match['refer.sector_code'] = {'$in': self.sectors}
        if month_till:
            match['accrual.month'] = {'$lte': month_till}
        if self.binds:
            match.update(Offset.get_binds_query(self.binds, raw=True))
        return match

    def _get_base_payments_filter(self, date_on, date_from=None):
        """
        Возвращает базовый поисковый фильтр агрегации для коллекции Payment
        :param date_on: дата, на которую искать начисления (начисления ищутся
        раньше этой даты)
        :param date_from: необязательно, для поиска оборотов (берутся только
        начисления, начиная с этой даты)
        :return: словарь с фильтром
        """
        match = {'is_deleted': {'$ne': True}}
        if self.by_bank:
            match['doc.date'] = {'$lt': date_on}
            if date_from:
                match['doc.date'].update({'$gte': date_from})
        else:
            match['date'] = {'$lt': date_on}
            if date_from:
                match['date'].update({'$gte': date_from})
        # Задаем критерии поиска в зависимости от условий (добавляем фильтры)
        if self.sectors:
            match['sector_code'] = {'$in': self.sectors}
        if self.binds:
            match.update(Payment.get_binds_query(self.binds, raw=True))
        return match

    def _get_custom_offsets_filter(self):
        raise NotImplemented('Custom filter undefined')

    def _get_custom_payments_filter(self):
        raise NotImplemented('Custom filter undefined')

    def _get_custom_accruals_filter(self):
        raise NotImplemented('Custom filter undefined')


class _AccountsServicesHouseBalance(ServicesBalanceBase):
    """Методы рассчета Сальдо и оборотов по поставщикам, услугам и домам"""

    def _update_repayment_by_advance(self, repayment, payments):
        accounts_sums = self.__get_accounts_sums(repayment)
        for account, value in payments.items():
            repayment.update(
                {
                    (account, ADVANCE_SERVICE_TYPE): (
                            value
                            - accounts_sums.get(account, 0)
                    ),
                },
            )

    def _update_advance_storno_by_advance(self, advance_storno,
                                          advance_storno_summary):
        accounts_sums = self.__get_accounts_sums(advance_storno_summary)
        for account in accounts_sums:
            advance_storno.update(
                {
                    (account, ADVANCE_SERVICE_TYPE): (
                        -accounts_sums.get(account, 0)
                    ),
                },
            )

    def _update_balance_accruals_by_advance(self, accruals, advance_storno):
        for key, value in advance_storno.items():
            advance_key = (
                None if self.old_method else key[0],
                ADVANCE_SERVICE_TYPE,
            )
            accruals.setdefault(advance_key, 0)
            accruals[advance_key] += value

    def _update_refund_by_advance(self, refund, neg_accruals):
        refund_sums = self.__get_accounts_sums(refund)
        accruals_sums = self.__get_accounts_sums(neg_accruals)
        for account, value in accruals_sums.items():
            refund.update(
                {
                    (account, ADVANCE_SERVICE_TYPE): (
                            value
                            - refund_sums.get(account, 0)
                    ),
                },
            )

    def _update_balance_offsets_by_advance(self, offsets, payments,
                                           neg_accruals):
        accruals_sums = self.__get_accounts_sums(neg_accruals)
        offsets_sums = self.__get_accounts_sums(offsets)
        accounts = (
                set(accruals_sums.keys())
                | set(offsets_sums.keys())
                | set(payments.keys())
        )
        for account in accounts:
            offsets.update(
                {
                    (account, ADVANCE_SERVICE_TYPE): (
                            payments.get(account, 0)
                            - offsets_sums.get(account, 0)
                            - accruals_sums.get(account, 0)
                    ),
                },
            )
            if accruals_sums.get(account):
                # TODO: оптимизировать
                account_services = {
                    a_s[1]: -v
                    for a_s, v in neg_accruals.items()
                    if a_s[0] == account
                }
                for service, value in account_services.items():
                    key = (account, service)
                    offsets.setdefault(key, 0)
                    offsets[key] += value
                    offsets[(account, ADVANCE_SERVICE_TYPE)] -= value

    @staticmethod
    def __get_accounts_sums(source_dict):
        accounts_sums = {}
        for account_service, value in source_dict.items():
            accounts_sums.setdefault(account_service[0], 0)
            accounts_sums[account_service[0]] += value
        return accounts_sums

    def _get_service_accruals(self, match):
        """
        Получение положительных и отрицательных начислений в соответствии с
        переданным фильтром (включает пени)
        :param: match: фильтр для Accrual
        :return: dict: начисления по услуге для аккаунтов
        """
        query_pipeline = [
            {'$match': match},
            {'$project': {
                'account': '$account._id',
                'services': 1,
            }},
            {'$unwind': '$services'},
            {'$project': {
                'value': {'$add': [
                    '$services.value',
                    '$services.totals.shortfalls',
                    '$services.totals.privileges',
                    '$services.totals.recalculations'
                ]},
                'service_type': '$services.service_type',
                'tariff_plan': 1,
                'account': 1,
            }},
            {'$project': {
                'service_type': 1,
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
                'tariff_plan': 1,
                'account': 1,
            }},
            {'$group': {
                '_id': {
                    'account': '$account',
                    'service': '$service_type',
                },
                'value_p': {'$sum': '$value_p'},
                'value_n': {'$sum': '$value_n'},
                't_plans': {'$addToSet': '$tariff_plan'},
            }},
        ]

        def make_result(key):
            id_dict = {x['_id']: x[key] for x in result if x[key]}
            self._change_penalty_service_types(id_dict)
            return id_dict

        result = list(
            Accrual.objects.aggregate(
                *query_pipeline,
                allowDiskUse=True,
            ),
        )
        self._tuple_id(result)
        positive_accruals = make_result('value_p')
        negative_accruals = make_result('value_n')
        tariff_plans = make_result('t_plans')
        # добавим пени
        pos_penalties, neg_penalties = self._get_penalties_accruals(match)
        for key, value in pos_penalties.items():
            positive_accruals.setdefault(key, 0)
            positive_accruals[key] += value
        for key, value in neg_penalties.items():
            negative_accruals.setdefault(key, 0)
            negative_accruals[key] += value
        return positive_accruals, negative_accruals, tariff_plans

    def _get_penalties_accruals(self, match):
        """
        Получение положительных и отрицательных пеней в соответствии с
        переданным фильтром
        :param: match: фильтр для Accrual
        :return: dict: начисления по услуге для аккаунтов
        """
        query_pipeline = [
            {'$match': match},
            {'$project': {
                'account': '$account._id',
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
            }},
            {'$group': {
                '_id': '$account',
                'p_p': {'$sum': '$value_p'},
                'p_n': {'$sum': '$value_n'},
            }}
        ]

        # Приведение к нужному виду
        def make_result(key):
            return {
                (x['_id'], PENALTY_SERVICE_TYPE): x[key]
                for x in result if x[key]
            }

        result = list(
            Accrual.objects.aggregate(
                *query_pipeline,
                allowDiskUse=True,
            ),
        )
        positive_penalties = make_result('p_p')
        negative_penalties = make_result('p_n')
        return positive_penalties, negative_penalties

    def _get_balance_offsets(self, match):
        """
        Поиск оффсетов
        :return: dict: оффсеты по услуге по лицевым счетам
        """
        query_pipeline = [
            {'$match': match},
            {'$project': {
                'account': '$refer.account._id',
                'services': 1,
            }},
            {'$unwind': '$services'},
            {'$project': {
                'value': '$services.value',
                'service_type': '$services.service_type',
                'account': 1,
            }},
            {'$group': {
                '_id': {
                    'account': '$account',
                    'service': '$service_type',
                },
                'value': {'$sum': '$value'},
            }}
        ]
        result = list(
            Offset.objects.aggregate(
                *query_pipeline,
                allowDiskUse=True,
            ),
        )
        self._tuple_id(result)
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_turnovers_offsets(self, match):
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$unwind': '$services',
            },
            {
                '$group': {
                    '_id': {
                        'account': '$refer.account._id',
                        'service': '$services.service_type',
                    },
                    'value': {'$sum': '$services.value'},
                },
            }

        ]
        if self.old_method:
            query_pipeline.insert(
                1,
                {
                    '$project': {
                        'refer.account._id': 1,
                        'services': {
                            '$cond': {
                                'if': {'$lt': ['$refer.date', '$accrual.date']},
                                'then': '$services',
                                'else': {'$literal': 0},
                            },
                        },
                    }
                },
            )
        result = list(
            Offset.objects.aggregate(
                *query_pipeline,
                allowDiskUse=True,
            ),
        )
        self._tuple_id(result)
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_storno_offsets(self, match):
        """
        Получение погашений аванса, у которых дата погешения (refer.doc.date)
        меньше конца периода отчета
        и меньше даты погашенного начисления (accrual.doc.date)
        и с датой погашенного начисления в периоде отчета (accrual.doc.date)
        :return: dict: возвраты по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$unwind': '$services',
            },
            {
                '$project': {
                    'account': '$refer.account._id',
                    'value': '$services.value',
                    'service_type': '$services.service_type',
                },
            },
            {
                '$group': {
                    '_id': {
                        'account': '$account',
                        'service': '$service_type',
                    },
                    'value': {'$sum': '$value'},
                },
            }
        ]
        if self.old_method:
            query_pipeline.insert(
                1,
                {
                    '$project': {
                        'refer.account._id': 1,
                        'services': {
                            '$cond': {
                                'if': {'$lt': ['$refer.date', '$accrual.date']},
                                'then': '$services',
                                'else': {'$literal': 0},
                            },
                        },
                    }
                },
            )
        result = list(
            Offset.objects.aggregate(
                *query_pipeline,
                allowDiskUse=True,
            ),
        )
        self._tuple_id(result)
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_payments(self, match):
        """
        Оплаты для рассчета аванса для сальдо
        """
        query_pipeline = [
            {'$match': match},
            {'$group': {
                '_id': '$account._id',
                'value': {'$sum': '$value'},
            }}
        ]
        result = list(
            Payment.objects.aggregate(
                *query_pipeline,
                allowDiskUse=True,
            ),
        )
        return {r['_id']: r['value'] for r in result}

    @staticmethod
    def _tuple_id(data):
        for row in data:
            row['_id'] = (
                row['_id'].get('account'),
                row['_id'].get('service'),
            )

    @staticmethod
    def _change_penalty_service_types(data):
        penalty_keys = {}
        for key in data:
            if _PENALTY_SERVICE_TYPES_CHANGE & set(key):
                penalty_keys[key] = (key[0], PENALTY_SERVICE_TYPE)
        for key, value in penalty_keys.items():
            data.setdefault(value, 0)
            data[value] += data.pop(key)

    @staticmethod
    def _change_advance_service_types(data):
        advance_keys = {}
        for key in data:
            if _OLD_ADVANCE_SERVICE_TYPE in key:
                advance_keys[key] = (key[0], ADVANCE_SERVICE_TYPE)
        for key, value in advance_keys.items():
            data.setdefault(value, 0)
            data[value] += data.pop(key)


class _VendorsServicesHousesBalance(ServicesBalanceBase):
    """Методы рассчета Сальдо и оборотов по поставщикам, услугам и домам"""

    ADVANCE_KEY = (
        None,
        ADVANCE_SERVICE_TYPE,
        None,
    )

    def _get_service_accruals(self, match):
        """
        Получение положительных и отрицательных начислений в соответствии с
        переданным фильтром (включает пени)
        :param: match: фильтр для Accrual
        :return: dict: начисления по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$project': {
                    'house': '$account.area.house._id',
                    'services': 1,
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
                            '$services.totals.recalculations',
                        ],
                    },
                    'service_type': '$services.service_type',
                    'vendor': '$services.vendor._id',
                    'contract': '$services.vendor.contract',
                    'tariff_plan': 1,
                    'house': 1,
                },
            },
            {
                '$project': {
                    'service_type': 1,
                    'vendor': 1,
                    'contract': 1,
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
                    'tariff_plan': 1,
                    'house': 1,
                },
            },
            {
                '$group': {
                    '_id': {
                        'contract': '$contract',
                        'house': '$house',
                        'service': '$service_type',
                    },
                    'vendor': {'$first': '$vendor'},
                    'value_p': {'$sum': '$value_p'},
                    'value_n': {'$sum': '$value_n'},
                    't_plans': {'$addToSet': '$tariff_plan'},
                },
            },
        ]

        def make_result(key):
            id_dict = {x['_id']: x[key] for x in result if x[key]}
            self._change_penalty_service_types(id_dict)
            return id_dict

        result = list(Accrual.objects.aggregate(*query_pipeline))
        self._tuple_id(result)
        positive_accruals = make_result('value_p')
        negative_accruals = make_result('value_n')
        tariff_plans = make_result('t_plans')
        # добавим пени
        pos_penalties, neg_penalties = self._get_penalties_accruals(match)
        for key, value in pos_penalties.items():
            positive_accruals.setdefault(key, 0)
            positive_accruals[key] += value
        for key, value in neg_penalties.items():
            negative_accruals.setdefault(key, 0)
            negative_accruals[key] += value
        return positive_accruals, negative_accruals, tariff_plans

    def _get_penalties_accruals(self, match):
        """
        Получение положительных и отрицательных пеней в соответствии с
        переданным фильтром
        :param: match: фильтр для Accrual
        :return: dict: начисления по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$project': {
                    'house': '$account.area.house._id',
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
                    'contract': '$penalty_vendor.contract',
                },
            },
            {
                '$group': {
                    '_id': {
                        'contract': '$contract',
                        'house': '$house',
                    },
                    'p_p': {'$sum': '$value_p'},
                    'p_n': {'$sum': '$value_n'},
                },
            },
        ]

        # Приведение к нужному виду
        def make_result(key):
            return {
                (
                    x['_id'].get('contract'),
                    PENALTY_SERVICE_TYPE,
                    x['_id']['house'],
                ): x[key]
                for x in result if x[key]
            }

        result = list(Accrual.objects.aggregate(*query_pipeline))
        positive_penalties = make_result('p_p')
        negative_penalties = make_result('p_n')
        return positive_penalties, negative_penalties

    def _get_balance_offsets(self, match):
        """
        Поиск оффсетов
        :return: dict: оффсеты по услуге по лицевым счетам
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$project': {
                    'house': '$refer.account.area.house._id',
                    'services': 1,
                },
            },
            {
                '$unwind': '$services',
            },
            {
                '$project': {
                    'value': '$services.value',
                    'service_type': '$services.service_type',
                    'vendor': '$services.vendor._id',
                    'contract': '$services.vendor.contract',
                    'house': 1,
                },
            },
            {
                '$group': {
                    '_id': {
                        'contract': '$contract',
                        'house': '$house',
                        'service': '$service_type',
                    },
                    'vendor': {'$first': '$vendor'},
                    'value': {'$sum': '$value'},
                },
            },
        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        self._tuple_id(result)
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_turnovers_offsets(self, match):
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$unwind': '$services',
            },
            {
                '$group': {
                    '_id': {
                        'contract': '$services.vendor.contract',
                        'house': '$refer.account.area.house._id',
                        'service': '$services.service_type',
                    },
                    'vendor': {'$first': '$services.vendor._id'},
                    'value': {'$sum': '$services.value'},
                },
            }
        ]
        if self.old_method:
            query_pipeline.insert(
                1,
                {
                    '$project': {
                        'refer.account.area.house._id': 1,
                        'services': {
                            '$cond': {
                                'if': {
                                    '$gte': ['$refer.date', '$accrual.date'],
                                },
                                'then': '$services',
                                'else': {'$literal': 0},
                            },
                        },
                    },
                },
            )
        result = list(Offset.objects.aggregate(*query_pipeline))
        self._tuple_id(result)
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_storno_offsets(self, match):
        """
        Получение погашений аванса, у которых дата погешения (refer.doc.date)
        меньше конца периода отчета
        и меньше даты погашенного начисления (accrual.doc.date)
        и с датой погашенного начисления в периоде отчета (accrual.doc.date)
        :return: dict: возвраты по услуге для аккаунтов
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$unwind': '$services',
            },
            {
                '$project': {
                    'house': '$refer.account.area.house._id',
                    'value': '$services.value',
                    'service_type': '$services.service_type',
                    'vendor': '$services.vendor._id',
                    'contract': '$services.vendor.contract',
                },
            },
            {
                '$group': {
                    '_id': {
                        'contract': '$contract',
                        'house': '$house',
                        'service': '$service_type',
                    },
                    'vendor': {'$first': '$vendor'},
                    'value': {'$sum': '$value'},
                },
            },
        ]
        if self.old_method:
            query_pipeline.insert(
                1,
                {
                    '$project': {
                        'refer.account.area.house._id': 1,
                        'services': {
                            '$cond': {
                                'if': {'$lt': ['$refer.date', '$accrual.date']},
                                'then': '$services',
                                'else': {'$literal': 0},
                            },
                        },
                    },
                },
            )
        result = list(Offset.objects.aggregate(*query_pipeline))
        self._tuple_id(result)
        result = {x['_id']: x['value'] for x in result if x['value']}
        self._change_penalty_service_types(result)
        self._change_advance_service_types(result)
        return result

    def _get_storno_advance_update_data(self, storno_match, storno_result):
        query_pipeline = [
            {
                '$match': storno_match,
            },
            {
                '$project': {
                    'house': '$refer.account.area.house._id',
                    'value': '$total',
                    'service_type': ADVANCE_SERVICE_TYPE,
                    'vendor': '$advance_vendor._id',
                    'contract': '$advance_vendor.contract',
                },
            },
            {
                '$group': {
                    '_id': {
                        'contract': '$contract',
                        'house': '$house',
                        'service': '$service_type',
                    },
                    'vendor': {'$first': '$vendor'},
                    'value': {'$sum': '$value'},
                },
            },
        ]
        result = list(Offset.objects.aggregate(*query_pipeline))
        self._tuple_id(result)
        return {x['_id']: x['value'] for x in result if x['value']}

    def _get_payments(self, match):
        """
        Оплаты для рассчета аванса для сальдо
        """
        query_pipeline = [
            {
                '$match': match,
            },
            {
                '$group': {
                    '_id': 0,
                    'value': {'$sum': '$value'},
                },
            },
        ]
        result = list(Payment.objects.aggregate(*query_pipeline))
        return result[0]['value'] if result else 0

    def _tuple_id(self, data):
        for row in data:
            row['_id'] = (
                row['_id'].get('contract'),
                row['_id'].get('service'),
                row['_id'].get('house'),
            )

    @staticmethod
    def _change_penalty_service_types(data):
        penalty_keys = {}
        for key in data:
            if _PENALTY_SERVICE_TYPES_CHANGE & set(key):
                penalty_keys[key] = (key[0], PENALTY_SERVICE_TYPE, key[2])
        for key, value in penalty_keys.items():
            data.setdefault(value, 0)
            data[value] += data.pop(key)

    @staticmethod
    def _change_advance_service_types(data):
        advance_keys = {}
        for key in data:
            if _OLD_ADVANCE_SERVICE_TYPE in key:
                advance_keys[key] = (key[0], ADVANCE_SERVICE_TYPE, key[2])
        for key, value in advance_keys.items():
            data.setdefault(value, 0)
            data[value] += data.pop(key)

    def change_penalty_service_types(self, data):
        self._change_penalty_service_types(data)

    def _update_advance_storno_by_advance(self, advance_storno,
                                          advance_storno_summary):
        advances = {}
        for key, value in advance_storno_summary.items():
            advance_key = (
                None if self.old_method else key[0],
                ADVANCE_SERVICE_TYPE,
                key[2],
            )
            advances.setdefault(advance_key, 0)
            advances[advance_key] -= value
        advance_storno.update(advances)

    def _update_balance_accruals_by_advance(self, accruals, advance_storno):
        for key, value in advance_storno.items():
            advance_key = (
                None if self.old_method else key[0],
                ADVANCE_SERVICE_TYPE,
                key[2],
            )
            accruals.setdefault(advance_key, 0)
            accruals[advance_key] += value
