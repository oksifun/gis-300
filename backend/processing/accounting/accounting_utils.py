from processing.models.tasks.accounting_sync import AccountingSyncTask


def add_object_to_sync(provider_id=None, object_id=None, collection=None):
    """
    Добавление или обновление объекта в коллекцию AccountingSyncTask
    для ожидания синхронизации
    """
    # Обновление имеющийся или создание новой задачи на синхронизацию
    AccountingSyncTask.objects(provider=provider_id,
                               object_id=object_id,
                               object_collection=collection
                               ).upsert_one(provider=provider_id,
                                            object_id=object_id,
                                            object_collection=collection
                                            )


def get_dict_value_by_query(dict_obj, query_key_text):
    """
    Преобразует путь к полю в БД к запросу в словарь
    :param dict_obj: cловарь для которого нужно получить значение
    :param query_key_text: поле из БД вида 'area.house.address'
    :return: значение словаря, например: dict_obj[area][house][address]
    """
    query_key_text = query_key_text.split('.')
    for key in query_key_text:
        try:
            dict_obj = dict_obj.get(key)
        except AttributeError:
            return
    return dict_obj


def get_bank_account_from_sector_field(sector, sector_code, area_type):
    """
    Определяет банковский счет
    :param area_type: list - типа [LivingArea, BaseArea]
    :param sector: list -  переданного поля sector
    :param sector_code: str - по которому определяет рассчетное поле в sector
    :return: str - банковский счет
    """
    for s in sector:
        # Находим нужное вложение по sector_code
        if s["sector_code"] == sector_code:
            bank_account = s["bank_account"]
            # Ищем более приоритетные счета
            living_bank_account = None
            not_living_bank_account = None
            parking_bank_account = None
            for a in s["area_types"]:
                if a["type"] == "LivingArea" and a["type"] in area_type:
                    living_bank_account = a.get("bank_account")
                elif a["type"] == "NotLivingArea" and a["type"] in area_type:
                    not_living_bank_account = a.get("bank_account")
                elif a["type"] == "ParkingArea" and a["type"] in area_type:
                    parking_bank_account = a.get("bank_account")

            if parking_bank_account:
                return parking_bank_account
            elif not_living_bank_account:
                return not_living_bank_account
            elif living_bank_account:
                return living_bank_account
            else:
                return bank_account
