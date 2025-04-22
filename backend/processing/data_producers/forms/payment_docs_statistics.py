from processing.models.billing.provider.main import Provider
from processing.models.billing.payment import PaymentDoc, Payment


def _get_payment_docs_dict(docs_ids_list):
    payments_docs = PaymentDoc.objects(
        id__in=docs_ids_list
    ).only('id', 'bank_fee', 'sum_bank_fee',
           'bank', 'date', 'description').as_pymongo()
    result = {}
    for elem in payments_docs:
        result.update({
            elem['_id']: dict(bank_fee=elem['bank_fee'],
                              sum_bank_fee=elem.get('sum_bank_fee'),
                              bank=elem.get('bank'),
                              description=elem.get('description'),
                              date=elem['date']
                              )
        })
    return result


def _get_banks_dict(banks_ids):
    banks_list = Provider.objects(
        __raw__={'_id': {'$in': banks_ids}}
    ).as_pymongo()
    result = {
        x['_id']: {
            'logo_image': x.get('logo_image'),
            'name': x['bic_body'][0].get('NameP') if x['bic_body'] else '',
            '_type': x['_type'],
        }
        for x in banks_list
    }
    return result


def _get_payment_dict(payments):
    """Делаем сгруппированный словарь в котором ключ группы платежей - doc.id"""
    grouped_payments = {}
    # Группировка платежей по докам
    for payment in payments:
        payment_group = grouped_payments.setdefault(payment['doc']['_id'], [])
        payment_group.append(payment)
    return grouped_payments


def _get_bank_fee(p_doc_data, doc_sum):
    """Расчет комиссии банка и суммы платежа с учетом комисии"""
    # Поле с суммой с учетом комиссии банка
    sum_with_fee = p_doc_data['sum_bank_fee']
    # Рассчет суммы комиссии и платежа суммы платежа после комиссии
    if not sum_with_fee:
        fee = p_doc_data.get('bank_fee', 0) * doc_sum / 100
        sum_with_fee = doc_sum - fee
    # Если сумма с учетом комиссии изестна, найдем только сумму самой комиссии
    else:
        fee = doc_sum - sum_with_fee
    return fee, sum_with_fee


def get_payments_doc_stats(docs_ids_list):
    """
    Статистика и картинки по платежным документам
    :param docs_ids_list: list: список id платежных документов
    Пример полей ответа:
    :return: dict: суммы, комиссии и т.д.
    """
    # Документы оплат
    p_docs_dict = _get_payment_docs_dict(docs_ids_list)

    # Все оплаты
    payments = Payment.objects(
        doc__id__in=docs_ids_list
    ).only('value', 'doc.bank', 'doc.id', 'has_receipt').as_pymongo()

    # Оплаты сгруппированные по документу
    payment_dict = _get_payment_dict(payments)

    # Банки
    banks_dict = _get_banks_dict([p_docs_dict[x]['bank'] for x in p_docs_dict])
    # Данные по банкам
    banks = {}
    for bank_id in banks_dict:
        bank = banks_dict[bank_id]
        logo = bank.get('logo_image')
        # Если поле логотипа не пустое:
        if logo:
            logo = {
                "file": str(logo["file"]),
                "name": logo["name"],
            }
        bank_data = {
            "NAMEN": bank["name"],
            # "_id": str(bank_id),
            "_type": bank["_type"][0] if bank["_type"] else '',
            "logo_image": logo
        }
        banks.update({bank_id: bank_data})

    # Общая сумма оплат
    total_sum = sum([x['value'] for x in payments])
    # Общее количество
    total_length = len(payments)

    # Статистика по документам
    doc_stat = []
    for p_doc_id in p_docs_dict:
        # Данные платежного документа
        p_doc_data = p_docs_dict[p_doc_id]
        # Платежи платежного документа
        doc_payments = payment_dict.get(p_doc_id)
        # Количество оплат с чеками внутри платежного документа
        receipts_count = len(
            [1 for x in doc_payments or () if x.get('has_receipt')]
        )
        if doc_payments:
            # Сумма платежей по документу
            doc_sum = sum([x['value'] for x in doc_payments])
            # Количество платежей документа
            doc_payments_count = len(doc_payments)
            # Комиссия банка
            fee, pure_doc_sum = _get_bank_fee(p_doc_data, doc_sum)

            doc_stat.append(
                dict(
                    doc_id=str(p_doc_id),
                    sum=doc_sum,
                    sum_after_fee=pure_doc_sum,
                    payments_count=doc_payments_count,
                    fee=fee,
                    description=p_doc_data['description'],
                    date=p_doc_data['date'],
                    bank=banks.get(p_doc_data['bank']),
                    receipts_count=receipts_count,
                    receipts_fullness=(
                        (
                            'full'
                            if doc_payments_count / receipts_count == 1
                            else 'partial'
                        )
                        if receipts_count
                        else None
                    )
                )
            )
    # Сортировка статистики по дате
    doc_stat.sort(key=lambda x: x['date'], reverse=True)

    doc_stat = dict(total_sum=total_sum,
                    total_length=total_length,
                    doc_statistics=doc_stat,
                    # banks=banks
                    )
    return doc_stat
