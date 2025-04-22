from processing.data_producers.forms.accrual_doc import *


if __name__ == '__main__':
    register_mongoengine_connections()
    r = get_accruals_with_grouped_tariffs(
        doc_id=ObjectId('5a74215ecc898c003089d70f'),
        account_id=ObjectId('5a53591718a58f000107b50e')
    )
    for g in r:
        print(g['title'])
        for gg in g['data']:
            print('  ', gg['title'])
            print('    ', gg['service_types'])
            for gggg in gg['not_grouped_data']:
                print('      ', gggg)
            for ggg in gg['grouped_data']:
                print('    ', ggg['title'])
                print('      ', ggg['service_types'])
                for gggg in ggg['data']:
                    print('      ', gggg)
    r = get_balance_by_accrual_doc(
        doc_id=ObjectId('5a74215ecc898c003089d70f'),
        account_id=ObjectId('5a53591718a58f000107b50e'),
        provider_id=None
    )
    print('balance', r)

