from dateutil.relativedelta import relativedelta

from processing.models.billing.accrual import Accrual
from app.offsets.models.offset import Offset
from processing.models.billing.payment import Payment
from processing.models.choices import AccrualDocumentStatus


CONDUCTED_STATUSES = [AccrualDocumentStatus.READY, AccrualDocumentStatus.EDIT]


class AccountBalance:

    def __init__(self, account_id, provider_id=None, binds=None):
        self.account = account_id
        self.provider = provider_id
        self.binds = binds

    def get_month_balance(self, month_on, sectors):
        result = 0
        match = {
            'account._id': self.account,
            'is_deleted': {'$ne': True},
            'sector_code': {'$in': sectors},
            'month': {'$lt': month_on},
            'doc.status': {'$in': CONDUCTED_STATUSES},
        }
        if self.binds:
            match.update(Accrual.get_binds_query(self.binds, raw=True))
        accruals = list(Accrual.objects.aggregate(
            {'$match': match},
            {'$group': {
                '_id': '',
                'val': {'$sum': '$debt'},
            }},
        ))
        if accruals:
            result += accruals[0]['val']
        match = {
            'refer.account._id': self.account,
            'refer.sector_code': {'$in': sectors},
            'accrual.month': {'$lt': month_on},
        }
        if self.binds:
            match.update(Offset.get_binds_query(self.binds, raw=True))
        offsets = list(Offset.objects.aggregate(
            {'$match': match},
            {'$group': {
                '_id': '',
                'val': {'$sum': '$total'},
            }},
        ))
        if offsets:
            result -= offsets[0]['val']
        return result

    def get_date_balance(self, date_on, sectors, use_bank_date=True,
                         group_by_sector=False):
        result = {} if group_by_sector else 0
        match = {
            'account._id': self.account,
            'is_deleted': {'$ne': True},
            'sector_code': {'$in': sectors},
            'doc.date': {'$lt': date_on},
            'doc.status': {'$in': CONDUCTED_STATUSES},
        }
        if self.binds:
            match.update(Accrual.get_binds_query(self.binds, raw=True))
        accruals = list(Accrual.objects.aggregate(
            {'$match': match},
            {'$group': {
                '_id': '$sector_code' if group_by_sector else '',
                'val': {'$sum': '$value'},
            }},
        ))
        if accruals:
            if group_by_sector:
                result = {a['_id']: a['val'] for a in accruals}
            else:
                result += accruals[0]['val']
        match = {
            'account._id': self.account,
            'sector_code': {'$in': sectors},
            'doc.date' if use_bank_date else 'date': {'$lt': date_on},
            'is_deleted': {'$ne': True},
        }
        if self.binds:
            match.update(Payment.get_binds_query(self.binds, raw=True))
        offsets = list(Payment.objects.aggregate(
            {'$match': match},
            {'$group': {
                '_id': '$sector_code' if group_by_sector else '',
                'val': {'$sum': '$value'}
            }},
        ))
        if offsets:
            if group_by_sector:
                for o in offsets:
                    result.setdefault(o['_id'], 0)
                    result[o['_id']] -= o['val']
            else:
                result -= offsets[0]['val']
        return result


