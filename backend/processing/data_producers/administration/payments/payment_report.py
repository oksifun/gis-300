from collections import OrderedDict

from app.auth.models.actors import Actor
from app.autopayment.models.logs import AutoPaymentLog
from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual
from processing.models.billing.log import PublicPaySource
from processing.models.billing.payment import Payment
from processing.models.billing.responsibility import Responsibility
from processing.models.tasks.sber_autopay import SberAutoPayAccount
from utils.crm_utils import get_crm_client_ids

from .core import BaseReport


class PaymentReport(BaseReport):
    XLSX_TEMPLATE = 'templates/payments/payments_stat.xlsx'
    TOP_BANKS_CNT = 4  # количество топ-банков
    XLSX_WORKSHEETS = {
        'Общий по системе': {
            'entry_produce_method': 'common_stat',
            'columns': {
                'common': {'column': 'B', 'start_row': 2},
                'banks': {'column': 'A', 'start_row': 11, 'multicolumn': True}
            },
        },
        'Рынок с реестрами Сбера': {
            'entry_produce_method': 'sber_stat',
            'columns': {
                'clients_cnt': {'column': 'B', 'start_row': 2},
                'accruals_value': {'column': 'B', 'start_row': 3,
                                   'multicolumn': True},
                'common': {'column': 'B', 'start_row': 4},
                'payments': {'column': 'B', 'start_row': 12,
                             'multicolumn': True},
                'banks': {'column': 'A', 'start_row': 24, 'multicolumn': True},
                'auto_pay': {
                    'column': 'A',
                    'start_row': 31,
                    'multicolumn': True,
                },
            },
        },
        'Рынок единичных платежей': {
            'entry_produce_method': 'not_sber_stat',
            'columns': {
                'clients_cnt': {'column': 'B', 'start_row': 2},
                'accruals_value': {'column': 'B', 'start_row': 3,
                                   'multicolumn': True},
                'common': {'column': 'B', 'start_row': 4},
                'payments': {'column': 'B', 'start_row': 12,
                             'multicolumn': True},
                'banks': {'column': 'A', 'start_row': 22, 'multicolumn': True},
                'auto_pay': {
                    'column': 'A',
                    'start_row': 29,
                    'multicolumn': True,
                },
            },
        },
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client_ids = get_crm_client_ids()
        self.prepare_data()

    def prepare_data(self) -> None:
        # получаем все оплаты за период
        self.all_payments_queryset = self.get_payments(
            filter={'doc._type': {
                '$nin': ['ManualDoc', 'LostDoc',
                         'CashReceiptDoc', 'LostBankOrderDoc'],
                '$size': 2
            }}
        )

        # извлекаем из них данные о жителях, организациях
        self.all_providers, self.all_accounts = \
            self.get_payments_providers_and_accounts(self.all_payments_queryset)
        self.all_payment_ids = self.all_payments_queryset.distinct('id')

        # получаем все оплаты Сбер
        sber_payments_queryset = self.get_payments(
            filter={
                'doc._type': {'$in': ['SberDoc'], '$size': 2}
            }
        )
        # извлекаем из них данные о жителях, организациях из Сбер-платежей
        self.sber_providers, self.sber_accounts = \
            self.get_payments_providers_and_accounts(sber_payments_queryset)
        self.sber_payment_ids = sber_payments_queryset.distinct('id')

        # получаем все оплаты без Сбера
        self.non_sber_providers = list(
            set(self.all_providers) - set(self.sber_providers)
        )
        # извлекаем из них данные о жителях, организациях без Сбер-платежей
        self.non_sber_accounts = list(
            set(self.all_accounts) - set(self.sber_accounts)
        )

    def get_entries(self, produce_method_name):
        return getattr(self, produce_method_name)()

    def get_responsibles(self, account_ids) -> list:
        """
        Поиск отвественных собственников
        :return: list: id собственников
        """
        q = {
            '$and': [
                {'$or': [
                    {'date_from': {'$lte': self.date_from}},
                    {'date_from': None},
                ]},
                {'$or': [
                    {'date_till': {'$gte': self.date_till}},
                    {'date_till': None},
                ]}
            ],
        }
        if account_ids is not None:
            q['account._id'] = {'$in': account_ids}
        responsibles = Responsibility.objects(__raw__=q)
        return responsibles.distinct('account._id')

    @staticmethod
    def get_active_stat(resp_ids, not_resp_ids) -> (int, int):
        """
        Возвращает количество пользователей с активированным или нет ЛК
        :return: (int, int)
        """
        resp_active = Actor.objects(
            __raw__={
                'owner._id': {'$in': resp_ids},
                'has_access': True,
            },
        ).count()
        if not_resp_ids is None:
            not_resp_active = Actor.objects(
                __raw__={
                    'owner._id': {'$nin': resp_ids},
                    'has_access': True,
                    'owner.owner_type': 'Tenant',
                },
            ).count()
        else:
            not_resp_active = Actor.objects(
                __raw__={
                    'owner._id': {'$in': not_resp_ids},
                    'has_access': True,
                },
            ).count()
        return resp_active, not_resp_active

    def get_resp_stat(self, resp_stat, accounts, with_total=False):
        responsibles = self.get_responsibles(accounts)
        if accounts is None:
            not_responsibles = None
        else:
            not_responsibles = list(set(accounts) - set(responsibles))
        resp_active_cnt, not_resp_active_cnt = self.get_active_stat(
            responsibles,
            not_responsibles,
        )
        if with_total:
            resp_stat['total_cnt'] += len(
                responsibles)  # общее количество отвественных
        if 'active_cnt' in resp_stat:
            # ответственные активированные
            resp_stat['active_cnt'] += resp_active_cnt
        if 'non_active_cnt' in resp_stat:
            # обычные активированные
            resp_stat['non_active_cnt'] += not_resp_active_cnt
        return resp_stat

    def get_mobile_stat(self) -> dict:
        """
        Возвращает статистику по использованию мобильных приложений
        :return: dict
        """
        stat = OrderedDict({
            'android': 0,
            'ios': 0,
            'huawei': 0,
        })
        return stat

    def get_tg_stat(self, account_ids=None) -> dict:
        """
        Количество telegram-ботов, которые жители использовали
        хотя бы один раз за этот месяц
        :return: dict
        """
        query = {
            'telegram_chats': {'$ne': None},
            'is_deleted': {'$ne': True}
        }
        if account_ids:
            query.update({'_id': {'$in': account_ids}})
        return {'telegram': Tenant.objects(__raw__=query).count()}

    def get_payments(self, filter=None, provider_ids=None):
        query = {
            'doc.date': {'$gte': self.date_from, '$lt': self.date_till},
            'is_deleted': {'$ne': True},
            'doc.provider': {
                '$in': provider_ids if provider_ids else self.client_ids
            }
        }
        if filter:
            query.update(filter)
        payments = Payment.objects(__raw__=query)
        return payments

    @staticmethod
    def get_payments_by_id(payment_ids, providers_filter=None):
        query = {'_id': {'$in': payment_ids}}
        if providers_filter:
            query.update(providers_filter)
        return Payment.objects(__raw__=query)

    @staticmethod
    def get_payments_providers_and_accounts(queryset) -> (list, list):
        providers = queryset.distinct('doc.provider')
        accounts = queryset.distinct('account.id')
        return providers, accounts

    def get_accruals(self, provider_ids) -> dict:
        result = {'values': {'cnt': 0, 'value': 0}}
        accruals = list(Accrual.objects(
            doc__date__gte=self.date_from,
            doc__date__lt=self.date_till,
            owner__in=provider_ids,
            doc__status__in=['ready', 'edit'],
            is_deleted__ne=True
        ).aggregate(
            {'$group': {
                '_id': None,
                'value': {'$sum': '$value'},
                'cnt': {'$sum': 1},
            }},
            {'$project': {
                'value': 1,
                'cnt': 1,
                '_id': 0
            }}
        ))
        if accruals:
            result['values'].update({
                'cnt': accruals[0]['cnt'],
                'value': round(accruals[0]['value'] / 100, 2)
            })
        return result

    def get_sber_payment_stat(self, queryset) -> dict:
        registry_cnt = 0
        registry_value = 0
        other_cnt = 0
        other_value = 0
        all_auto_payment_accounts = [
            item.account for item in SberAutoPayAccount.objects
        ]
        auto_payment_cnt = 0
        auto_payment_value = 0

        for item in queryset.as_pymongo():
            if item['doc']['_type'] == ['SberDoc', 'RegistryDoc']:
                registry_cnt += 1
                registry_value += item['value']
            elif (
                    item['account']['_id'] in all_auto_payment_accounts
                    or item.get('auto_payment')
            ):
                auto_payment_cnt += 1
                auto_payment_value += item['value']
            else:
                if not item.get('auto_payment'):
                    other_cnt += 1
                    other_value += item['value']
        stats = OrderedDict(
            registry={'cnt': registry_cnt,
                      'value': round(registry_value / 100, 2)},
            auto_payment={'cnt': auto_payment_cnt,
                          'value': round(auto_payment_value / 100, 2)},
        )
        c300_auto_pay = self._get_auto_pay_stat(
            Payment.objects(
                doc__date__gte=self.date_from,
                doc__date__lt=self.date_till,
                doc__provider__in=self.sber_providers,
                is_deleted__ne=True,
            ),
        )
        stats.update(
            c300_auto_pay=c300_auto_pay.pop('total'),
        )
        pay_log_stat = self.get_logs_stats(self.sber_accounts)
        stats.update(pay_log_stat)
        stats.update(
            other={'cnt': other_cnt, 'value': round(other_value / 100, 2)},
        )
        stats['auto_pay_by_banks'] = c300_auto_pay
        return stats

    def get_not_sber_payments_stat(self, queryset) -> dict:
        """
        Возвращает статистику по оплатам без SberDoc
        :return: dict
        """
        c300_auto_pay = self._get_auto_pay_stat(queryset)
        stat = OrderedDict(
            c300_auto_pay=c300_auto_pay.pop('total'),
        )
        pay_log_stat = self.get_logs_stats(self.non_sber_accounts)
        stat.update(pay_log_stat)
        stat.update(other={'cnt': 0, 'value': 0})
        stat['auto_pay_by_banks'] = c300_auto_pay
        return stat

    def _get_auto_pay_stat(self, queryset):
        c300_auto_pay = {'total': self._get_auto_pay_stats_total(queryset)}
        c300_auto_pay.update(self._get_auto_pay_stats_by_banks(queryset))
        return c300_auto_pay

    @staticmethod
    def _get_auto_pay_stats_total(queryset):
        auto_payments = list(queryset.aggregate(
            {
                '$match': {
                    'auto_payment': True,
                    'is_deleted': {'$ne': True},
                }
            },
            {
                '$group': {
                    '_id': '',
                    'cnt': {'$sum': 1},
                    'value': {'$sum': '$value'},
                }
            },
        ))
        c300_auto_pay = {
            'cnt': 0,
            'value': 0,
        }
        if auto_payments:
            c300_auto_pay['cnt'] = auto_payments[0]['cnt']
            c300_auto_pay['value'] = round(auto_payments[0]['value'] / 100, 2)
        return c300_auto_pay

    def _get_auto_pay_stats_by_banks(self, queryset):
        tenants = queryset.filter(
            __raw__={
                'auto_payment': True,
                'is_deleted': {'$ne': True},
            },
        ).distinct(
            'account._id',
        )
        logs = AutoPaymentLog.objects(
            log__startswith='status: success',
            created__gte=self.date_from,
            created__lt=self.date_till,
            tenant__in=tenants,
        ).as_pymongo()
        results = {}
        for log in logs:
            data = log['log'].split(' ')
            card = data[7]
            value = round(float(data[5]), 2)
            bank = card[0: card.find('*')]
            result = results.setdefault(
                bank,
                {
                    'bank': bank,
                    'cnt': 0,
                    'value': 0,
                },
            )
            result['cnt'] += 1
            result['value'] += value
        return results

    def get_logs_stats(self, accounts_ids):
        queryset = PublicPaySource.objects(
            __raw__={
                'created': {
                    '$gte': self.date_from,
                    '$lt': self.date_till,
                },
                'tenant': {'$in': accounts_ids}
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '$source',
                    'num': {'$sum': 1},
                },
            },
        )
        data = {i['_id']: i['num'] for i in queryset}
        return OrderedDict(
            receipt_qrcode={
                'cnt': data.get('slip', 0),
                'value': 0,
            },
            mail_button={
                'cnt': data.get('email_button', 0),
                'value': 0,
            },
            mail_qrcode={
                'cnt': data.get('email_qr', 0),
                'value': 0,
            },
            tg_bot={
                'cnt': data.get('telegram', 0),
                'value': 0,
            },
        )

    def get_banks_stat(self, queryset=None, provider_ids=None) -> dict:
        """
        Возвращает статистику по банкам
        :return: dict
        """
        banks_stat = OrderedDict()
        match = {
            'doc.date': {'$gte': self.date_from, '$lt': self.date_till},
            'is_deleted': {'$ne': True},
        }
        if provider_ids:
            match.update({'doc.provider': {'$in': provider_ids}})
        pipeline = [
            {'$match': match},
            {
                '$project': {
                    'bank': {'$ifNull': ["$doc.bank", "н/о"]},
                    'value': 1,
                    '_type': '$doc._type'
                },
            },
            {
                '$lookup': {
                    'from': 'Provider',
                    'localField': 'bank',
                    'foreignField': '_id',
                    'as': 'bank_info',
                }
            },
            {'$unwind': '$bank_info'},
            {
                '$project': {
                    'bank': '$bank_info.NAMEP',
                    'value': 1,
                    '_type': 1,
                }
            },
            {
                '$group': {
                    '_id': {
                        'bank': '$bank',
                    },
                    'cnt': {'$sum': 1},
                    'value': {'$sum': '$value'},
                }
            },
            {
                '$project': {
                    'bank': '$_id.bank',
                    'value': 1,
                    'cnt': 1,
                    '_id': 0,
                }
            },
            {
                '$sort': {
                    'value': -1
                }
            }
        ]
        if queryset:
            payments = list(queryset.aggregate(*pipeline))
        else:
            payments = list(Payment.objects.aggregate(*pipeline))

        other_cnt = 0
        other_value = 0
        for idx, item in enumerate(payments):
            if idx < self.TOP_BANKS_CNT:
                banks_stat[item['bank']] = {
                    'name': item['bank'],
                    'cnt': item['cnt'],
                    'value': round(item['value'] / 100, 2),
                }
            else:
                other_cnt += item['cnt']
                other_value += item['value']
        if other_cnt:
            banks_stat['other'] = {
                'name': 'Остальные банки',
                'cnt': other_cnt,
                'value': round(other_value / 100, 2),
            }
        return banks_stat

    def common_stat(self) -> dict:
        """
        Возвращает общую статистику
        :return: dict
        """
        stat = OrderedDict({
            'common': {},
            'banks': {}
        })
        resp_stat = OrderedDict({
            'total_cnt': 0,
            'active_cnt': 0,
            'non_active_cnt': 0,
        })

        resp_stat = self.get_resp_stat(resp_stat, self.all_accounts,
                                       with_total=True)
        stat['common'].update(resp_stat)
        stat['common'].update(self.get_mobile_stat())
        stat['common'].update(self.get_tg_stat(self.all_accounts))
        stat['banks'].update(
            self.get_banks_stat(self.all_payments_queryset)
        )
        return stat

    def sber_stat(self) -> dict:
        """
        Возвращает статистику по реестрам Сбера
        :return: dict
        """
        stat = OrderedDict({
            'clients_cnt': {},
            'accruals_value': {},
            'common': {},
            'payments': {},
            'banks': {},
            'auto_pay': {},
        })
        resp_stat = OrderedDict({
            'total_cnt': 0,
            'active_cnt': 0,
        })

        if self.sber_providers:
            resp_stat = self.get_resp_stat(
                resp_stat,
                self.sber_accounts,
                with_total=True,
            )
            stat['accruals_value'].update(
                self.get_accruals(self.sber_providers)
            )
        stat['clients_cnt'].update(value=len(self.sber_providers))
        stat['common'].update(resp_stat)
        stat['common'].update(self.get_mobile_stat())
        stat['common'].update(self.get_tg_stat(self.sber_accounts))
        payments_queryset = self.get_payments_by_id(
            self.sber_payment_ids)
        payment_stat = self.get_sber_payment_stat(payments_queryset)
        auto_pay_by_banks = payment_stat.pop('auto_pay_by_banks')
        stat['payments'].update(payment_stat)
        stat['banks'].update(
            self.get_banks_stat(provider_ids=self.sber_providers),
        )
        stat['auto_pay'].update(auto_pay_by_banks)
        return stat

    def not_sber_stat(self) -> dict:
        """
        Возвращает статистику по всем реестрам кроме Сбера
        :return: dict
        """
        stat = OrderedDict({
            'clients_cnt': {},
            'accruals_value': {},
            'common': {},
            'payments': OrderedDict(),
            'banks': {},
            'auto_pay': {},
        })
        resp_stat = OrderedDict({
            'total_cnt': 0,
            'active_cnt': 0,
        })

        if self.non_sber_providers:
            resp_stat = self.get_resp_stat(
                resp_stat,
                self.non_sber_accounts,
                with_total=True,
            )
            stat['accruals_value'].update(
                self.get_accruals(self.non_sber_providers)
            )
        stat['clients_cnt'].update({'value': len(self.non_sber_providers)})
        stat['common'].update(resp_stat)
        stat['common'].update(self.get_mobile_stat())
        stat['common'].update(self.get_tg_stat(self.non_sber_accounts))
        payments_queryset = self.get_payments(
            provider_ids=self.non_sber_providers,
            filter={
                'doc._type': {
                    '$nin': ['ManualDoc', 'LostDoc', 'CashReceiptDoc',
                             'SberDoc', 'LostBankOrderDoc'],
                    '$size': 2}
            }
        )
        payment_stat = self.get_not_sber_payments_stat(payments_queryset)
        auto_pay_by_banks = payment_stat.pop('auto_pay_by_banks')
        stat['payments'].update(payment_stat)
        stat['banks'].update(self.get_banks_stat(payments_queryset))
        stat['auto_pay'].update(auto_pay_by_banks)
        return stat
