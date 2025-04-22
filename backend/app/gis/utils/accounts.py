from datetime import datetime
from dateutil.relativedelta import relativedelta  # НЕ timedelta

from bson import ObjectId

from app.gis.core.exceptions import NoDataError
from app.gis.models.choices import GisObjectType
from app.gis.models.guid import GUID

from app.gis.utils.common import sb, get_time

from app.accruals.models.accrual_document import AccrualDoc

from processing.models.billing.responsibility import Responsibility
from processing.models.billing.account import Tenant  # НЕ Account
from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment
from processing.models.choices import AccrualsSectorType

from processing.data_producers.balance.base import CONDUCTED_STATUSES


ACCOUNT_TYPE_NAMES: dict = {
    GisObjectType.UO_ACCOUNT: "ЛС для оплаты за жилое помещение и КУ",
    GisObjectType.CR_ACCOUNT: "ЛС для оплаты Капитального ремонта",
    GisObjectType.TKO_ACCOUNT: "ЛС для оплаты вывоза ТКО",
    GisObjectType.RSO_ACCOUNT: "ЛС для оплаты за КУ (напрямую с РСО)",
    GisObjectType.RC_ACCOUNT: "ЛС Расчетно-кассового центра",
    GisObjectType.OGV_OMS_ACCOUNT:
        "ЛС органов гос. власти и местного самоуправления",
}

SKIPPABLE_SECTOR_CODES: set = {
    AccrualsSectorType.COMMERCIAL,  # вызов электрика, мытье окон,...
}  # пропускаемые направления платежей


def get_account_type_name(account_type: str) -> str:
    """Получить название назначения ЛС"""
    return ACCOUNT_TYPE_NAMES.get(account_type,
        f"ЛС с типом {sb(account_type)}")


def get_account_type_by(sector_code: str) -> str or None:
    """
    Получить тип (ГИС ЖКХ) ЛС по назначению платежа
    """
    if sector_code in {
        AccrualsSectorType.RENT,
        AccrualsSectorType.TARGET_FEE,  # целевой сбор
        AccrualsSectorType.COMMUNAL,  # водо/тепло/электро-снабжение
        AccrualsSectorType.LEASE,  # аренда?
        AccrualsSectorType.CABLE_TV,  # кабельное?
    }:  # ЛС для оплаты за жилое помещение и КУ
        return GisObjectType.UO_ACCOUNT
    elif sector_code in {
        AccrualsSectorType.CAPITAL_REPAIR,
    }:  # ЛС для оплаты Капитального Ремонта
        return GisObjectType.CR_ACCOUNT
    elif sector_code in {
        AccrualsSectorType.GARBAGE,
    }:  # ЛС для оплаты вывоза ТКО
        return GisObjectType.TKO_ACCOUNT
    elif sector_code in {
        AccrualsSectorType.WATER_SUPPLY,  # Водоканал
        AccrualsSectorType.WASTE_WATER,
        AccrualsSectorType.HEAT_SUPPLY,  # Генерирующая компания
        AccrualsSectorType.GAS_SUPPLY,
    }:  # ЛС для оплаты за КУ (РСО)
        return GisObjectType.RSO_ACCOUNT
    elif sector_code in {
        AccrualsSectorType.SOCIAL_RENT,  # Администрация
    }:  # ЛС Органа Государственной Власти / Местного Самоуправления
        return GisObjectType.OGV_OMS_ACCOUNT
    elif sector_code in SKIPPABLE_SECTOR_CODES:  # "commercial"?
        return None  # пропускаем направление платежа
    elif sector_code in {'rkc'}:  # не используется в Системе
        return GisObjectType.RC_ACCOUNT  # ЛС РЦ
    else:  # тип ЛС не определен?
        return None


def _get_closed_month(provider_id: ObjectId, house_id: ObjectId) -> datetime:
    """
    Получить последний закрытый период начислений организации
    """
    # objects(house__id__in=house_id_s).sort(date_from=-1)  # другой индекс
    last_accrual_doc: dict = AccrualDoc.objects(__raw__={
        # WARN без 'type' - любой тип документа начислений (КУ, КР,...)
        'sector_binds.provider': provider_id,  # получатель платежа (owner)
        # provider - выставляющая документ на оплату организация (РЦ или УО)
        'house._id': house_id,  # разный период формирования по домам
        'status': CONDUCTED_STATUSES,  # только проведенные документы
    }).order_by('-date').as_pymongo().first()  # последний сформированный

    return last_accrual_doc['date_from']


