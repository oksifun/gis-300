# -*- coding: utf-8 -*-


class TenantWithoutInnError(Exception):
    """Исключение вызывается если не у всех жителей юр. лиц указан ИНН."""
    pass
