"""Переименование всех slug содержащих точку.

На текущий момент это:
['Tariffs.service_types', 'accruals.offsets', 'automation.sims',
'house_info.epd', 'providers.area_rating', 'providers_list.sims',
'testPage.bootstrap', 'testPage.directives']
"""

from mongoengine_connections import register_mongoengine_connections
from processing.models.permissions import ClientTab


if __name__ == '__main__':
    register_mongoengine_connections()
    for tab in ClientTab.objects(slug__contains='.'):
        tab.update(slug=tab.slug.replace('.', '_'))