class AccountsListBalance:

    ACCOUNTS_STEP = 100

    def __init__(self, accounts, provider_id=None, binds=None):
        self.accounts = accounts
        self.provider = provider_id
        self.binds = binds

    def get_date_balance(self, date_on, sectors=None, use_bank_date=True,
                         group_by_sector=False):
        ix = 0
        result = {} if group_by_sector else 0
        while ix < len(self.accounts) + self.ACCOUNTS_STEP:
            accounts = self.accounts[ix: ix + self.ACCOUNTS_STEP]
            self._update_balance(
                result,
                accounts,
                date_on,
                sectors,
                use_bank_date,
                group_by_sector
            )
            ix += self.ACCOUNTS_STEP
        return result

    def _update_balance(self, data, accounts, date_on, sectors, use_bank_date,
                        group_by_sector):
        match = {
            'account._id': {'$in': accounts},
            'is_deleted': {'$ne': True},
            'doc.date': {'$lt': date_on},
            'doc.status': {'$in': CONDUCTED_STATUSES},
            **({'sector_code': {'$in': sectors}} if sectors else {})
        }
        if self.binds:
            match.update(Accrual.get_binds_query(self.binds, raw=True))
        accruals = list(Accrual.objects.aggregate(
            {'$match': match},
            {'$group': {
                '_id': '$sector_code' if group_by_sector else '',
                'val': {'$sum': '$value'}
            }},
        ))
        if accruals:
            if group_by_sector:
                for a in accruals:
                    data.setdefault(a['_id'], 0)
                    data[a['_id']] += a['val']
            else:
                data += accruals[0]['val']
        match = {
            'account._id': {'$in': accounts},
            'doc.date' if use_bank_date else 'date': {'$lt': date_on},
            'is_deleted': {'$ne': True},
            **({'sector_code': {'$in': sectors}} if sectors else {})
        }
        if self.binds:
            match.update(Payment.get_binds_query(self.binds, raw=True))
        offsets = list(Payment.objects.aggregate(
            {'$match': match},
            {'$group': {
                '_id': '$sector_code' if group_by_sector else '',
                'val': {'$sum': '$value'}
            }}
        ))
        if offsets:
            if group_by_sector:
                for o in offsets:
                    data.setdefault(o['_id'], 0)
                    data[o['_id']] -= o['val']
            else:
                data -= offsets[0]['val']
        return data


