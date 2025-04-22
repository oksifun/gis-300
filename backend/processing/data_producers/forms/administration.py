from mongoengine import Document

from mongoengine_connections import register_mongoengine_connections
from processing.models.billing.provider.main import ProviderPublicCode, Provider


def get_providers_and_sites():
    """
    Получение id с ссылками на сайты в ProviderPublicCode, поиск соотвествующих названий
    в Provide и добавление их имен к выдачи вместе с ProviderPublicCode
    :return: list - Список организаций с их названиями и сайтами
    """

    # получаем весь список из коллекции ProviderPublicCode
    providers_list = list(ProviderPublicCode.objects.as_pymongo().all())
    # список id клиентов
    providers = [prov['provider'] for prov in providers_list]
    # находим документы в колекции Provide соответсвующие списку клиентов
    relevant_docs = list(Provider.objects.filter(id__in=providers).as_pymongo())

    # формируем список документов на выдачу
    for prov in providers_list:
        for rel in relevant_docs:
            if prov['provider'] == rel['_id']:
                prov.update(dict(str_name=rel['str_name']))

    return providers_list
