from bson import ObjectId

import settings

from processing.models.billing.provider.main import Provider


def generate_public_url_for_pay(number,
                                accrual_id=None,
                                provider_id=None,
                                provider_url=None,
                                value=None,
                                sector=None,
                                source=None):
    """
    Генерирует ссылку на оплату, используя редирект с ЛКЖ на страницу эквайера.
    Обязательно принимает либо сумму с направлением, либо _id начисления.
    начисления.


    :param number: Номер ЛС
    :type number: str
    :param accrual_id: _id начисления.
    :type accrual_id: ObjectId
    :param provider_id: _id организации (нужен для генерации урлы организации,
    если такая имеется)
    :type provider_id: ObjectId
    :param provider_url: урла организации (если не хочется передавать _id
    организации для генерации урлы)
    :type provider_url: str
    :param value: Сумма для оплаты (если не формируется для начисления)
    :type value: str or float
    :param sector: Направление
    :type sector: str
    :param source: откуда произведена оплата
    :type source: str

    :return: Ссылка на оплату в ЛКЖ, которая редиректит на страницу эквайера
    :rtype: str
    """
    cabinet_url = settings.DEFAULT_CABINET_URL

    if provider_url:
        cabinet_url = provider_url
    elif provider_id:
        url = Provider.objects.only('url').get(id=provider_id).url
        if url:
            cabinet_url = url

    if value is not None and sector:
        params = f'value={value}&sector={sector}'
    else:
        params = f'accrual={accrual_id}'

    if source:
        source = f'&source={source}'
    else:
        source = ''

    api_url = '/api/v4/public/pay_by_qr/'
    base_url = f"{settings.DEFAULT_PROTOCOL}://{cabinet_url}{api_url}"
    return f"{base_url}?number={number}&{params}{source}"