class HouseAccountsBalance:

    def __init__(self, house, accounts_ids=None,
                 accounts_filter=None, binds=None,  account_types=None,
                 area_types=None,
                 is_developer=None):
        self.accounts = accounts_ids
        self.house = house
        self.accounts_filter = accounts_filter
        self.binds = binds
        self.area_types = area_types
        self.is_developer = is_developer
        self.account_types = account_types

    def get_date_balance(self, date_on, sectors, use_bank_date=True):
        result = {}
        # начисления
        accruals = self._get_accruals(date_on, sectors)
        if accruals:
            for account in accruals:
                result[account['account_id']] = account
        # оплаты
        payments = self._get_payments(date_on, sectors, use_bank_date)
        if payments:
            for account in payments:
                account_data = result.setdefault(account['account_id'], {
                    'account_id': account['account_id'],
                    'area_id': account['area_id'],
                    'area_number': account['area_number'],
                    'area_order': account['area_order'],
                    'val': 0,
                })
                account_data['val'] -= account['val']
        return result

    def get_turnovers(self, date_from, date_till, sectors, use_bank_date=True):
        debit = self.get_debit_turnovers(
            date_from,
            date_till,
            sectors,
        )
        credit = self.get_credit_turnovers(
            date_from,
            date_till,
            sectors,
            use_bank_date,
        )
        result = {k: (v['val'], 0) for k, v in debit.items()}
        for account, data in credit.items():
            account_data = result.get(account)
            if account_data:
                result[account] = (account_data[0], data['val'])
            else:
                result[account] = (0, data['val'])
        return result

    def get_debit_turnovers(self, date_from, date_till, sectors):
        accruals = self._get_accruals(
            date_on=date_till + relativedelta(days=1),
            sectors=sectors,
            date_from=date_from,
        )
        return {a['account_id']: a for a in accruals}

    def get_credit_turnovers(self, date_from, date_till, sectors,
                             use_bank_date=True):
        payments = self._get_payments(
            date_on=date_till + relativedelta(days=1),
            sectors=sectors,
            date_from=date_from,
            use_bank_date=use_bank_date,
        )
        return {p['account_id']: p for p in payments}

    def _get_accruals(self, date_on, sectors, date_from=None):
        date_match = {'$lt': date_on}
        if date_from:
            date_match['$gte'] = date_from
        match_dict = {
            'account.area.house._id': self.house,
            'is_deleted': {'$ne': True},
            'sector_code': {'$in': sectors},
            'doc.date': date_match,
            'doc.status': {'$in': CONDUCTED_STATUSES}
        }
        if self.accounts is not None:
            match_dict['account._id'] = {'$in': self.accounts}
        if self.binds:
            match_dict.update(Accrual.get_binds_query(self.binds, raw=True))
        if self.area_types:
            match_dict.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match_dict.update({'account.is_developer': True})
        elif self.is_developer is False:
            match_dict.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match_dict.update({'account._type': self.account_types})
        aggregation_pipeline = [
            {'$match': match_dict},
            {'$group': {
                '_id': '$account._id',
                'area_id': {'$first': '$account.area._id'},
                'area_number': {'$first': '$account.area.str_number'},
                'area_order': {'$first': '$account.area.order'},
                'val': {'$sum': '$value'},
            }},
            {'$project': {
                'account_id': '$_id',
                'area_id': 1,
                'area_number': 1,
                'area_order': 1,
                'val': 1,
                '_id': 0
            }}
        ]
        if self.accounts_filter:
            self.extend_aggregation_by_account_filter(
                aggregation_pipeline=aggregation_pipeline,
                areas_list=self.accounts_filter.get('areas_list'),
                porches_list=self.accounts_filter.get('porches_list'),
                property_types=self.accounts_filter.get('property_types'),
                area_types=self.accounts_filter.get('area_types'),
                account_types=self.accounts_filter.get('account_types'),
                advanced_filter=self.accounts_filter.get('advanced_filter')
            )
            aggregation_pipeline.append({'$project': {
                'account_id': 1,
                'area_id': 1,
                'area_number': 1,
                'area_order': 1,
                'val': 1
            }})
        return list(Accrual.objects.aggregate(*aggregation_pipeline))

    def _get_payments(self, date_on, sectors, use_bank_date, date_from=None):
        date_match = {'$lt': date_on}
        if date_from:
            date_match['$gte'] = date_from
        match_dict = {
            'account.area.house._id': self.house,
            'sector_code': {'$in': sectors},
            'doc.date' if use_bank_date else 'date': date_match,
            'is_deleted': {'$ne': True},
        }
        if self.accounts is not None:
            match_dict['account._id'] = {'$in': self.accounts}
        if self.binds:
            match_dict.update(Payment.get_binds_query(self.binds, raw=True))
        if self.area_types:
            match_dict.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match_dict.update({'account.is_developer': True})
        elif self.is_developer is False:
            match_dict.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match_dict.update({'account._type': self.account_types})
        aggregation_pipeline = [
            {'$match': match_dict},
            {'$group': {
                '_id': '$account._id',
                'area_id': {'$first': '$account.area._id'},
                'area_number': {'$first': '$account.area.str_number'},
                'area_type': {'$first': '$account.area._type'},
                'area_order': {'$first': '$account.area.order'},
                'val': {'$sum': '$value'}
            }},
            {'$project': {
                'account_id': '$_id',
                'area_id': 1,
                'area_number': 1,
                'area_type': 1,
                'area_order': 1,
                'val': 1,
                '_id': 0
            }}
        ]
        if self.accounts_filter:
            self.extend_aggregation_by_account_filter(
                aggregation_pipeline=aggregation_pipeline,
                areas_list=self.accounts_filter.get('areas_list'),
                porches_list=self.accounts_filter.get('porches_list'),
                property_types=self.accounts_filter.get('property_types'),
                area_types=self.accounts_filter.get('area_types'),
                account_types=self.accounts_filter.get('account_types'),
                advanced_filter=self.accounts_filter.get('advanced_filter')
            )
            aggregation_pipeline.append({'$project': {
                'account_id': 1,
                'area_id': 1,
                'area_number': 1,
                'area_order': 1,
                'val': 1
            }})
        return list(Payment.objects.aggregate(*aggregation_pipeline))

    _PROPERTY_TYPES = {'private', 'government', 'municipal', None}

    @classmethod
    def extend_aggregation_by_account_filter(cls, aggregation_pipeline,
                                             areas_list, porches_list,
                                             property_types, area_types,
                                             account_types, advanced_filter):
        final_match = {}
        if areas_list:
            aggregation_pipeline.extend([
                {
                    '$lookup': {
                        'from': 'Area',
                        'localField': 'area_id',
                        'foreignField': '_id',
                        'as': 'area',
                    },
                },
                {
                    '$unwind': '$area',
                },
            ])
            agg_group = aggregation_pipeline[1]['$group']
            agg_group['area_number_num'] = {'$first': '$account.area.number'}
            agg_project = aggregation_pipeline[2]['$project']
            agg_project['area_number_num'] = 1
            final_match['area_number_num'] = {'$in': areas_list}
        if property_types and not (cls._PROPERTY_TYPES - property_types):
            aggregation_pipeline.extend([
                {
                    '$lookup': {
                        'from': 'Account',
                        'localField': 'account_id',
                        'foreignField': '_id',
                        'as': 'account',
                    }},
                {
                    '$unwind': '$account',
                },
            ])
            final_match['account.statuses.ownership.type'] = {
                '$in': property_types,
            }
        if property_types:
            aggregation_pipeline.append(final_match)
        if porches_list:
            aggregation_pipeline.extend([
                {'$lookup': {
                    'from': 'House',
                    'localField': 'area.house._id',
                    'foreignField': '_id',
                    'as': 'house'
                }},
                {'$unwind': '$house'},
                {'$unwind': {
                    'path': '$house.porches',
                }},
                {'$project': {
                    '_id': 1,
                    'account': 1,
                    'area': 1,
                    'house': 1,
                    'eq_area_house_porch': {
                        '$eq': ['$area.porch', '$house.porches._id']}
                }},
                {'$match': {
                    'eq_area_house_porch': True,
                }},

                # Фильтруем по номерам помещений и подъездов
                {'$match': {
                    'house.porches.number': {'$in': porches_list}
                }}
            ])
        if advanced_filter:
            aggregation_pipeline.append({'$match': advanced_filter})


