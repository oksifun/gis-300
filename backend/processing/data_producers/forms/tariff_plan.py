from mongoengine import DoesNotExist

from processing.models.billing.tariff_plan import TariffsTree
from app.caching.models.current_tariffs_tree import CurrentTariffsTree, \
    TariffsFolder


def get_provider_tariffs_tree(provider_id):
    try:
        tree = CurrentTariffsTree.objects.as_pymongo().get(provider=provider_id)
    except DoesNotExist:
        tree = TariffsTree.objects.get(provider=provider_id)
        tree.update_cache(forced=True)
        tree = CurrentTariffsTree.objects.as_pymongo().get(provider=provider_id)
    return tree['tree']


def get_tariffs_folder(folder_id):
    folder = TariffsFolder.objects.as_pymongo().get(folder_id=folder_id)
    return folder
