from enum import IntFlag
from processing.models.permissions import Permissions, ClientTab


def provider_has_permission(provider_id, slug_name):
    tab = ClientTab.objects(
        slug=slug_name,
    ).only(
        'id',
        'slug',
    ).as_pymongo().first()
    if not tab:
        return False
    tab = str(tab['_id'])
    permission = Permissions.objects(
        actor_id=provider_id,
    ).only(
        'granular.Tab',
    ).as_pymongo().first()
    if not permission:
        return False
    tab_permission = permission['granular']['Tab'].get(tab)
    if not tab_permission:
        return False
    if tab_permission[0]['permissions'].get('r'):
        return True
    return False


class PermissionEnum(IntFlag):
    create = 1
    read = create * 2
    update = read * 2
    delete = update * 2

    @classmethod
    def all(cls):
        return [perm.name for perm in cls]

    @classmethod
    def max(cls):
        return sum((perm.value for perm in cls))


def convert_permission_from_int_to_dict(number: int) -> dict:
    """Преобразовывает права из числа в словарь."""
    return {perm.name: bool(number & perm.value) for perm in PermissionEnum}


def convert_permission_from_dict_to_int(perms: dict) -> int:
    """Преобразовывает права из словаря в число."""
    return sum(
        getattr(PermissionEnum, perm_type)
        for perm_type, value in perms.items()
        if bool(value)
    )


def union_permissions(parent: dict, current: dict) -> dict:
    """Объединяет родительские права и текущие.

    Правила объединения:
    1. если значение в родительских False, то в результате None
    2. в других случаях в результат передаётся значение текущих прав.
    """
    parent_perms = perms_strong_dict(parent)
    current_perms = perms_strong_dict(current)
    for slug, perms in parent_perms.items():
        for perm_type, value in perms.items():
            if value is False:
                parent_perms[slug][perm_type] = None
            else:
                current_value = (
                    current_perms.get(slug, {}).get(perm_type, False)
                )
                parent_perms[slug][perm_type] = current_value
    return parent_perms


def filter_permissions(
    own_permissions: dict, permissions: dict, is_super: bool,
):
    """Фильтрация прав по собственным правам.

    Во время этой операции теряются None значения.

    Результат: словарь прав с числовыми значениями.
    """
    own_permissions = perms_strong_int(own_permissions)
    permissions = perms_strong_int(permissions)
    if is_super:
        return permissions
    return {
        slug: perm & permissions.get(slug, 0)
        for slug, perm in own_permissions.items()
    }


def perms_strong_int(perms: dict) -> dict:
    """Возвращает словарь прав строго с числовым значением."""
    if type(next(iter(perms.values()), None)) is int:
        return perms
    return {
        slug: convert_permission_from_dict_to_int(perm)
        for slug, perm in perms.items()
    }


def perms_strong_dict(perms: dict) -> dict:
    """Возвращает словарь прав строго со значением состоящим из словаря."""
    if type(next(iter(perms.values()), None)) is dict:
        return perms
    return {
        slug: convert_permission_from_int_to_dict(perm)
        for slug, perm in perms.items()
    }


def migration_convert_permission_from_dict_to_int(perms: dict) -> int:
    """Преобразовывает права из словаря в число."""
    action_map = {action[0]: action for action in PermissionEnum.all()}
    return sum(
        getattr(PermissionEnum, action_map[perm_type])
        for perm_type, value in perms.items()
        if bool(value)
    )
