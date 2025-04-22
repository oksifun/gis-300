from datetime import datetime

from processing.accounting.accounting_utils import get_dict_value_by_query
from processing.models.billing.account import Account
from processing.models.billing.payment import PaymentDoc, Payment
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES
from processing.models.logging.accounting_log import AccountingLog
from processing.models.tasks.accounting_sync import AccountingSyncTask


def get_payments_delta(provider_id):
    """
    Получение списка платежей в количестве не превышающем 100,
    из коллекции синхронизации
    :param provider_id: id организации
    :return: список словарей документов в которых произошли изменения
    """
    # Поиск записей измененных и ожидающих выдачи данных по жителям
    delta_documents = AccountingSyncTask.objects(provider=provider_id,
                                                 object_collection="Payment"
                                                 )[:100]
    if not delta_documents:
        return
    # Получение всех измененных платежей
    payments_ids = [x.object_id for x in delta_documents]
    changed_payments = Payment.objects(id__in=payments_ids).as_pymongo()

    # Поиск недостающих полей
    # Данные из коллекции жителя
    accounts = _get_account_fields(changed_payments)
    # Данные из коллекции жителя
    payment_docs = _get_payment_doc_fields(changed_payments)
    # Все названия направлений начислений
    sector_names = _get_sector_names(changed_payments)

    # Приклеиваем все найденные поля к каждой оплате
    for payment in changed_payments:
        # Из Account
        a_id = get_dict_value_by_query(payment, "account._id")
        if a_id:
            payment["area_number"] = accounts[a_id]["area_number"]
            payment["address"] = accounts[a_id]["address"]
            payment["number"] = accounts[a_id]["number"]
        # Название направления начисления
        payment["sector"] = sector_names[payment["sector_code"]]
        # Из PaymentDoc
        p_id = get_dict_value_by_query(payment, "doc._id")
        payment["doc_description"] = payment_docs[p_id]["description"]
        payment["doc_status"] = payment_docs[p_id]["doc_status"]
        payment["doc_bank_account"] = payment_docs[p_id]["bank_account"]
        payment["doc_type"] = payment_docs[p_id]["doc_type"]
        payment["doc_number"] = payment_docs[p_id]["doc_number"]
        payment["bank_fee"] = payment_docs[p_id]["bank_fee"]

        # Преобразование копеек в рубли
        field_list = (
            "bank_fee",
            "value",
            "penalties",
        )
        for field in field_list:
            target = payment.get(field)
            # Пропускаем поле bank_fee, если это не процент
            if field == 'bank_fee' and isinstance(target, float):
                continue
            if target:
                payment[field] = round(target / 100., 2)


    # Таблица соответсвия
    fields_relations = (
        # поля из модели Payment - поля для выдачи
        ("_id", "_id"),
        ("area_number", "account.area"),
        ("address", "account.house"),
        ("number", "account.number"),
        ("account.agreement_number", "account.agreement_number"),  # нет в базе
        ("account.agreement_date", "account.agreement_date"),  # нет в базе

        ("doc._id", "doc._id"),
        ("doc.date", "doc.date"),
        ("doc_description", "doc.description"),
        ("doc_status", "doc.status"),
        ("doc_bank_account", "doc.bank_account"),
        ("doc_type", "doc.type"),  # отсеить то что doc.type из PD _type (PesDoc) выше
        ("doc_number", "doc.number"),
        ("bank_fee", "doc.bank_fee"),

        ("month", "period"),
        ("sector", "sector"),
        ("date", "date"),
        ("value", "value"),
        ("penalties", "penalties"),  # нет в базе
    )
    # Приведение полей выдачи к соответсвию
    result = []
    for payment in changed_payments:
        # Пересобираем поля
        delta_payment= {"type": "payment", "account": {}, "doc": {}}
        # Пересборка полей
        for field in fields_relations:
            # Для вложенных полей account
            if "." in field[1] and field[1].split(".")[0] == "account":
                delta_payment["account"].update(
                    {field[1].split(".")[-1]: get_dict_value_by_query(payment, field[0])}
                )
            # Для вложенных полей doc
            elif "." in field[1] and field[1].split(".")[0] == "doc":
                delta_payment["doc"].update(
                    {field[1].split(".")[-1]: get_dict_value_by_query(payment, field[0])}
                )
            else:
                delta_payment.update({field[1]: get_dict_value_by_query(payment, field[0])})
        result.append(delta_payment)

    # Запись в лог факта запроса данных
    AccountingLog(provider=provider_id,
                  date=datetime.utcnow(),
                  query_collection="Payment").save()

    # Удаление из задач синхронизации отданные записи
    delta_documents.delete()
    return result


def _get_account_fields(changed_payments):
    """
    Все документы из Account, совпавшие по account.id
    :param changed_payments: QuerySet или list - документы из коллекции Payment
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    account_id_list = list(set([x["account"]["_id"] for x in changed_payments if x.get("account")]))
    accounts = Account.objects(id__in=account_id_list).as_pymongo()
    accounts = {x["_id"]: {"area_number": get_dict_value_by_query(x, "area.str_number"),
                           "address": get_dict_value_by_query(x, "area.house.address"),
                           "number": x["number"]
                           }
                for x in accounts}
    return accounts


def _get_payment_doc_fields(changed_payments):
    """
    Все документы из PaymentDoc, совпавшие по doc.id
    :param changed_payments: QuerySet или list - документы из коллекции Payment
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    payment_doc_id_list = list(set([x["doc"]["_id"] for x in changed_payments]))
    payment_docs = PaymentDoc.objects(id__in=payment_doc_id_list).as_pymongo()
    states = ["RegistryDoc", "ManualDoc", "CashReceiptDoc"]
    payment_docs = {x["_id"]: {"description": x.get("description"),
                               "bank_account": x.get("bank_number"),
                               "doc_type": [t for t in x.get("_type") if t in states][0],
                               "bank_fee": x.get("bank_fee"),
                               "doc_number": x.get("registry_number"),
                               "doc_status": "deleted" if x.get("status") else ("verified"
                                                                                if x.get("bank_statement")
                                                                                else "in_progress")
                               }
                    for x in payment_docs}
    return payment_docs


def _get_sector_names(changed_payments):
    """
    Все названия направлений начислений
    :param changed_payments: QuerySet - документы из коллекции Accruals
    :return: dict - в котором необходимое значение будет получено по
    соответсвующему полю документа, которые будет использовано как ключ
    """
    sector_code_list = list(set([x["sector_code"] for x in changed_payments]))
    sector_names = {x[0]: x[1] for x in ACCRUAL_SECTOR_TYPE_CHOICES if x[0] in sector_code_list}
    return sector_names
