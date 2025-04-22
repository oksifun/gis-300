from lib.gridfs import get_file_from_gridfs
from processing.models.billing.account import Account
from app.registries.core.file_parser import format_bank_acc


def get_tgk1_sber_registry(source_file_id):
    # открываем файл
    file = get_file_from_gridfs(source_file_id, raw=True)
    file_bytes = file.read()
    lines = file_bytes.decode('cp1251').split('\r\n')
    # добавляем к номерам ЛС договоры с ТГК-1
    numbers = []
    reg_format_100500 = False
    for l in lines:
        if l.find('#') == 0:
            reg_format_100500 = True
            continue
        if not l:
            continue
        data = l.split(';')
        if reg_format_100500:
            numbers.append(format_bank_acc(data[2]))
        else:
            numbers.append(format_bank_acc(data[5]))
    tenants = Account.objects(number__in=numbers).as_pymongo().only(
        'id', 'number', 'statuses.ownership'
    )
    tenants = {t['number']: t for t in tenants}
    data_num = 2 if reg_format_100500 else 5
    for ix, l in enumerate(lines):
        if not l or l.find('#') == 0:
            continue
        data = l.split(';')
        tenant = tenants.get(data[data_num])
        if (
            tenant
            and tenant.get('statuses')
            and tenant['statuses'].get('ownership')
        ):
            contract = ''
            for c in tenant['statuses']['ownership']['contracts']:
                if c['type'] == 'heat_supply':
                    contract = c['number']
                    break
            contract = contract[-5:].zfill(5)
            data[data_num] = '{}{}'.format(contract, tenant['number'])
            lines[ix] = ';'.join(data)
    # кодируем обратно в файл и отдаём
    reg_str = '\r\n'.join(lines)
    return file.filename, reg_str.encode('cp1251')

