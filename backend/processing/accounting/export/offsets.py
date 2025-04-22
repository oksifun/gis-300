# -*- coding: utf-8 -*-
from processing.accounting.export.abstract import (
    JSONFileCreator,
    SummaryCreator,
)
from app.offsets.models.offset import Offset
from dateutil.relativedelta import relativedelta


class OffsetSummaryCreator(SummaryCreator):
    """Класс, создающий саммари из офсетов."""
    model = Offset
    file_type = "Расщепление"
    service_template = dict(
        # TODO Заготовка для будущего апгрейда
        use_vat=False,
        vat=0,
        vat_rate=0,
        paid=0,
        repayment=0,
        service_id='',
        service_name='',
    )

    def __init__(self, house, binds, date_from, date_till):
        super().__init__(binds=binds)
        self.house = house
        self.date_from = date_from
        self.date_till = date_till

    @property
    def match(self) -> dict:
        match = {
            'refer.account.area.house._id': self.house,
            'refer.doc.date': {
                '$gte': self.date_from,
                '$lt': self.date_till,
            },
        }
        if self.binds:
            match.update(
                self.model.get_binds_query(self.binds, raw=True),
            )
        return match
       
    @property
    def pipeline(self) -> list:
        return [
            {
                '$match': self.match
            },
            {
                '$project': {
                    'services': 1,
                    'area_type': {
                        '$cond': [
                            {
                                '$lte': [{'$size': '$refer.account.area._type'},
                                         2]
                            },
                            {'$arrayElemAt': ['$refer.account.area._type', 0]},
                            {'$arrayElemAt': ['$refer.account.area._type', -2]},
                        ]
                    },
                    'account_type': {
                        '$arrayElemAt': ['$refer.account._type', 0]
                    },
                    'account': '$refer.account._id',
                    'house_id': '$refer.account.area.house._id',
                    
                }
            },
            {
                '$lookup': {
                    'from': 'Account',
                    'localField': 'account',
                    'foreignField': '_id',
                    'as': 'account',
                }
            },
            {'$unwind': '$account'},
            {
                '$project': {
                    'services': 1,
                    'account_type': 1,
                    'area_type': 1,
                    'contract': '$account.entity_contract',
                    'house_id': 1,
                    'service': {'$literal': self.service_template},
                }
            },
            {'$unwind': '$services'},
            {
                '$project': {
                    'service': 1,
                    'value': '$services.value',
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
                }
            },
            {
                '$group': {
                    '_id': {
                        'house_id': '$house_id',
                        'file_type': self.file_type,
                        'account_type': '$account_type',
                        'service_id': '$service_id',
                        'service': '$service',
                        'area_type': '$area_type',
                        'contract': '$contract',
                    },
                    'paid': {'$sum': '$value'},
                }
            },
            {
                '$sort': {
                    '_id.house_id': 1,
                    '_id.file_type': 1,
                    '_id.account_type': 1,
                    '_id.contract': 1,
                }
            }
        ]


class OffsetJsonFileCreator(JSONFileCreator):
    values_list = ('paid',)

    @property
    def header(self):
        return {
            "file_type": self.file_type,
            "bank_date": "2019-07-01T00:00:00",
            "bank_account": "40702810420100000387",
            "description": "",
            "type": self.account_type,
            "house_address": self.address,
            "house_id": str(self.data['house_id']),
        }
