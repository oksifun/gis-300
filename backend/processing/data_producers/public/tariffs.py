import datetime

from bson import ObjectId

from processing.models.billing.regional_settings import RegionalSettings


def update_value_for_urban_tariffs(tariff_pl_doc):
    """
    Изменение ставки тарифа
    """

    # Городские системные тарифы
    city_plans = RegionalSettings.objects(
        region_code=tariff_pl_doc['region_code']
    ).only('tariff_plans').as_pymongo()
    if city_plans:
        # Если запрос не пустой
        city_plans = city_plans.get()
        city_tariff_plans = {}
        if tariff_pl_doc['date_till']:
            sorted(city_plans['tariff_plans'],
                   key=lambda x: x['date_from'], reverse=True)
            for t_p in city_plans['tariff_plans']:
                if tariff_pl_doc['date_from'] >= t_p['date_from']:
                    for group_tariff in t_p['tariffs']:
                        city_tariff_plans.update(
                            {x['service_type']: x['value']
                             for x in group_tariff['tariffs']})
                    break
        else:
            for t_p in city_plans['tariff_plans']:
                # Берем первый, который удовлетворяет временному условию,
                # т.к. они в БД отсортированы по дате
                if t_p['date_from'] <= datetime.datetime.now():
                    # Проходим по группам и собираем все услуги
                    for group_tariff in t_p['tariffs']:
                        city_tariff_plans.update(
                            {x['service_type']: x['value']
                             for x in group_tariff['tariffs']})
                    break

        if city_tariff_plans:
            for tariff in tariff_pl_doc.tariffs:

                if tariff.type in ('urban', 'городской'):
                    # Находим соответствующий вид платежа и подменяем ставку.
                    # Если не найдены ближайший системный тарифный план,
                    # или в его тарифах не найден нужный
                    # признак платежа то значение не изменяем.
                    # Возможно умалчивание является ошибкой
                    if isinstance(tariff.service_type, ObjectId):
                        tariff.value = round(
                            city_tariff_plans.get(
                                tariff.service_type, tariff.value) / 100, 2
                        )
                    else:
                        # для старого api
                        tariff['value'] = round(
                            city_tariff_plans.get(
                                tariff.service_type._id, tariff.value) / 100, 2
                        )
