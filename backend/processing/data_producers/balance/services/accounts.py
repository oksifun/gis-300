from processing.data_producers.balance.services.base import ServicesBalanceBase, \
    _AccountsServicesHouseBalance


class AccountServicesBalance(ServicesBalanceBase):
    """Методы рассчета Сальдо и оборотов по услугам по домам"""

    def __init__(self,
                 binds,
                 account_id,
                 sectors=None,
                 by_bank=True):
        """
        :param account_id: лицевой счёт
        """
        super().__init__(
            binds=binds,
            sectors=sectors,
            by_bank=by_bank,
        )
        self.account = account_id

    def _get_custom_accruals_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Accrual по одному
        собственнику
        """
        return {'account._id': self.account}

    def _get_custom_offsets_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Offsets по одному
        собственнику
        """
        return {'refer.account._id': self.account}

    def _get_custom_payments_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Payment по одному
        собственнику
        """
        return {'account._id': self.account}


class AccountsServicesHouseBalance(_AccountsServicesHouseBalance):
    """Методы рассчета Сальдо и оборотов по услугам по домам"""

    def __init__(self,
                 binds,
                 house_id,
                 accounts_ids=None,
                 account_types=None,
                 area_types=None,
                 is_developer=False,
                 sectors=None,
                 by_bank=True):
        """
        :param house_id: дом
        :param account_types: необязательно, типы собственников
        :param area_types: необязательно, типы помещений
        :param is_developer: необязательно, признак застройщика
        """
        super().__init__(
            binds=binds,
            sectors=sectors,
            by_bank=by_bank,
        )
        self.house = house_id
        self.accounts_ids = accounts_ids
        self.account_types = account_types
        self.area_types = area_types
        self.is_developer = is_developer

    MAX_ACCOUNTS_FOR_QUERY = 100

    def _get_custom_accruals_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Accrual по домам
        """
        if (
                self.accounts_ids is not None
                and len(self.accounts_ids) < self.MAX_ACCOUNTS_FOR_QUERY
        ):
            match = {'account._id': {'$in': self.accounts_ids}}
        else:
            match = {'account.area.house._id': self.house}
        if self.area_types:
            match.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'account.is_developer': True})
        elif self.is_developer is False:
            match.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'account._type': {"$in": self.account_types}})
        return match

    def _get_custom_offsets_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Offsets по домам
        """
        if (
                self.accounts_ids is not None
                and len(self.accounts_ids) < self.MAX_ACCOUNTS_FOR_QUERY
        ):
            match = {'refer.account._id': {'$in': self.accounts_ids}}
        else:
            match = {'refer.account.area.house._id': self.house}
        if self.area_types:
            match.update({'refer.account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'refer.account.is_developer': True})
        elif self.is_developer is False:
            match.update({'refer.account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'refer.account._type': {"$in": self.account_types}})
        return match

    def _get_custom_payments_filter(self):
        """
        Возвращает поисковый фильтр агрегации для коллекции Payment по домам
        """
        if (
                self.accounts_ids is not None
                and len(self.accounts_ids) < self.MAX_ACCOUNTS_FOR_QUERY
        ):
            match = {'account._id': {'$in': self.accounts_ids}}
        else:
            match = {'account.area.house._id': self.house}
        if self.area_types:
            match.update({'account.area._type': {"$in": self.area_types}})
        if self.is_developer:
            match.update({'account.is_developer': True})
        elif self.is_developer is False:
            match.update({'account.is_developer': {'$ne': True}})
        if self.account_types:
            match.update({'account._type': {"$in": self.account_types}})
        return match
