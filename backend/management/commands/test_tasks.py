import datetime

from bson import ObjectId

from mongoengine_connections import register_mongoengine_connections
from app.offsets.tasks.calculate_offsets import try_calculate

if __name__ == "__main__":
    register_mongoengine_connections()

    d = datetime.datetime.now()

    # get_registry_from_file(
    #     **{
    #         'file_id': ObjectId('63234027772728000cb79f47'),
    #         'provider_id': ObjectId('526234b0e0e34c4743821ab4'), 'actor_id': ObjectId('5262c99ce0e34c1fb79a6016'), 'parent': 'ManualRegistryTask'},
    # )
    # provider = Provider.objects(
    #     id='526234b0e0e34c4743821b4c',
    # ).only(
    #     'mailing',
    # ).get()
    # mailing = dict(provider.mailing.to_mongo())
    # tenant = Tenant.objects(pk=ObjectId('5262c6d3e0e34c1fca9a4157')).get()
    # accrual = Accrual.objects(
    #     account__id=tenant.id,
    #     doc__id='606d80f4239c720042435d1b',
    # ).as_pymongo().get()
    # send_bill_file_email(tenant, accrual, mailing)

    # export_gcjs_file(
    #     'AccrualsExport',
    #     ObjectId('5a2548763588ec00300758c3'),
    #     datetime.datetime(2021, 10, 1, 0, 0),
    #     ['rent'],
    # )

    # res = compare_bank_statement(
    #     ObjectId('6005881804290600092d0c34'),
    # )

    # make_issuing_documents_query(
    #     contract_id=ObjectId('5d8b06465a58df0013175f11'),
    #     date=datetime.datetime.now(),
    #     period=datetime.datetime.now(),
    #     email=True,
    #     bill=True,
    #     certificate=True,
    #     binds=None
    # )

    # res = compare_bank_statement(bs_id=ObjectId('60802326599646000a6930f1'))

    # res = get_registry_from_file(
    #     file_id=ObjectId('5cee39e5d135f3000a222b42'),
    #     provider_id=ObjectId('54d9f45df3b7d439807b010a'),
    # )

    # calldebtor(
    #     **{
    #         'phonenumbers': ['89119204071'],
    #         'task_id': '5df2094f6928420032d5cf5c',
    #         'account_id': '5bd1a87c9e92680032191477',
    #         'provider_id': '58c6a0cc8b7f74003d3344e7',
    #     }
    # )

    # res = sber_registry_to_payments(
    #     ObjectId("5f58f2abdf1a1a000ab94c44"),
    #     0,
    #     {
    #         "bank_account": "40702810955080001558",
    #         "date": datetime.datetime(2020, 9, 9),
    #         "sum": 2273623,
    #         "provider": ObjectId("526234b3e0e34c4743822066"),
    #         "reg_name": "EPS103960652230_1100940211_7801534550_"
    #                     "40702810955080001558_493.y08"
    #     },
    #     ''
    # )

    # res = get_registries_from_mail(
    #     datetime.datetime(2021, 11, 26),
    #     test_mode=True,
    # )

    # res = parse_registry(ObjectId("5cefd61a341abc0014c9b45a"))

    res = try_calculate(
        tenant_id=ObjectId("5fbfd4e25185fc0001eeed27"),
        sector='rent',
        uuid='a3b7a431-7978-4b4c-933f-affbf4e26ccf',
    )

    # res = get_cash_fiscal_numbers(
    #     datetime.datetime.now(),
    #     ObjectId("5c6d77d6fed352001037e9e2"),
    # )

    # res = accrual_summary_export(
    #     provider_id=ObjectId('5a254b9e3588ec0030075957'),
    #     doc_ids=(
    #         ObjectId('5d39c1a1806250002d92ae03'),
    #         ObjectId("5d3ab54f5d6569002a626cc8"),
    #         ObjectId("5d3ab77b5d65690039626daa"),
    #         ObjectId("5d3ab86b67c59e0031b53a21"),
    #         ObjectId("5d3ab987a5624300361358f4"),
    #         ObjectId("5d3aa0f9e3805f00579d57a1"),
    #     ),
    #     task_id=ObjectId('5d8dd77eda6a70000a95806a'),
    # )

    # run_custom_script(
    #     ObjectId("5cb5eed31b94a7000a011b86"),
    #     'change_meters_check_date',
    #     **{
    #         'house_id': '526237d1e0e34c524382c073',
    #         'check_date': '10.01.2014',
    #         'update_all_fields': '1',
    #         'first_area_number': '1',
    #         'last_area_number': '20',
    #     }
    # )

    print('завершено', datetime.datetime.now() - d, res)

