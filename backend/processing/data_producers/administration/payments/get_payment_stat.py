from datetime import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from lib.gridfs import put_file_to_gridfs
from processing.data_producers.administration.payments.payment_report import \
    PaymentReport


def get_payments_stat_by_months(month_till, months=1):
    date_from = month_till
    date_finish = month_till - relativedelta(months=months - 1)
    while date_from >= date_finish:
        date_till = date_from + relativedelta(months=1)
        filename = f'payment_month_stat_' \
                   f'{date_from.strftime("%Y.%m")}.xlsx'
        report = PaymentReport(**{
            'date_from': date_from,
            'date_till': date_till,
        })
        report.get_xlsx_openpyxl(filename)
        print('PaymentReport successfully created')
        with open(filename, mode='rb') as f:
            file = put_file_to_gridfs(
                'PaymentReport',
                ObjectId(),
                f.read(),
                filename=filename,
            )
            print(file)
        date_from -= relativedelta(months=1)


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()
    get_payments_stat_by_months(datetime(2021, 7, 1), 1)
