from datetime import datetime

from processing.accounting.accounting_utils import get_dict_value_by_query
from processing.models.billing.account import Account
from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment
from processing.models.billing.tenant_data import TenantData
from processing.models.logging.accounting_log import AccountingLog
from processing.models.tasks.accounting_sync import AccountingSyncTask

# Поля, при изменении которых
# необходима синхронизация
REQUIRED_FIELDS = (
    "_id",  # id
    "number",  # Номер лицевого счета
    "area",  # Объект данных о помещении
    "str_name",  # ФИО
    "_type",  # Тип жителя
    "ogrn",
    "inn",
    "kpp",
    "statuses",  # Даты учета
    "entity_contract"
)


def get_accounts_delta(provider_id):
    """
    Получение списка жителей в количестве не превышающем 100,
    которые не отдавались организации после записи жителей в БД
    или были изменены
    :param provider_id: id организации
    :return: список словарей жителей в которых произошли изменения
    """
    # Поиск записей измененных и ожидающих выдачи данных по жителям
    delta_documents = AccountingSyncTask.objects(provider=provider_id,
                                                 object_collection="Account"
                                                 )[:100]
    if not delta_documents:
        return
    # Получение всех измененных жителей
    tenants_ids = [x.object_id for x in delta_documents]
    changed_tenants = Account.objects(id__in=tenants_ids).as_pymongo()
    # Получение паспортных данных жителей
    passport_data = TenantData.objects(
        tenant__in=tenants_ids
    ).only('tenant', 'passport.series', 'passport.number').as_pymongo()
    passport_data = {x['tenant']: x['passport'] for x in passport_data}
    for tenant in changed_tenants:
        tenant_passport = passport_data.get(tenant['_id'])
        # Проверка нужна, потому как в БД есть ошибки в TenantData
        if tenant_passport and tenant_passport.get('number') and tenant_passport.get('series'):
            tenant.update(dict(p_serias=tenant_passport['series'],
                               p_number=tenant_passport['number']))

    fields_relations = [
        # поля из базы - поля для выдачи
        ("entity", "entity"),  # Уникальный идентификатор контрагента
        ("_id", "_id"),  # id
        ("number", "number"),  # Номер лицевого счета
        ("area.house.address", "area.house"),  # Адрес
        ("area.str_number", "area.number"),  # Номер помещения в виде строки
        ("str_name", "full_name"),  # ФИО
        ("_type", "tenant_type"),  # Тип жителя
        ("agreements._id", "agreements._id"),
        ("agreements.type", "agreements.type"),
        ("agreements.number", "agreements.number"),
        ("agreements.description", "agreements.description"),
        ("agreements.date", "agreements.date"),
        ("ogrn", "ogrn"),
        ("inn", "inn"),
        ("kpp", "kpp"),
        ("statuses.accounting.date_from", "date_start"),  # Дата начала учета
        ("statuses.accounting.date_till", "date_finish"),  # Дата окончания учета
        ("p_serias", "id_doc.series"),  # Серия паспорта
        ("p_number", "id_doc.number")  # Номер паспорта
    ]
    # Приведение полей выдачи к соответсвию
    tenants = [x for x in changed_tenants]
    result = []
    for tenant in tenants:
        # Пересобираем поля
        delta_tenant = {"type": "account", "area": {}, "agreements": {}}
        for field in fields_relations:
            if "." in field[1] and field[1].split(".")[0] == "area":
                delta_tenant["area"].update(
                    {field[1].split(".")[-1]: get_dict_value_by_query(tenant, field[0])}
                )
            elif "." in field[1] and field[1].split(".")[0] == "agreements":
                delta_tenant["agreements"].update(
                    {field[1].split(".")[-1]: get_dict_value_by_query(tenant, field[0])}
                )
            else:
                delta_tenant.update({field[1]: get_dict_value_by_query(tenant, field[0])})
        result.append(delta_tenant)
    # Запись в лог факт запроса данных
    AccountingLog(provider=provider_id,
                  date=datetime.utcnow(),
                  query_collection="Account").save()

    # Удаление из задач синхронизации отданные записи
    delta_documents.delete()
    return result


def get_account_providers(account_id):
    """
    Получение для конкретного жителя список всех организаций
    с которыми он рассчитывается
    :param account_id: id жителя
    :return: list - id организаций
    """
    accrual_providers = list(Accrual.objects(owner=account_id).as_pymongo().distinct("doc.provider"))
    payments_providers = list(Payment.objects(account__id=account_id).as_pymongo().distinct("doc.provider"))
    provider_ids = accrual_providers + payments_providers
    return provider_ids
