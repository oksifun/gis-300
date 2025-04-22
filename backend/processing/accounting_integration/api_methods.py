import urllib
from datetime import datetime
from io import BytesIO

import requests
from bson import ObjectId

from processing.accounting_integration import urls

TIMEOUT = 20.
HEADERS = {
    'Content-Type': 'application/json; charset=utf-8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
}


def __response_processing(response, params=None):
    """ Вспомогательная функция для разбора ответа """

    state = 'ready' if response.status_code == 200 else 'failed'
    content_type = response.headers.get('Content-Type', {})
    answer_body = None
    try:
        if 'application/x-zip-compressed' in content_type:
            answer_body = BytesIO(response.content)
        elif 'text/plain' in content_type:
            answer_body = response.text
        elif 'application/json' in content_type:
            answer_body = response.json()
    except Exception as error:
        answer_body = error
    # Пытаемся получить ответ
    return dict(
        status=response.status_code,
        state=state,
        answer=answer_body,
        params=params if params else {}
    )


def __encode_params(params: dict):
    """ Кодирование параметров без "плюсиков" """
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def __check_empty_params(*params):
    """ Исключаем булевы параметры, так как False искажает проверку """

    if not all([x for x in params if not isinstance(x, bool)]):
        raise AssertionError("Не допускается передача пустых значений")


def __make_abominable_boolean(boolean: bool):
    """Мерзкое преобразование логического типа в 'логическую строку' """
    return 'true' if boolean else 'false'


def __modify_date(date: datetime):
    """Преобразует дату в ISO без миллисекунд"""

    return date.replace(microsecond=0).isoformat()


def map_nomenclature(service_id: str, name: str, full_name: str,
                     owner: ObjectId):
    """
    Сопоставление номенклатуры
    Описание работы метода на стороне 1С:
        1) Поиск уже сопоставленной номенклатуры по id
        2) Если номенклатура не найдена в базе, производится поиск
            существующей в базе номенклатуры по переданному наименованию.
        3) Если номенклатура не найдена по наименованию, происходит создание
            номенклатуры со следующими реквизитами:
                - ВидНоменклатуры: «Услуги»
                - Наименование: «Переданное в запросе наименование»
                - ПолноеНаименование: «Переданное в запросе наименование»
                - СтавкаНДС: «БезНДС»
                - ЕдиницаИзмерения: «шт»
                - Услуга: «Истина».
        4) После того как номенклатура найдена или создана, производится ее
            сопоставление с указанным в запросе id.
        5) Если наименование найденной в базе номенклатуры отличается
            от переданного наименования, наименование номенклатуры
            в базе будет изменено на переданное.
        6) Если id номенклатуры отличается от переданного id, будет
            произведена замена текущего id на переданный.
    """
    __check_empty_params(service_id, name)

    params = dict(id=service_id, name=name)
    if full_name:
        params['NP300'] = full_name
    query = requests.post(
        url=urls.send_products(owner),
        json=params,
        headers=HEADERS,
        timeout=TIMEOUT
    )
    return __response_processing(query, params)


def create_invoice(
        inn: str,
        kpp: str,
        number: str,
        date_on: datetime,
        period: datetime,
        mark_to_sbis: bool,
        email_list: list,
        ids: list,
        counts: list,
        prices: list,
        bill: bool,
        owner: ObjectId,
        bill_only: bool,
        create_doc_invoice: bool = None,
        certificate: bool = None,
        send_to_email: bool = False
):
    """
     Формирование счета и акта выполненных работ.
     Параметры:
    :param inn – ИНН контрагента.
    :param kpp – КПП контрагента.
    :param number – номер договора с контрагентом.
    :param date_on – дата на которую должен быть сформирован документ
    :param mark_to_sbis – пометить для формирования в СБИС.
    :param email_list – отправить печатные формы акта и счета на
                           email клиента.
    :param ids – массив id номенклатуры.
    :param counts – массив, содержащий данные о количестве соответствующей
                   номенклатуры.
    :param prices – цены номенклатуры.
    :param period: - периоды оказания услуг
    :param bill: - выставить счет
    :param owner: ID поставщика услуг
    :param bill_only: выставить только счет
    :param create_doc_invoice:  необходимость создания документа
                                «Счет на оплату покупателю». Булево.
                                Должно содержать строковое значение «true»
                                или «false»
    :param certificate: - выставить акт выполненных работ
    :param send_to_email - отправлять комплект документов на email клиента

    Описание работы метода на стороне 1С:
        1) Производится создание документа реализации в соответствии
            с переданными параметрами. В случае, если найдена не сопоставленная
            номенклатура, будет выведено соответствующее сообщение и операция
            будет прервана.
        2) В случае если параметр mark_to_sbis установлен в значение true,
            в комментарии к документу будет указано:
            «НЕОБХОДИМО ОТПРАВИТЬ В СБИС! Документ создан автоматически
            через интеграцию с Системой С-300.»
        3) В случае если параметр send_to_email установлен в значение true,
            будет произведена отправка Акта выполненных работ и
            Счета на оплату на почту, указанную в email_list.
    """

    if not (len(ids) == len(counts) == len(prices)):
        raise AssertionError(
            "Количество элементов во всех массивах должно совпадать"
        )
    __check_empty_params(
        inn,  kpp, number, date_on, mark_to_sbis, ids, counts, prices
    )
    send_to_email = __make_abominable_boolean(send_to_email)

    params = dict(
        inn=inn,
        kpp=kpp,
        number=number,
        date_on=__modify_date(date_on),
        period=__modify_date(period),
        mark_to_sbis=__make_abominable_boolean(mark_to_sbis),
        email_list=email_list,
        id=ids,
        count=counts,
        price=prices,
        send_invoice=send_to_email,
        send_certificate_of_completion=send_to_email
    )
    # Если не выставляем счет отдельно, нужно добавить параметры к запросу
    if not bill_only:
        if None in {certificate, create_doc_invoice}:
            raise AttributeError(
                'Параметры: certificate, create_doc_invoice '
                'являются обязательными, если счет не выставляется отдельно!!'
            )

        params['create_document_invoice'] = \
            __make_abominable_boolean(create_doc_invoice)
    query = requests.post(
        url=(
            urls.create_invoice(owner)
            if not bill_only
            else urls.create_document_invoice(owner)
        ),
        json=params,
        headers=HEADERS,
        timeout=TIMEOUT * 3
    )
    return __response_processing(query, params)


