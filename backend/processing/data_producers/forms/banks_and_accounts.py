from processing.models.billing.provider.main import Provider, BankProvider


def get_banks_and_accounts(provider_id):
    """
    Отдаст список расчётных счетов и банков,
    присутствующих во всех документах оплат организации.
    """
    fields = 'banks_contracts', 'bank_accounts'
    provider = Provider.objects(id=provider_id).only(*fields).as_pymongo().get()
    bics = _get_bics(provider)
    bank_numbers = [
        dict(
            number=x['number'],
            active_till=x.get('active_till'),
            service_codes=x.get('service_codes', []),
        )
        for x in provider['bank_accounts']
        if x.get('number')
    ]
    banks = [
        dict(name=x['name'], id=str(x['bank']), bics=bics[x['bank']])
        for x in provider.get('banks_contracts', [])
        if x.get('bank') and x.get('name')
    ]
    return dict(bank_numbers=bank_numbers, banks=banks)


def _get_bics(provider):
    if not provider.get('banks_contracts'):
        return {}
    banks_ids = [
        x['bank']
        for x in provider['banks_contracts']
        if x.get('bank')
    ]
    fields = 'bic_body', 'id'
    banks = BankProvider.objects(id__in=banks_ids).only(*fields).as_pymongo()
    return {
        x['_id']: [y['BIC'] for y in x['bic_body']]
        for x in banks
    }
