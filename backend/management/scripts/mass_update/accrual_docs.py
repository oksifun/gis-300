from bson import ObjectId

from lib.helpfull_tools import DateHelpFulls
from lib.type_convert import str_to_bool
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.accrual import Accrual
from dateutil.relativedelta import relativedelta

from processing.models.logging.custom_scripts import CustomScriptData


def accrual_doc_unlock(logger, task, accrual_document_id):
    accrual_document_id = ObjectId(accrual_document_id)
    queryset = Accrual.objects(
        doc__id=accrual_document_id,
        lock=True,
    )
    logger(f'нашла {queryset.count()}')
    queryset.update(lock=False)


def set_accrual_doc_pay_till_date(
        logger, task, provider_id, house_id=None,
        months_inc=1, day_of_month=10, last_day_of_month=False):
    """
    Устанавливает документам начислений дату 'Оплатить до'
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param provider_id: организация
    :param house_id: дом (необязательно)
    :param months_inc: сколько месяцев добавить относительно периода документа
    :param day_of_month: какой день установить дате
    :param last_day_of_month: установить последнее число месяца
    :return:
    """
    provider_id = ObjectId(provider_id)
    months_inc = int(months_inc)
    day_of_month = int(day_of_month)
    if last_day_of_month:
        last_day_of_month = str_to_bool(last_day_of_month)
    dump_data = CustomScriptData(
        task=task.id if task else None,
        coll='AccrualDoc',
        data=[],
    ).save()
    match_query = {
        'provider': provider_id,
    }
    if house_id:
        match_query['house._id'] = house_id
    docs = AccrualDoc.objects(__raw__=match_query).as_pymongo()
    logger(f'нашла {docs.count()}')
    u = 0
    for ix, doc in enumerate(docs):
        pay_till = doc['date_from'] + relativedelta(months=months_inc)
        if last_day_of_month:
            pay_till = DateHelpFulls.start_of_day(
                DateHelpFulls.end_of_month(pay_till),
            )
        else:
            try:
                pay_till = pay_till.replace(day=day_of_month)
            except ValueError:
                pay_till = DateHelpFulls.start_of_day(
                    DateHelpFulls.end_of_month(pay_till),
                )
        if doc['pay_till'] == pay_till:
            continue
        CustomScriptData.objects(pk=dump_data.pk).update(
            push__data=doc
        )
        u += 1
        AccrualDoc.objects(pk=doc['_id']).update(pay_till=pay_till)
        Accrual.objects(doc__id=doc['_id']).update(doc__pay_till=pay_till)
        if ix % 1000 == 0:
            dump_data = CustomScriptData(
                task=task.id if task else None,
                coll='AccrualDoc',
                data=[]
            ).save()
    logger('обновила', u)
