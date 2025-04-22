from mongoengine import Q

from processing.models.billing.payment import Payment


def get_summation(provider_id, date_from, date_till):
    """
    Получение общей суммы оплат для переданного диапазона дат
    :param provider_id: id организации
    :param date_from: datetime - начало диапазона
    :param date_till: datetime - конец диапазона
    :return: int - общая сумма оплат
    """
    date_query = Q(doc__date__gte=date_from) & Q(doc__date__lte=date_till)
    payments = Payment.objects(date_query,
                               doc__provider=provider_id,
                               ).as_pymongo()
    summation = sum([p["value"] for p in payments])
    return summation