def get_last_accrual_doc_ids(provider_ids: list, house_id: ObjectId) -> list:
    """
    Получить последние (проведенные) документы начислений (дома) организации
    """
    # 'type': AccrualDocumentType.MAIN - нужны не только основные ПД
    grouped_docs = AccrualDoc.objects.aggregate(
        {'$match': {
            # WARN без 'type' - любой тип документа начислений (КУ, КР,...)
            'sector_binds.provider': {'$in': provider_ids},  #получатель платежа
            # provider - выставляющая документ на оплату организация (РЦ или УО)
            'house._id': house_id,  # разный период формирования по домам
            'status': {'$in': CONDUCTED_STATUSES},  # проведенные документы
        }},
        {'$group': {
            '_id': '$date_from',  # ключ возвращаемого набора - период выгрузки
            'ids': {'$push': '$_id'},  # наполняемый список идентификаторов
        }},
        {'$sort': {
            '_id': -1  # сортируем по дате начала (date_from)
        }},
    )  # : CommandCursor

    newest_docs: dict = next(iter(grouped_docs), None)  # первый с конца
    assert newest_docs, "Отсутствуют сформированные платежные документы"

    return newest_docs['ids']


def get_accrual_doc_ids(provider_ids: list, house_id: ObjectId,
        date_from: datetime, date_till: datetime):
    """
    Получить проведенные документы начислений (дома) организации по периоду
    """
    accrual_doc_ids: list = AccrualDoc.objects(__raw__={
        'sector_binds.provider': {'$in': provider_ids},
        'house._id': house_id,
        'status': {'$in': CONDUCTED_STATUSES},
        'date_from': {'$gte': date_from, '$lte': date_till},
        'is_deleted': {'$ne': True},
    }).distinct('_id')
    return accrual_doc_ids


def _get_tariff_plan_ids(provider_id: ObjectId, house_id: ObjectId) -> list:
    """
    Получить используемые в начислениях тарифные планы (дома) организации
    """
    last_accrual_docs: list = get_last_accrual_doc_ids([provider_id], house_id)
    assert last_accrual_docs, \
        "Документы начислений (дома) организации не найдены"

    tariff_plans: list = Accrual.objects(__raw__={
        'owner': provider_id,  # получатель платежа
        'doc._id': {'$in': last_accrual_docs},  # КУ, КР,...
        'doc.status': {'$in': CONDUCTED_STATUSES},  # TODO в работе?
        'tariff_plan': {'$ne': None},  # WARN встречается null
        'is_deleted': {'$ne': True},
    }).distinct('tariff_plan')  # идентификаторы тарифных планов
    assert tariff_plans, "Тарифные планы (документов) начислений не найдены"

    return tariff_plans


def get_accrual_accounts(*accrual_id_s: ObjectId, **accrual_query) -> dict:
    """
    Распределенные по направлениям платежа имеющие начисления жители

    :returns: 'sector_code': [ AccountId,... ]
    """
    if accrual_id_s:  # определенные идентификаторы начислений?
        accrual_query['_id'] = {'$in': accrual_id_s}

    accrual_query['is_deleted'] = {'$ne': True}  # WARN только актуальные

    pipeline: list = [
        {'$match': accrual_query},
        {'$group': {
            '_id': '$sector_code',  # WARN только _id
            'accounts': {'$addToSet': '$account._id'}
        }},
    ]
    # TODO hint('account.area.house._id_1_owner_1')?

    return {group['_id']: group['accounts']
        for group in Accrual.objects.aggregate(*pipeline)}  # : CommandCursor


def get_typed_accounts(*account_id_s: ObjectId, **accrual_query) -> dict:
    """
    Распределенные по типам ЛС имеющие начисления жители

    Одному типу ЛС может соответствовать несколько направлений платежа

    :returns: 'AccountType': [ AccountId,... ]
    """
    typed_accounts: dict = {}

    if account_id_s:  # определенные идентификаторы жильцов?
        # WARN заменяем на запрос по идентификаторам жильцов
        accrual_query = {'account._id': {'$in': account_id_s}}

    for sector_code, accounts in get_accrual_accounts(**accrual_query).items():
        account_type: str = get_account_type_by(sector_code)
        if account_type is None:
            continue  # WARN пропускаем ЛС без определенного типа

        if account_type in typed_accounts:
            typed_accounts[account_type] = list(
                set(typed_accounts[account_type] + accounts)
            )  # копия без дублей
        else:
            typed_accounts[account_type] = accounts

    return typed_accounts


def get_responsible_tenants(provider_ids: list, house_id: ObjectId = None,
        date_from: datetime = None, date_till: datetime = None,
        **query_params) -> list:
    """
    Получить идентификаторы ответственных квартиросъемщиков
    """
    query_params['provider__in'] = provider_ids
    if house_id:  # определенный дом?
        query_params['account__area__house__id'] = house_id

    if not date_from:  # без даты начала?
        date_from = get_time(midnight=True)  # начало текущего дня
    # query_params['date_from__lte'] = date_from  # null=True

    if not date_till:  # без даты окончания?
        date_till = get_time(date_from, months=1)  # следующий месяц
    query_params['date_till__not__lte'] = date_till  # null or gt

    return Responsibility.objects(**query_params).distinct('account._id')


