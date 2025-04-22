"""Миксин для работы с разрешениями."""
from mongoengine import MapField, IntField

from app.permissions.core.tools import (
    PermissionEnum,
    convert_permission_from_dict_to_int,
    convert_permission_from_int_to_dict,
    union_permissions, filter_permissions,
)


CABINET_PERMISSIONS = (
    'news',
    'request_log',
    'apartment_meters_data',
    'all_apartments_accruals',
    'tickets_from_tenants',
    'catalogue_cabinet_positions',
    'insurance',
    'compendium'
)


class PermissionsMixin:
    permissions = MapField(
        IntField(min_value=0, max_value=PermissionEnum.max())
    )

    @property
    def cabinet_perms(self):
        """Возвращает права для кабинета в виде словаря."""
        return {
            slug: convert_permission_from_int_to_dict(
                self.permissions.get(slug, 0),
            )
            for slug in CABINET_PERMISSIONS
        }

    @property
    def cabinet_slugs(self):
        """Возвращает права для кабинета в виде словаря."""
        return {
            slug: convert_permission_from_int_to_dict(
                self.permissions.get(slug, 0),
            )
            for slug in CABINET_PERMISSIONS
        }

    @property
    def long_perms(self):
        """Возвращает права в виде словаря."""
        return {
            slug: convert_permission_from_int_to_dict(perm)
            for slug, perm in self.permissions.items()
        }

    def has_perm(self, slug: str, perm: str) -> bool:
        """Проверяет есть ли право perm на вкладку slug."""
        permission = self.permissions.get(slug, 0)
        return bool(permission & getattr(PermissionEnum, perm, 0))

    def update_permissions(
        self, updated_perms: dict, own_permissions: dict, is_super
    ):
        """Объединяет текущие права и updated_perms."""
        if not is_super:
            updated_perms = self.merge_updated(updated_perms)
            updated_perms = union_permissions(own_permissions, updated_perms)
        for slug, perms in updated_perms.items():
            self.permissions[slug] = (
                convert_permission_from_dict_to_int(perms)
            )

        self.save()

    def merge_updated(self, updated_perms):
        current_perms = {}
        for slug, perm in self.permissions.items():
            perm_dict = convert_permission_from_int_to_dict(perm)
            current_perms[slug] = updated_perms.get(slug, perm_dict)
        return current_perms

    @property
    def parent_permissions(self):
        """Возвращает родительские права.

        Родительские права для сотрудника это права организации,
        для организации — права вида деятельности,
        для вида деятельности — все возможные права.
        """
        raise NotImplementedError

    def union_permissions(self, own_permissions: dict, is_super: bool = False):
        """Возвращает объединение своих и родительских прав."""
        parent_permissions = filter_permissions(
            own_permissions, self.parent_permissions, is_super,
        )
        permissions = self.permissions or {}
        return union_permissions(parent_permissions, permissions)

    def permissions_tree(self, own_permissions: dict, is_super: bool = False):
        """Дерево прав."""
        from processing.models.permissions import ClientTab
        # исключим неиспользуемые поля
        tabs = ClientTab.objects().all().as_pymongo().exclude(
            'resource_binds',
            'help',
            'permissions_help',
        )
        permissions = self.union_permissions(own_permissions, is_super)
        return tree(tabs, permissions)
