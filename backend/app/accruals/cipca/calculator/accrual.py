
def get_accrual_total_value(accrual, include_subsidy, auto_denormalize=True):
    """
    Принимает словарь начисления, считает общую сумму по нему. Если передать
    auto_denormalize=True, в переданном начислении будут рассчитаны
    автоматические поля, т.е. исходный словарь accrual будет изменён
    """
    if auto_denormalize:
        denormalize_totals(accrual)
    result = accrual['totals']['penalties']
    for service in accrual['services']:
        result += (
                service['value']
                + service['totals']['recalculations']
                + service['totals']['shortfalls']
                + service['totals']['privileges']
        )
    if include_subsidy and accrual.get('subsidy', None):
        result += accrual['subsidy']
    return result


def denormalize_totals(accrual):
    """
    Принимает словарь начисления и считает в нём автоматические поля:
    - debt
    - totals
    - services.totals
    """
    accrual['totals'] = {
        'penalties': sum(
            (p['value_include'] + p['value_return'])
            for p in accrual['penalties']
        ),
    }
    accrual['debt'] = max(accrual['totals']['penalties'], 0)
    for s in accrual['services']:
        s['totals'] = {
            'recalculations': sum(
                x['value'] for x in s['recalculations']
            ),
            'shortfalls': sum(
                x['value'] for x in s['shortfalls']
            ),
            'privileges': sum(
                x['value'] for x in s['privileges'] if not x['is_info']
            ),
            'privileges_info': sum(
                x['value'] for x in s['privileges'] if x['is_info']
            ),
        }
        v = s['value'] \
            + s['totals']['recalculations'] \
            + s['totals']['shortfalls'] \
            + s['totals']['privileges']
        if v > 0:
            accrual['debt'] += v
