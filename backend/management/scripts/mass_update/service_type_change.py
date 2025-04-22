from bson import ObjectId

from app.offsets.core.run_offsets import run_offsets
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.accrual import Accrual
from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.service_type import ServiceType
from processing.models.logging.custom_scripts import CustomScriptData


def change_service_by_provider(
        logger, task, provider_id,
        service_from_title=None, service_from_code=None,
        service_to_title=None, service_to_code=None,
        service_number=1, doc_id=None):
    """
    Массово заменяет одну услугу на другую в начислениях и тарифных планах

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param provider_id: организация
    :param service_number: какую по счёту найденную услугу заменять
    :param doc_id: замена только в задданом документе начислений
    :param month_till: только по заданный месяц

    Заменяемая услуга. Один из параметров обязательно должен быть задан:
    :param service_from_title: наименование
    :param service_from_code: системный код

    Искомая услуга. Один из параметров обязательно должен быть задан:
    :param service_to_title:
    :param service_to_code:
    """
    provider_id = ObjectId(provider_id)
    service_number = int(service_number)
    service_from = _get_service_type(
        service_code=service_from_code,
        service_title=service_from_title,
        provider_id=provider_id
    )
    service_to = _get_service_type(
        service_code=service_to_code,
        service_title=service_to_title,
        provider_id=provider_id
    )
    if doc_id:
        _change_service_for_house_or_doc(
            logger,
            task,
            provider_id=provider_id,
            house_id=None,
            service_from=service_from,
            service_to=service_to,
            month_till=None,
            service_number=service_number,
            doc_id=ObjectId(doc_id)
        )
    else:
        houses = get_binded_houses(provider_id)
        for ix, house in enumerate(houses):
            logger('дом {} {} из {}'.format(house, ix + 1, len(houses)))
            _change_service_for_house_or_doc(
                logger,
                task,
                provider_id=provider_id,
                house_id=house,
                service_from=service_from,
                service_to=service_to,
                month_till=None,
                service_number=service_number
            )


def change_canalization_service_by_provider(
        logger, task, provider_id, service_number=1):
    """
    Массово заменяет одну услугу канализация на канализацию холодной воды в
    начислениях и тарифных планах

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param provider_id: организация
    :param service_number: какую по счёту найденную услугу заменять
    """
    change_service_by_provider(
        logger, task, provider_id,
        service_from_code='waste_water_individual',
        service_to_code='waste_cold_water_individual',
        service_number=service_number)


def _change_service_for_house_or_doc(logger, task, provider_id, house_id,
                                     service_from, service_to, month_till=None,
                                     service_number=1, doc_id=None):
    if doc_id:
        m_dict = {'doc._id': doc_id}
    else:
        m_dict = {
            'owner': provider_id,
            'account.area.house._id': house_id,
            'services.service_type': service_from.pk,
        }
        if month_till:
            m_dict['month'] = {'$lte': month_till}
    accruals = Accrual.objects(__raw__=m_dict)
    total_count = accruals.count()
    tariff_plans = accruals.distinct('tariff_plan')
    st_replacements = {service_from.pk: service_to.pk}
    dump_data = []
    i = 0
    run_accounts = set()
    run_sectors = set()
    try:
        for ix, accrual in enumerate(accruals, start=1):
            dump_data.append(
                CustomScriptData(
                    task=task.id if task else None,
                    coll='Accrual',
                    data=[accrual.to_mongo()],
                ),
            )
            for k_off, v_on in st_replacements.items():
                ii = 0
                for service in accrual.services:
                    if service.service_type == k_off:
                        ii += 1
                        if ii == service_number:
                            service.service_type = v_on
                            i += 1
                            break
            accrual.save(ignore_lock=True)
            run_accounts.add(accrual.account.id)
            run_sectors.add(accrual.sector_code)
            if ix % 100 == 0:
                CustomScriptData.objects.insert(dump_data)
                dump_data = []
    finally:
        run_offsets(provider_id, list(run_accounts), list(run_sectors))
    if dump_data:
        CustomScriptData.objects.insert(dump_data)
    logger('Заменено {} призплатов в {} начислениях'.format(i, total_count))
    if doc_id or month_till:
        m_dict = {
            '_id': {'$in': tariff_plans},
            'provider': provider_id,
        }
    else:
        m_dict = {
            'provider': provider_id,
            'tariffs.service_type': service_from.pk,
        }
    tariff_plans = TariffPlan.objects(__raw__=m_dict)
    dump_data = CustomScriptData(
        task=task.id if task else None,
        coll='TariffPlan',
        data=[],
    ).save()
    i = 0
    for ix, t_plan in enumerate(tariff_plans.as_pymongo(), start=1):
        CustomScriptData.objects(
            pk=dump_data.pk,
        ).update(
            push__data=t_plan,
        )
        set_dict = {}
        for k_off, v_on in st_replacements.items():
            ii = 0
            for tariff_ix, tariff in enumerate(t_plan['tariffs']):
                if tariff['service_type'] == k_off:
                    ii += 1
                    if ii == service_number:
                        tariff['service_type'] = v_on
                        i += 1
                        update_field_name = f'tariffs.{tariff_ix}.service_type'
                        set_dict[update_field_name] = v_on
                        break
        if set_dict:
            TariffPlan.objects(
                pk=t_plan['_id'],
            ).update(
                __raw__={
                    '$set': set_dict,
                },
            )
        if ix % 100 == 0:
            dump_data = CustomScriptData(
                task=task.id if task else None,
                coll='TariffPlan',
                data=[]
            ).save()
    logger('Заменено {} призплатов в {} тарфиных планах'.format(
        i, len(tariff_plans)
    ))


def _get_service_type(service_title=None, service_code=None, provider_id=None):
    if service_code:
        result = ServiceType.objects(code=service_code).get()
    else:
        result = ServiceType.objects(
            title=service_title,
            provider=provider_id
        ).get()
    return result

