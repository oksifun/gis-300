import csv
from datetime import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from processing.data_producers.export.administration.payers import \
    get_tenants_with_sber_autopay
from processing.models.billing.account import Tenant
from app.house.models.house import House
from processing.models.billing.payment import Payment
from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids

TABLEHEAD = [
    "ОРГАНИЗАЦИЯ",
    "АДРЕС",
    "ФАМИЛИЯ",
    "ИМЯ ОТЧЕСТВО",
    "EMAIL",
    "ЛИЦЕВОЙ СЧЕТ"
]


def start_getting_data(*args):
    if 'autopay' in args:
        get_data_tables(autopay=True)
    if 'has_lk' in args:
        get_data_tables(has_lk=True)
    if 'sber_pay' in args:
        get_data_tables(sber_pay=True)
    if 'tinkoff_pay' in args:
        get_data_tables(tinkoff_pay=True)
    if 'pes_pay' in args:
        get_data_tables(pes_pay=True)
    if 'is_owner' in args:
        get_data_tables(is_owner=True)


def get_data_tables(autopay=False, has_lk=False, sber_pay=False,
                    tinkoff_pay=False, pes_pay=False, is_owner=False):
    #_create_files_to_data()
    clients_ids = get_crm_client_ids()
    print('|'.join(TABLEHEAD))
    for client_id in clients_ids:
        client = Provider.objects(
            pk=client_id,
        ).first()
        if not client:
            continue
        client_id = client.id
        houses = _get_houses_by_client(client_id)
        if autopay:
            for house in houses:
                _type = "Автоплатеж сбера"
                _get_sber_autopay_data(house, client)
        if has_lk:
            for house in houses:
                _type = "Есть ЛК"
                _get_tenants_with_cabinet(house, client)
        if pes_pay:
            for house in houses:
                _type = "Есть платеж ПЭС"
                _get_payments_pes_info(client, house)
        if sber_pay:
            for house in houses:
                _type = "Есть платеж Сбер"
                _get_payments_sber_info(client, house)
        if tinkoff_pay:
            for house in houses:
                _type = "Есть платеж Тинькофф"
                _get_payments_tinkoff_info(client, house)
        if is_owner:
            for house in houses:
                _get_owners_info(client, house)


def _create_files_to_data():
    filenames = [
        'autopay_Sber.csv',
        'has_lk.csv',
        'has_payments_in_PES.csv',
        'has_payments_in_Tinkoff.csv',
        'has_payments_in_Sber.csv'
    ]
    for filename in filenames:
        full_name = "../csv_files/" + filename
        file = open(full_name, 'w')
        wr = csv.writer(file, quoting=csv.QUOTE_ALL)
        wr.writerow(TABLEHEAD)
        file.close()


def _get_houses_by_client(client_id):
    houses = House.objects(
        service_binds__provider=client_id,
    ).as_pymongo()
    return houses


def _add_data_to_pes_table(tenant, house, client):
    full_name = "../csv_files/" + "has_payments_in_PES.csv"
    file = open(full_name, 'a')
    wr = csv.writer(file, quoting=csv.QUOTE_ALL)
    tenant_data = [
        client['str_name'],
        house['address'],
        tenant['last_name'],
        f"{tenant['first_name']} {tenant['patronymic_name']}",
        tenant['email'],
        tenant['number']
    ]
    wr.writerow(tenant_data)
    file.close()


def _get_payments_tinkoff_info(client, house):
    tenants_ids_with_payments = Payment.objects(
        date__gte=datetime(2020, 1, 1),
        date__lte=datetime(2021, 1, 1),
        account__area__house__id=house['_id'],
        doc__bank=ObjectId("576c62f23ed3f90006639721"),
    ).distinct('account.id')
    if tenants_ids_with_payments:
        tenants_with_payments = Tenant.objects(
            id__in=tenants_ids_with_payments
        ).as_pymongo()
        for tenant in tenants_with_payments:
            if 'email' in tenant and tenant['email']:
                full_name = "../csv_files/" + "has_payments_in_Tinkoff.csv"
                _put_data_to_table(tenant, client, house)