def get_accounts_balance(doc_date: datetime,
        account_ids: list, *sector_code_s: str) -> dict:
    """
    Сальдо по лицевым счетам и направлениям платежей на дату

    :returns: 'sector_code': { AccountId: value }
    """
    query: dict = {
        'account._id': {'$in': account_ids},  # индекс
        'is_deleted': {'$ne': True},
    }  # общие поля для Accrual и Payment
    if sector_code_s:
        query['sector_code'] = {'$in': sector_code_s}

    balance: dict = {}  # задолженность по услугам и направлениям платежа

    # суммируем начисления (увеличивают долг)
    for accrual in Accrual.objects(__raw__={**query,
        'doc.date': {'$lt': doc_date},
        'doc.status': {'$in': CONDUCTED_STATUSES},
    }).only('sector_code', 'account', 'value').as_pymongo():
        sector_code: str = accrual['sector_code']
        account_id: ObjectId = accrual['account']['_id']

        balance.setdefault(sector_code, {}).setdefault(account_id, 0)
        balance[sector_code][account_id] += accrual['value']  # : int

    # вычитаем оплаты (уменьшают долг)
    for payment in Payment.objects(__raw__={**query,
        'date': {'$lt': doc_date},  # НЕ doc.date!
    }).only('sector_code', 'account', 'value').as_pymongo():
        sector_code: str = payment['sector_code']
        account_id: ObjectId = payment['account']['_id']

        balance.setdefault(sector_code, {}).setdefault(account_id, 0)
        balance[sector_code][account_id] -= payment['value']  # : int

    return balance


def update_tenant_gis_data(*tenant_id_s: ObjectId) -> list:
    """
    Обновить ЕЛС и ИЖКУ перечисленных ЛС из имеющихся данных ГИС ЖКХ
    """
    guids = GUID.objects(__raw__={
        'tag': 'UOAccount',  # только ЛС для оплаты КУ
        'object_id': {'$in': tenant_id_s},
        'unique': {'$ne': None},  # с ид. ЖКУ
        'gis': {'$ne': None},  # с ид. ГИС ЖКХ
        'data': None,  # данные сохранены в новым формате?
    }).only('object_id', 'unique')  # : QuerySet

    from pymongo import UpdateOne  # не удаляет имеющиеся поля!

    requests: dict = {}  # "запросы" на изменение данных в БД

    for guid in guids:
        assert isinstance(guid, GUID)
        unified_number: str = guid.unique.split('-')[0]

        # Tenant.objects(id=guid.object_id).update_one(
        #     set__gis_uid=unified_number,  # ЕЛС
        #     set__hcs_uid=guid.unique,  # ид. ЖКУ
        #     upsert=False  # не создавать новые документы
        # )  # обновляем ЛС по-одному

        requests[guid.object_id] = UpdateOne(  # исключаем повторные обновления
            filter={'_id': guid.object_id},  # наличие ЕЛС не учитывается
            update={'$set': {
                'gis_uid': unified_number,  # ЕЛС
                'hcs_uid': guid.unique,  # ид. ЖКУ
            }},  # : dict
            upsert=False)  # не создавать новые документы!

    write_result = Tenant._get_collection().bulk_write(
        [*requests.values()],  # requests must be a list!
        bypass_document_validation=True,  # без валидации
        ordered=False,  # False - параллельно, True - последовательно
    )  # : BulkWriteResult
    assert write_result.matched_count == len(requests), "Обновлены данные" \
        f" ГИС ЖКХ {write_result.matched_count} ЛС из {len(requests)}"

    return list(requests)  # возвращаем ObjectId обновленных ЛС


def _area_living(*area_id_s: ObjectId,
        date_from: datetime = None, date_till: datetime = None) -> dict:
    """
    Количество жильцов в квартирах (в указанный период)

    :returns: (area.id, family.householder): count
    """
    if not date_from:  # период проживания "от" не указан?
        date_from = datetime.now() \
            .replace(minute=0, hour=0, second=0, microsecond=0)  # текущий!

    if not date_till:  # период проживания "до" не указан?
        date_till = date_from + relativedelta(months=1)  # следующий месяц!

    groups = Tenant.objects(__raw__={
        'area._id': {'$in': area_id_s},
        'statuses.living': {'$exists': True, '$ne': []},  # лишняя проверка?
        'statuses.living.date_from': {'$lte': date_from},
        'statuses.living.date_till': {
            '$not': {'$lte': date_till}  # null or gt
        },
        'is_deleted': {'$ne': True},
    }).as_pymongo().aggregate({
        '$group': {
            '_id': {  # ключ группировки
                'area': '$area._id',
                'holder': '$family.householder'  # может отсутствовать!
            },
            'count': {'$sum': 1}}
    })  # : QuerySet

    area_tenant_count = {(group['_id']['area'], group['_id'].get('holder')):
        group['count'] for group in groups}

    return area_tenant_count


def get_no_uid_tenant_ids(account_ids: list) -> list:
    """Идентификаторы ЛС без номера ЕЛС"""

    return Tenant.objects(__raw__={
        '_id': {'$in': account_ids},
        'gis_uid': {'$in': [None, '']},
    }).distinct('id')  # : [ TenantId,... ]
