# -*- coding: utf-8 -*-
from processing.accounting.export.abstract import (
    DataTransformer, SummaryCreator)
from processing.models.billing.accrual import Accrual


class PenaltySummaryCreator(SummaryCreator):
    """Класс, создающий саммари по пеням."""
    model = Accrual
    file_type = None
    service_template = dict()

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
                'penalties': '$totals.penalties',
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
            {
                '$project': {
                    'account_type': 1,
                    'area_type': 1,
                    'contract': '$account.entity_contract',
                    'house_id': '$account.area.house._id',
                    'penalties': 1,
                }
            },
            {
                '$group': {
                    '_id': {
                        'house_id': '$house_id',
                        'account_type': '$account_type',
                        'area_type': '$area_type',
                        'contract': '$contract',
                    },
                    'penalties': {'$sum': '$penalties'}
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'house_id': '$_id.house_id',
                    'account_type': '$_id.account_type',
                    'contract': '$_id.contract',
                    'area_type': '$_id.area_type',
                    'penalties': 1,
                }
            },
            {
                '$sort': {
                    'house_id': 1,
                    'account_type': 1,
                    'contract': 1,
                    'area_type:': 1,
                }
            },
        ]
    
    def result(self):
        result = dict()
        penalties = self.model.objects.aggregate(*self.pipeline)
        for penalty in penalties:
            key = (
                penalty['house_id'],
                penalty['account_type'],
                penalty.get('contract'),
                DataTransformer.rename_area_type(penalty['area_type']),
            )
            result[key] = penalty['penalties']
        return result
