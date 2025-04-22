from processing.data_producers.balance.services.base import \
    _VendorsServicesHousesBalance


class VendorsServicesBalance(_VendorsServicesHousesBalance):
    """Методы рассчета Сальдо и оборотов по услугам по домам"""

    def __init__(self,
                 binds,
                 houses_ids: list,
                 account_types=None,
                 area_types=None,
                 is_developer=False,
                 sectors=None,
                 by_bank=True):
        """
        :param houses_ids: список домов
        :param account_types: необязательно, типы собственников
        :param area_types: необязательно, типы помещений
        :param is_developer: необязательно, признак застройщика
        """
        super().__init__(
            binds=binds,
            sectors=sectors,
            by_bank=by_bank,
        )
        self.houses = houses_ids
        self.account_types = account_types
        self.area_types = area_types
        self.is_developer = is_developer
        self.old_method = False

    def _get_custom_accruals_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Accrual по домам
        """
        match = {'account.area.house._id': {'$in': self.houses}}
        if self.area_types:
            match.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'account.is_developer': True})
        elif self.is_developer is False:
            match.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'account._type': self.account_types})
        return match

    def _get_custom_offsets_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Offsets по домам
        """
        match = {'refer.account.area.house._id': {'$in': self.houses}}
        if self.area_types:
            match.update({'refer.account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'refer.account.is_developer': True})
        elif self.is_developer is False:
            match.update({'refer.account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'refer.account._type': self.account_types})
        return match

    def _get_custom_payments_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Payment по домам
        """
        match = {'account.area.house._id': {'$in': self.houses}}
        if self.area_types:
            match.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'account.is_developer': True})
        elif self.is_developer is False:
            match.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'account._type': self.account_types})
        return match