def _get_payments_sber_info(client, house):
    tenants_ids_with_payments = Payment.objects(
        date__gte=datetime(2020, 1, 1),
        date__lte=datetime(2021, 1, 1),
        account__area__house__id=house['_id'],
        doc__bank=ObjectId("54cb2547f3b7d455bbabd3ef"),
    ).distinct('account.id')
    if tenants_ids_with_payments:
        tenants_with_payments = Tenant.objects(
            id__in=tenants_ids_with_payments
        ).as_pymongo()
        for tenant in tenants_with_payments:
            if 'email' in tenant and tenant['email']:
                full_name = "../csv_files/" + "has_payments_in_Sber.csv"
                _put_data_to_table(tenant, client, house)


def _get_payments_pes_info(client, house):
    tenants_ids_with_payments = Payment.objects(
        date__gte=datetime(2020, 1, 1),
        date__lte=datetime(2021, 1, 1),
        account__area__house__id=house['_id'],
        doc__bank__in=[ObjectId("54cb2598f3b7d455bbabe051"), ObjectId("54cb2598f3b7d445bbabe055")],
    ).distinct('account.id')
    if tenants_ids_with_payments:
        tenants_with_payments = Tenant.objects(
            id__in=tenants_ids_with_payments
        ).as_pymongo()
        for tenant in tenants_with_payments:
            if 'email' in tenant and tenant['email']:
                full_name = "../csv_files/" + "has_payments_in_PES.csv"
                _put_data_to_table(tenant, client, house)


def _get_sber_autopay_data(house, client):
    date_till = datetime.now()
    date_from = date_till - relativedelta(months=3)
    tenants_autopay = get_tenants_with_sber_autopay(date_from=date_from,
                                            date_till=date_till,
                                            house_id=house['_id'])
    for tenant_id in tenants_autopay:
        tenant = Tenant.objects(
            id=tenant_id
        ).as_pymongo()
        tenant = tenant[0]
        if 'email' in tenant and tenant['email']:
            _put_data_to_autopay_sber_table(tenant, client, house)


def _put_data_to_autopay_sber_table(tenant, client, house):
    filename = 'autopay_Sber.csv'
    _put_data_to_table(tenant, client, house)


def _put_data_to_table(tenant, client, house):
    #full_name = "../csv_files/" + tablename
    #file = open(full_name, 'a')
    #wr = csv.writer(file, quoting=csv.QUOTE_ALL)
    address = ''
    last_name = ''
    first_name = ""
    patronymic_name = ''
    if 'address' in house:
        address = house['address']
    if 'last_name' in tenant:
        last_name = tenant['last_name']
    if 'first_name' in tenant:
        first_name = tenant['first_name']
    if 'patronymic_name' in tenant:
        patronymic_name = tenant['patronymic_name']
    if 'patronymic_name' in tenant:
        patronymic_name = tenant['patronymic_name']
    tenant_data = [
        str(client),
        str(address),
        str(last_name),
        str(f"{first_name} {patronymic_name}"),
        str(tenant['email']),
        str(tenant['number'])
    ]
    print(' ; '.join(tenant_data))
    #wr.writerow(tenant_data)
    #file.close()


def _get_tenants_with_cabinet(house, client):
    tenants_with_cabinet = Tenant.objects(
        area__house__id=house['_id'],
        has_access=True,
        activation_code=None,
        activation_step=None
    ).as_pymongo()
    if tenants_with_cabinet:
        for tenant in tenants_with_cabinet:
            if 'email' in tenant and tenant['email']:
                _put_data_to_has_lk_table(tenant, client, house)


def _put_data_to_has_lk_table(tenant, client, house):
    filename = 'has_lk.csv'
    _put_data_to_table(tenant, client, house)


def _get_owners_info(client, house):
    tenants = Tenant.objects(
        area__house__id=house['_id'],
        statuses__ownership__is_owner=True
    ).as_pymongo()
    if tenants:
        for tenant in tenants:
            if 'email' in tenant and tenant['email']:
                _put_data_to_table(tenant, client, house)
