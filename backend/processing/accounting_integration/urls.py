"""Ссылки для запросов к 1C"""
import settings
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID, EIS24_PROVIDER_OBJECT_ID, \
    KOTOLUP_PROVIDER_OBJECT_ID, SEMENCOVA_PROVIDER_OBJECT_ID


# Сигнатуры методов
SIGNATURES = dict(
    # Сопоставление номенклатуры
    sendProducts='sendProducts',

    # Формирование счета и акта выполненных работ
    createInvoice='createInvoice',

    # Формирование счета (отдельно от верхнего запроса)
    createDocumentInvoice='createDocumentInvoice',

    # Запрос баланса клиента по договору
    getContractBalance='getContractBalance',

    # Запрос акта сверки
    getReconciliationReport='getReconciliationReport',

    # Запрос архивного счета и акта выполненных работ.
    # ВАЖНО!!!: связанные запросы.
    getClientDocumentsList='getClientDocumentsList',
    getPaymentDocuments='getPaymentDocuments',
)

PREFIX = 'http://'

# Таблица соответсвия поставщика услуг и адреса сервера 1С
OWNERS = {
    ZAO_OTDEL_PROVIDER_OBJECT_ID: settings.SWAMP_THING['OTDEL'],
    EIS24_PROVIDER_OBJECT_ID: settings.SWAMP_THING['EIS'],
    KOTOLUP_PROVIDER_OBJECT_ID: settings.SWAMP_THING['KOTOLUP'],
    SEMENCOVA_PROVIDER_OBJECT_ID: settings.SWAMP_THING['SEMENCOVA'],

}


def send_products(owner):
    """ Сопоставление номенклатуры """

    return (
        PREFIX + '/'.join([OWNERS[owner], SIGNATURES['sendProducts']])
    )


def create_invoice(owner):
    """
    Формирование счета и акта выполненных работ
    (выставление комплекта документов)
    """

    return (
        PREFIX + '/'.join([OWNERS[owner], SIGNATURES['createInvoice']])
    )


def create_document_invoice(owner):
    """
    Формирование документа счет на оплату покупателю (отдельно)
    (выставление комплекта документов)
    """

    return (
        PREFIX + '/'.join([OWNERS[owner], SIGNATURES['createDocumentInvoice']])
    )


def contract_balance(owner):
    """
    Ежедневное получение сальдо из 1С по договорам организаций
    """

    return (
        PREFIX + '/'.join([OWNERS[owner], SIGNATURES['getContractBalance']])
    )


def reconciliation_report(owner):
    """ Запрос акта сверки """

    return (
        PREFIX
        + '/'.join([OWNERS[owner], SIGNATURES['getReconciliationReport']])
    )


def client_document_list(owner):
    """ Запрос архивного счета и акта выполненных работ. Часть 1 """

    return (
        PREFIX
        + '/'.join([OWNERS[owner], SIGNATURES['getClientDocumentsList']])
    )


def payment_document_list(owner):
    """ Запрос архивного счета и акта выполненных работ. Часть 2 """

    return (
        PREFIX
        + '/'.join([OWNERS[owner], SIGNATURES['getPaymentDocuments']])
    )
