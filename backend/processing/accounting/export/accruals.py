# -*- coding: utf-8 -*-
from processing.accounting.export.abstract import (
    JSONFileCreator,
    SummaryCreator,
)
from processing.models.billing.accrual import Accrual


class AccrualSummaryCreator(SummaryCreator):
    """Класс, создающий саммари по начислениям."""
    model = Accrual
    file_type = "Начисления"
    service_template = dict(
        # TODO Заготовка для будущего апгрейда
        use_vat=False,
        vat=0,
        vat_rate=0,
        total=0,
        value=0,
        shortfalls=0,
        privileges=0,
        recalculations=0,
        service_id='',
        service_name='',
    )

    def __init__(self, accrual_doc, binds):
        super().__init__(binds=binds)
        self.accrual_doc = accrual_doc

    @property
    def match(self) -> dict:
        match = {
            'doc._id': self.accrual_doc.id,
            'account.area.house._id': self.accrual_doc.house.id,
        }
        if self.binds:
            match.update(
                self.model.get_binds_query(self.binds, raw=True)
            )
        return match
    
    @property
    def pipeline(self) -> list:
        return [
            {'$match': self.match},
            {'$project': {
                'services': 1,
                'value': 1,
                'area_type': {'$cond': [
                    {'$lte': [{'$size': '$account.area._type'}, 2]},
                    {'$arrayElemAt': ['$account.area._type', 0]},
                    {'$arrayElemAt': ['$account.area._type', -2]},
                ]},
                'account_type': {'$arrayElemAt': ['$account._type', 0]},
                'account': '$account._id',
            }},
            {'$lookup': {
                'from': 'Account',
                'localField': 'account',
                'foreignField': '_id',
                'as': 'account',
            }},
            {'$unwind': '$account'},
            {'$project': {
                'services': 1,
                'account_type': 1,
                'area_type': 1,
                'contract': '$account.entity_contract',
                'house_id': '$account.area.house._id',
                'service': {'$literal': self.service_template},
                'value': 1,
            }},
            {'$unwind': '$services'},
            {'$project': {
                'value': '$services.value',
                'shortfalls': '$services.totals.shortfalls',
                'privileges': '$services.totals.privileges',
                'recalculations': '$services.totals.recalculations',
                'total': {'$add': [
                    '$services.value',
                    '$services.totals.shortfalls',
                    '$services.totals.privileges',
                    '$services.totals.recalculations'
                ]},
                'service': 1,
                'service_id': {
                    '$cond': {
                        'if': {
                            '$eq': [
                                '$services.service_type',
                                self.penalty_id,
                            ]
                        },
                        'then': 'penalties',
                        'else': '$services.service_type',
                    },
                },
                'account_type': 1,
                'area_type': 1,
                'contract': 1,
                'house_id': 1,
            }},
            {'$group': {
                '_id': {
                    'house_id': '$house_id',
                    'file_type': self.file_type,
                    'account_type': '$account_type',
                    'service_id': '$service_id',
                    'service': '$service',
                    'area_type': '$area_type',
                    'contract': '$contract',
                },
                'value': {'$sum': '$value'},
                'shortfalls': {'$sum': '$shortfalls'},
                'privileges': {'$sum': '$privileges'},
                'recalculations': {'$sum': '$recalculations'},
                'total': {'$sum': '$total'},
            }},
            {
                '$sort': {
                    '_id.house_id': 1,
                    '_id.file_type': 1,
                    '_id.account_type': 1,
                    '_id.contract': 1,
                }
            }
        ]


class AccrualJsonFileCreator(JSONFileCreator):
    values_list = (
        'value', 'shortfalls', 'privileges', 'recalculations', 'total',
    )
    
    def __init__(self, data: dict, accrual_doc):
        super().__init__(data)
        self.accrual_doc = accrual_doc

    @property
    def header(self):
        return {
            "file_type": self.file_type,
            "doc_id": str(self.accrual_doc.id),
            "doc_date": self.accrual_doc.date.isoformat(),
            "description": self.accrual_doc.description,
            "type": self.account_type,
            "house_address": self.address,
            "house_id": str(self.data['house_id']),
        }
