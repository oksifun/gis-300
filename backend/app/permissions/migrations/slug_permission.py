import argparse

from app.auth.models.actors import RoboActor, Actor
from app.permissions.core.tools import (
    migration_convert_permission_from_dict_to_int,
)
from processing.models.billing.business_type import BusinessType
from processing.models.permissions import Permissions, ClientTab
from mongoengine_connections import register_mongoengine_connections


def tab_mapper() -> dict:
    """Возвращает словарь tab.id: tab.slug"""
    tabs = ClientTab.objects.only('slug').all()
    return {str(tab.id): tab.slug for tab in tabs}


def transform_permissions(permissions: Permissions, tabs: dict) -> dict:
    """Преобразовывает права из старого формата в новый."""
    if not permissions:
        return {}
    permissions = permissions.granular.get('Tab', dict())
    perms = (
        {slug_id: perms[0]['permissions']
         for slug_id, perms in permissions.items()
         if perms}
    )
    return (
        {tabs[slug_id]: migration_convert_permission_from_dict_to_int(value)
         for slug_id, value in perms.items()
         if slug_id in tabs}
    )


def migrate_business_types(tabs: dict) -> None:
    bts = BusinessType.objects(permissions=None)
    for bt in bts:
        permissions = Permissions.objects(actor_id=bt.id).first()
        perms = transform_permissions(permissions, tabs)
        bt.update(permissions=perms)


def migrate_provider_permissions_to_roboactor(provider_id) -> None:
    """Миграция прав организации в права RoboActor."""
    tabs = tab_mapper()
    permissions = Permissions.objects(actor_id=provider_id).first()
    if not permissions:
        return
    perms = transform_permissions(permissions, tabs)
    roboactor = RoboActor.get_default_robot(provider_id)
    roboactor.update(permissions=perms)


def migrate_roboactors(tabs: dict) -> None:
    actors = (
        RoboActor
        .objects(permissions__in=[None, {}], _type='RoboActor')
        .timeout(False)
    )
    for actor in actors:
        permissions = Permissions.objects(actor_id=actor.provider.id).first()
        perms = transform_permissions(permissions, tabs)
        actor.update(permissions=perms)


def migrate_actors(tabs: dict) -> None:
    actors = (
        Actor
        .objects(permissions__in=[None, {}], _type='Actor')
        .timeout(False)
    )
    for actor in actors:
        permissions = Permissions.objects(actor_id=actor.owner.id).first()
        perms = transform_permissions(permissions, tabs)
        actor.update(permissions=perms)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Миграция прав')
    parser.add_argument(
        '--business_types',
        type=bool,
        default=False,
        help='Мигрировать виды деятельности (default: False)'
    )
    parser.add_argument(
        '--actors',
        type=bool,
        default=False,
        help='Мигрировать сотрудников и жителей (default: False)'
    )
    parser.add_argument(
        '--providers',
        type=bool,
        default=False,
        help='Мигрировать провайдеров (default: False)'
    )
    my_namespace = parser.parse_args()
    if not any((
        my_namespace.actors,
        my_namespace.business_types,
        my_namespace.providers,
    )):
        my_namespace.actors = True
        my_namespace.business_types = True
        my_namespace.providers = True
    register_mongoengine_connections()
    tabs = tab_mapper()
    if my_namespace.business_types:
        migrate_business_types(tabs)
    if my_namespace.providers:
        migrate_roboactors(tabs)
    if my_namespace.actors:
        migrate_actors(tabs)

