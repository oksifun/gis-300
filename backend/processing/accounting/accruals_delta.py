from datetime import datetime

from lib.helpfull_tools import by_mongo_path
from processing.accounting.accounting_utils import get_dict_value_by_query, \
    get_bank_account_from_sector_field
from processing.models.billing.account import Account
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.tariff_plan import TariffPlan
from app.offsets.models.offset import Offset
from processing.models.billing.settings import Settings
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES
from processing.models.logging.accounting_log import AccountingLog
from processing.models.tasks.accounting_sync import AccountingSyncTask


def get_accruals_delta(provider_id):
    """
    Получение списка начислений в количестве не превышающем 100,
    из коллекции синхронизации
    :param provider_id: id организации
    :return: список словарей документов в которых произошли изменения
    """
    # Поиск записей измененных и ожидающих выдачи данных по жителям
    delta_documents = AccountingSyncTask.objects(provider=provider_id,
                                                 object_collection="Accrual"
                                                 )[:100]
    if not delta_documents:
        return
    # Получение всех измененных аккруалов
    accruals_ids = [x.object_id for x in delta_documents]
    changed_accruals = Accrual.objects(id__in=accruals_ids).as_pymongo()

    # Поиск необходимых полей:
    # Все документы из AccrualDoc, совпавшие по id
    accrual_docs = _get_accrual_doc_fields(changed_accruals)
    # Все лицевые счета
    account_numbers = _get_account_numbers(changed_accruals)
    # Все названия направлений начислений
    sector_names = _get_sector_names(changed_accruals)
    # Названия всех услуг в соответсвии с тарифными планами
    service_names = _get_service_names(changed_accruals)
    # Документы из Settings с содержанием счетов,
    # на которые выставленны квитанции
    all_banks_by_house = _get_settings(changed_accruals, provider_id)
    # Оффсеты для каждого документа начисления
    all_offsets = Offset.objects(refer__id__in=accruals_ids).as_pymongo()

    # Приклеиваем все найденные поля к каждому документу
    for accrual in changed_accruals:
        # Адрес дома
        accrual["address"] = accrual_docs[accrual["doc"]["_id"]]["address"]
        # Описание платежа
        accrual["description"] = accrual_docs[accrual["doc"]["_id"]]["description"]
        # Номер лицевого счета
        accrual["number"] = account_numbers[accrual["account"]["_id"]]
        # Название направления начисления
        accrual["sector"] = sector_names[accrual["sector_code"]]
        # Название для каждой услуги
        for service in accrual["services"]:
            service["name"] = service_names[service["service_type"]]
            # Преобразование копеек в рубли
            field_list = (
                "tariff",
                "value",
                "totals.privileges",
                "totals.recalculations",
                "totals.shortfalls",
            )
            _make_ruble(field_list, service)

        # Банковский счет
        accrual["bank_account"] = get_bank_account_from_sector_field(
            all_banks_by_house[accrual["account"]["area"]["house"]["_id"]],
            accrual["sector_code"],
            accrual["account"]["area"]["_type"]
        )
        # Офсеты
        accrual["offsets"] = [{"month": offset["accrual"]["month"],
                               "services": offset["services"]}
                              for offset in all_offsets if accrual["_id"] == offset["refer"]["_id"]]

    # Таблица соответсвия
    fields_relations = (
        # поля из базы - поля для выдачи
        ("account.area.str_number", "account.area"),
        ("address", "account.house"),
        ("number", "account.number"),
        ("account.agreement_number", "account.agreement_number"),
        ("account.agreement_date", "account.agreement_date"),

        ("doc._id", "doc._id"),
        ("doc.date", "doc.date"),
        ("description", "doc.description"),
        ("doc.status", "doc.status"),

        ("offsets", "offsets"),
        ("bank_account", "bank_account"),
        ("month", "period"),
        ("sector", "sector"),
    )
    # Приведение полей выдачи к соответсвию
    result = []
    for accrual in changed_accruals:
        # Пересобираем поля
        delta_accrual = {"type": "accrual", "account": {}, "doc": {}, "services": []}
        # Пересборка полей
        for field in fields_relations:
            # Для вложенных полей account
            if "." in field[1] and field[1].split(".")[0] == "account":
                delta_accrual["account"].update(
                    {field[1].split(".")[-1]: get_dict_value_by_query(accrual, field[0])}
                )
            # Для вложенных полей doc
            elif "." in field[1] and field[1].split(".")[0] == "doc":
                delta_accrual["doc"].update(
                    {field[1].split(".")[-1]: get_dict_value_by_query(accrual, field[0])}
                )
            else:
                delta_accrual.update({field[1]: get_dict_value_by_query(accrual, field[0])})
        # Для вложенных полей services
        for s in accrual["services"]:
            service = {}
            service.update({"name": s["name"]})
            service.update({"value": s["value"]})
            service.update({"price": s["tariff"]})
            service.update({"consumption": round(s["consumption"], 6)})
            service.update({"recalculations": s["totals"]["recalculations"]})
            service.update({"shortfalls": s["totals"]["shortfalls"]})
            service.update({"privileges": s["totals"]["privileges"]})
            delta_accrual["services"].append(service)
        result.append(delta_accrual)

    # Запись в лог факта запроса данных
    AccountingLog(provider=provider_id,
                  date=datetime.utcnow(),
                  query_collection="Accrual").save()

    # Удаление из задач синхронизации отданные записи
    delta_documents.delete()
    return result