class HousesBalance:

    def __init__(self, houses,
                 binds=None,
                 account_types=None,
                 area_types=None,
                 is_developer=False):
        self.houses = houses
        self.binds = binds
        self.area_types = area_types
        self.is_developer = is_developer
        self.account_types = account_types

    def get_date_balance(self, date_on, sectors, use_bank_date=True,
                         split_areas=False):
        if split_areas:
            return self._get_splitted_date_balance(
                date_on, sectors, use_bank_date
            )
        else:
            return self._get_date_balance(date_on, sectors, use_bank_date)

    def _get_date_balance(self, date_on, sectors, use_bank_date=True):
        result = {}
        # начисления
        match_dict = {
            'account.area.house._id': {'$in': self.houses},
            'is_deleted': {'$ne': True},
            'sector_code': {'$in': sectors},
            'doc.date': {'$lt': date_on},
            'doc.status': {'$in': CONDUCTED_STATUSES},
        }
        if self.binds:
            match_dict.update(Accrual.get_binds_query(self.binds, raw=True))
        if self.area_types:
            match_dict.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match_dict.update({'account.is_developer': True})
        elif self.is_developer is False:
            match_dict.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match_dict.update({'account._type': self.account_types})
        aggregation_pipeline = [
            {'$match': match_dict},
            {'$group': {
                '_id': '$account.area._id',
                'house_id': {'$first': '$account.area.house._id'},
                'value': {'$sum': '$value'},
            }},
        ]
        aggregation_pipeline.extend([
            {'$group': {
                '_id': '$house_id',
                'val': {'$sum': '$value'},
            }},
            {'$lookup': {
                'from': 'House',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'house',
            }},
            {'$unwind': '$house'},
            {'$project': {
                '_id': 1,
                'val': 1,
                'address': '$house.address'
            }},
        ])
        accruals = list(Accrual.objects.aggregate(*aggregation_pipeline))
        if accruals:
            for house in accruals:
                result[house['_id']] = house
        # оплаты
        match_dict = {
            'account.area.house._id': {'$in': self.houses},
            'sector_code': {'$in': sectors},
            'doc.date' if use_bank_date else 'date': {'$lt': date_on},
            'is_deleted': {'$ne': True},
        }
        if self.binds:
            match_dict.update(Payment.get_binds_query(self.binds, raw=True))
        if self.area_types:
            match_dict.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match_dict.update({'account.is_developer': True})
        elif self.is_developer is False:
            match_dict.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match_dict.update({'account._type': self.account_types})
        aggregation_pipeline = [
            {'$match': match_dict},
            {'$group': {
                '_id': '$account.area._id',
                'house_id': {'$first': '$account.area.house._id'},
                'value': {'$sum': '$value'},
            }},
        ]
        aggregation_pipeline.extend([
            {'$group': {
                '_id': '$house_id',
                'val': {'$sum': '$value'},
            }},
            {'$lookup': {
                'from': 'House',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'house',
            }},
            {'$unwind': '$house'},
            {'$project': {
                '_id': 1,
                'val': 1,
                'address': '$house.address'
            }},
        ])
        payments = list(Payment.objects.aggregate(*aggregation_pipeline))
        if payments:
            for house in payments:
                house_data = result.setdefault(house['_id'], {
                    '_id': house['_id'],
                    'address': house['address'],
                    'val': 0,
                })
                house_data['val'] -= house['val']
        return result

    def _get_splitted_date_balance(self, date_on, sectors, use_bank_date=True):
        result = {}
        # начисления
        match_dict = {
            'account.area.house._id': {'$in': self.houses},
            'is_deleted': {'$ne': True},
            'sector_code': {'$in': sectors},
            'doc.date': {'$lt': date_on},
            'doc.status': {'$in': CONDUCTED_STATUSES},
        }
        if self.binds:
            match_dict.update(Accrual.get_binds_query(self.binds, raw=True))
        if self.area_types:
            match_dict.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match_dict.update({'account.is_developer': True})
        elif self.is_developer is False:
            match_dict.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match_dict.update({'account._type': self.account_types})
        aggregation_pipeline = [
            {'$match': match_dict},
            {'$group': {
                '_id': '$account.area._id',
                'house_id': {'$first': '$account.area.house._id'},
                'area_type': {'$first': '$account.area._type'},
                'value': {'$sum': '$value'},
            }},
            {'$project': {
                '_id': 1,
                'house_id': 1,
                'value': 1,
                'area_type': {'$cond': [
                    {'$lte': [{'$size': '$area_type'}, 2]},
                    {'$arrayElemAt': ['$area_type', 0]},
                    {'$arrayElemAt': ['$area_type', -2]},
                ]},
            }},
            {'$group': {
                '_id': {
                    'house': '$house_id',
                    'area_type': '$area_type',
                },
                'val': {'$sum': '$value'},
            }},
            {'$lookup': {
                'from': 'House',
                'localField': '_id.house',
                'foreignField': '_id',
                'as': 'house',
            }},
            {'$unwind': '$house'},
            {'$project': {
                '_id': '$_id.house',
                'area_type': '$_id.area_type',
                'val': 1,
                'address': '$house.address'
            }},
        ]
        accruals = list(Accrual.objects.aggregate(*aggregation_pipeline))
        if accruals:
            for house in accruals:
                result[(house['_id'], house['area_type'])] = house
        # оплаты
        match_dict = {
            'account.area.house._id': {'$in': self.houses},
            'sector_code': {'$in': sectors},
            'doc.date' if use_bank_date else 'date': {'$lt': date_on},
            'is_deleted': {'$ne': True},
        }
        if self.binds:
            match_dict.update(Accrual.get_binds_query(self.binds, raw=True))
        if self.area_types:
            match_dict.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match_dict.update({'account.is_developer': True})
        elif self.is_developer is False:
            match_dict.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match_dict.update({'account._type': self.account_types})
        aggregation_pipeline = [
            {'$match': match_dict},
            {'$group': {
                '_id': '$account.area._id',
                'house_id': {'$first': '$account.area.house._id'},
                'area_type': {'$first': '$account.area._type'},
                'value': {'$sum': '$value'},
            }},
            {'$project': {
                '_id': 1,
                'house_id': 1,
                'value': 1,
                'area_type': {'$cond': [
                    {'$lte': [{'$size': '$area_type'}, 2]},
                    {'$arrayElemAt': ['$area_type', 0]},
                    {'$arrayElemAt': ['$area_type', -2]},
                ]},
            }},
            {'$group': {
                '_id': {
                    'house': '$house_id',
                    'area_type': '$area_type',
                },
                'val': {'$sum': '$value'},
            }},
            {'$lookup': {
                'from': 'House',
                'localField': '_id.house',
                'foreignField': '_id',
                'as': 'house',
            }},
            {'$unwind': '$house'},
            {'$project': {
                '_id': '$_id.house',
                'area_type': '$_id.area_type',
                'val': 1,
                'address': '$house.address',
            }},
        ]
        payments = list(Payment.objects.aggregate(*aggregation_pipeline))
        if payments:
            for house in payments:
                house_data = result.setdefault(
                    (house['_id'], house['area_type']),
                    {
                        '_id': house['_id'],
                        'area_type': house['area_type'],
                        'address': house['address'],
                        'val': 0,
                    }
                )
                house_data['val'] -= house['val']
        return result