def get_contract_balance(
        inn: str, kpp: str, date_on: datetime, number: str, owner: ObjectId
):
    """
    :param inn – ИНН контрагента.
    :param kpp – КПП контрагента.
    :param number – номер договора с контрагентом.
    :param date_on – дата, на которую получаем остаток по договору.
    :param owner: ID поставщика услуг

    Запрос баланса клиента по договору.
    Описание работы метода на стороне 1С:
        Метод осуществляет срез суммы остатка по регистру бухгалтерии на дату,
        переданную в запросе, по контрагенту с указанными ИНН и КПП,
        по счету 62.01 Расчеты с покупателями и заказчиками. В качестве
        субконто указывается договор с переданным в запросе номером.
        Проверить данные можно, построив ОСВ по счету 62.01,
        и сравнив полученное значение со значением в колонке
        «Сальдо на конец периода».
    """
    __check_empty_params(inn, kpp, date_on, number)

    params = dict(
        inn=inn,
        kpp=kpp,
        number=number,
        date_on=__modify_date(date_on),
    )
    query = requests.get(
        url=urls.contract_balance(owner),
        params=__encode_params(params),
        timeout=TIMEOUT,
        headers=HEADERS
    )
    return __response_processing(query, params)


def get_reconciliation_report(
        inn: str,
        kpp: str,
        number: str,
        date_start: datetime,
        date_end: datetime,
        owner: ObjectId
):
    """
    Запрос акта сверки.
    Описание работы метода на стороне 1С:
        1) В базе будет создан документ АктСверкиВзаиморасчетов.
           В качестве параметров сверки указаны переданные даты, договор
           и данные контрагента.
        2) Будет сформирована печатная форма с подписью и печатью в формате pdf.
        3) Данные будут упакованы в zip-архив и возвращены в соответствии
           с описанием в пункте «Основные принципы функционирования интеграции».
    """
    __check_empty_params(inn, kpp, date_start, date_end, number)

    params = dict(
        inn=inn,
        kpp=kpp,
        number=number,
        date_start=__modify_date(date_start),
        date_end=__modify_date(date_end),
    )
    query = requests.get(
        url=urls.reconciliation_report(owner),
        params=__encode_params(params),
        timeout=TIMEOUT,
        headers=HEADERS
    )
    return __response_processing(query, params)


def get_client_documents(
        inn: str,
        kpp: str,
        number: str,
        date_start: datetime,
        date_end: datetime,
        owner: ObjectId
):
    """
    Запрос архивного счета и акта выполненных работ. Часть 1.

    ВАЖНО!!!
    Данный метод связан с get_archive_account_and_certificate.

    Описание работы метода на стороне 1С:
        1) Метод получает список документов «РеализацияТоваровУслуг» за
            указанный период по указанному контрагенту и номеру договора.
        2) Составляется соответствие в формате: уникальный идентификатор
            документа в 1С, наименование документа.
        3) Данные конвертируются в формат JSON и возвращаются в теле запроса.
           Пример возвращаемых данных:
            {
            "description": "ОК",
            "value": {
            "adce0565-6bac-11e8-a19a-10bf487bf318": "Реализация (акт, накладная)
            0000-002262 от 09.06.2018 9:37:18",
            "67fbf7fc-1680-11e6-9693-4ccc6a0085de": "Реализация (акт, накладная)
            0000-000388 от 10.05.2016 10:35:20",
            "8702db40-b1c3-11e8-978e-525400793001": "Реализация (акт, накладная)
            0000-003583 от 06.09.2018 13:56:37",
            "32c28608-ce49-11e5-bf03-9c2a701bf57a": "Реализация (акт, накладная)
            0000-000014 от 28.02.2016 12:00:11"
            }
            }

    """
    __check_empty_params(inn, kpp, date_start, date_end, number)

    params = dict(
        inn=inn,
        kpp=kpp,
        number=number,
        date_start=__modify_date(date_start),
        date_end=__modify_date(date_end)
    )
    query = requests.get(
        url=urls.client_document_list(owner),
        params=__encode_params(params),
        timeout=TIMEOUT,
        headers=HEADERS
    )
    return __response_processing(query, params)


def get_archive_account_and_certificate(document_id: str, owner: ObjectId):
    """
    Запрос архивного счета и акта выполненных работ. Часть 2.

    ВАЖНО!!!
    Данный метод связан с get_client_documents.
    :param :id – уникальный идентификатор документа по которому необходимо
                 вернуть счет и акт выполненных работ.

    Описание работы метода на стороне 1С:
        1) Метод получает документ из базы 1С по переданному уникальному
            идентификатору.
        2) Для найденного документа формируются печатные формы счета и акта
            выполненных работ с печатями и подписями в формате pdf.
        3) Сформированные печатные формы упаковываются в zip архив и
            возвращаются в соответствии с описанием в пункте
            «Основные принципы функционирования интеграции».
    """

    params = dict(id=document_id)
    query = requests.get(
        url=urls.payment_document_list(owner),
        params=params,
        timeout=TIMEOUT,
        headers=HEADERS
    )
    return __response_processing(query, params)