def get_accruals_ids_from_doc(accrual_doc_id):
    """
    Для старой модели AccrualDoc, метода update_offsets.
    :param accrual_doc_id
    :return: result: list - [ (id документа, id провайдера), ... ]
    :return: providers_ids: list - id всех организаций которым начислили
    """
    accrual_doc = AccrualDoc.objects(id=accrual_doc_id).as_pymongo().get()
    providers_ids = [x["provider"] for x in accrual_doc["sector_binds"]]
    accruals = Accrual.objects(doc__id=accrual_doc_id,
                               doc__provider__in=providers_ids
                               ).as_pymongo()
    result = [(x["_id"], x["doc"]["provider"]) for x in accruals]
    return result, providers_ids


def _get_accrual_doc_fields(changed_accruals):
    """
    Все документы из AccrualDoc, совпавшие по id
    :param changed_accruals: QuerySet - документы из коллекции Accruals
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    accrual_doc_id_list = list(set([x["doc"]["_id"] for x in changed_accruals]))
    accrual_docs = AccrualDoc.objects(id__in=accrual_doc_id_list).as_pymongo()
    accrual_docs = {x["_id"]: {"address": x["house"]["address"],
                               "description": x["description"],
                               }
                    for x in accrual_docs}
    return accrual_docs


def _get_account_numbers(changed_accruals):
    """
    Все лицевые счета
    :param changed_accruals: QuerySet - документы из коллекции Accruals
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    accrual_account_id_list = list(set([x["account"]["_id"] for x in changed_accruals]))
    account_numbers = Account.objects(id__in=accrual_account_id_list).as_pymongo()
    account_numbers = {x["_id"]: x["number"] for x in account_numbers}
    return account_numbers


def _get_sector_names(changed_accruals):
    """
    Все названия направлений начислений
    :param changed_accruals: QuerySet - документы из коллекции Accruals
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    sector_code_list = list(set([x["sector_code"] for x in changed_accruals]))
    sector_names = {x[0]: x[1] for x in ACCRUAL_SECTOR_TYPE_CHOICES if x[0] in sector_code_list}
    return sector_names


def _get_service_names(changed_accruals):
    """
    Названия всех услуг в соответсвии с тарифными планами
    :param changed_accruals: QuerySet - документы из коллекции Accruals
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    all_tariff_list = list(set([x["tariff_plan"] for x in changed_accruals]))
    all_tariffs_and_services = TariffPlan.objects(id__in=all_tariff_list).as_pymongo()
    tariff_summary_list = []
    for t in all_tariffs_and_services:
        tariff_summary_list.extend((t["tariffs"]))
    service_names = {x["service_type"]: x["title"] for x in tariff_summary_list}
    return service_names


def _get_settings(changed_accruals, provider_id):
    """
    Документы из Settings с содержанием счетов,
    на которые выставленны квитанции
    :param changed_accruals: QuerySet - документы из коллекции Accruals
    :param provider_id: тут понятно
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    # Все id домов
    house_id_list = list(set([get_dict_value_by_query(x, "account.area.house._id")
                              for x in changed_accruals]))
    all_settings = Settings.objects(house__in=house_id_list,
                                    provider=provider_id
                                    ).as_pymongo()
    all_banks_by_house = {x["house"]: x["sectors"] for x in all_settings}
    return all_banks_by_house


def _make_ruble(field_list, service):
    """
    Преобразует копейки в рубли в схеме переданных полей
    :param field_list: list - путь в словаре в стиле Mongo
    :param service: dict: словарь услуги из БД
    """
    for field in field_list:
        target = by_mongo_path(service, field)
        if target:
            if '.' in field:
                field1, field2 = field.split('.')
                service[field1][field2] = round(target / 100., 2)
            else:
                service[field] = round(target / 100., 2)
