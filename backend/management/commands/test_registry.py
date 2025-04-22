import datetime

from bson import ObjectId

from mongoengine_connections import register_mongoengine_connections
from app.registries.core.registries_import import registry_to_payments


if __name__ == '__main__':
    register_mongoengine_connections()

    res = registry_to_payments(
        ObjectId("5d8a123cfbf974000ad4243e"),
        5,
        {
            'date': datetime.datetime.now(),
            'reg_name': 'EPS103960652230_1884710007_4703142888_40702810755000015164_227.y23',
            'sum': 2283188,
            'bank_account': '40702810755000015164',
            'provider': ObjectId("585b9f0f54dc030050774cfe"),
        },
        parent='SbolInRegistry',
    )
    # res = process_registry_readings(
    #     ObjectId('59350ee888b4560001a414a4'),
    #     {'HotWaterAreaMeter': [['20496568', 'ГВС', [3.0]]],
    #      'ColdWaterAreaMeter': [['21264473', 'ХВС', [6.0]]],
    #      'ElectricTwoRateAreaMeter': [['12074248', 'ЭЛ/ЭН', [192.0, 9.0]]]},
    #     datetime.datetime(2018, 12, 1, 0, 0),
    #     'EPS103960652230_1884812217_4703148174_40702810002100028622_033.y15',
    #     datetime.datetime(2019, 2, 4, 17, 19, 23, 698939),
    #     '14-01-2019;12-00-09;9055;9055999V;350611123569;4773245547626;477324554'
    #     '7626;ЯНИНО-1 ГП,НОВАЯ УЛ,14аК2,25;122018;21264473;ХВС;1;6;20496568;ГВС'
    #     ';1;3;12074248;ЭЛ/ЭН1;1;192;12074248;ЭЛ/ЭН2;2;9;[!];[!];;21643,63;21643'
    #     ',63;0,00',
    # )
    print(res)
