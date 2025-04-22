# -*- coding: utf-8 -*-
from processing.accounting.export.abstract import (
    JSONFileCreator,
    SummaryCreator,
)
from processing.data_producers.balance.services.vendors import (
    VendorsServicesBalance,
)


class VendorPaymentSummaryCreator(SummaryCreator):
    model = None
    file_type = "Поставщики"
    service_template = dict(
        # TODO Заготовка для будущего апгрейда
        use_vat=False,
        vat=0,
        vat_rate=0,
        invoice=0,
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
        return {}
    
    @property
    def pipeline(self) -> list:
        return []
    
    def result(self):
        sb = VendorsServicesBalance(
            houses_ids=[self.house],
            binds=self.binds,
        )
        turnovers = sb.get_credit_turnovers(
            self.date_from,
            self.date_till,
        )
        return [
            {
                '_id': {
                    'house_id': self.house,
                    'file_type': self.file_type,
                    'account_type': 'LegalTenant',
                    'service_id': key[1],
                    'service': self.service_template.copy(),
                    'area_type': 'LivingArea',
                    'contract': key[0],
                },
                'invoice': (data['payment'] +
                            data['advance_storno'] +
                            data['corrections']),
            } for key, data in turnovers.items()]
        

class VendorPaymentJsonFileCreator(JSONFileCreator):
    values_list = ('invoice',)
    
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


