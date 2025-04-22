from bson import ObjectId

from mongoengine_connections import register_mongoengine_connections
from app.offsets.core.run_offsets import run_offsets
from processing.models.billing import TariffPlan, Accrual
from processing.models.logging.custom_scripts import CustomScriptData

def changing_tariff_plan(logger, task, tariff_plan, bad_service_type,
                         good_service_type):

    """
    Исправляет неверный услуги у тарифных планов и начислений, имеющих
    ссылку на эти тарифные планы.

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param tariff_plan: тарифный план
    :param bad_service_type: ошибочная услуга, которую нужно исправить
    :param good_service_type: правильная услуга
    :return:
    """

    pairs = []
    accruals = Accrual.objects(
        tariff_plan=tariff_plan
    )
    logger(f'Начилений найдено: {accruals.count()}')
    CustomScriptData(
        task=task.id if task else None,
        coll='Accrual',
        data=list(accruals.as_pymongo()),
    ).save()
    provider_id = None
    accounts_set = set()
    sectors_set = set()
    for accrual in accruals:
        if not provider_id:
            provider_id = accrual.doc.provider
        accounts_set.add(accrual.account.id)
        sectors_set.add(accrual.sector_code)

        for service in accrual.services:
            if service.service_type == bad_service_type:
                service.service_type = good_service_type

        save_model(accrual, logger)
    logger(f'Начиления изменены')

    tariff_plan = TariffPlan.objects(id=tariff_plan)
    CustomScriptData(
        task=task.id if task else None,
        coll='Tariff_plan',
        data=list(tariff_plan.as_pymongo()),
    ).save()
    tariff_plan = tariff_plan.first()
    logger(f'Обновление тарифного плана')
    for tariff in tariff_plan.tariffs:
        if tariff.service_type == bad_service_type:
            tariff.service_type = good_service_type
    save_model(tariff_plan, logger)
    logger(f'Тарифные планы изменены\n______________________________')
    run_offsets(
        provider_id=provider_id,
        account_ids=accounts_set,
        sector_codes=sectors_set,
    )


def save_model(model, logger):
    try:
        kwargs = dict()
        if model._class_name == 'Accrual':
            kwargs.update(dict(ignore_lock=True))
        model.save(**kwargs)
    except Exception as err:
        logger(f'Ошибка сохранения {model._class_name} {model.id}: {err}')


if __name__ == "__main__":
    register_mongoengine_connections()
    tariff_plans = [
        ObjectId("5ea7c7ee4d3992003e01661e"),
        ObjectId("5dfa148a12f3dd00186cdab9"),
        ObjectId("5e68a69b802b0f002bc29cad"),
        ObjectId("5e33ea494a8e2c0050eff7e6"),
        ObjectId("5e186c6842aaca002da2ff8b"),
        ObjectId("5e283c22737bde00430dad28")
]
    bad_id = ObjectId("526234c0e0e34c474382233c")
    good_id = ObjectId("5936af7ccd3024006a086e62")
    for tariff_plan in tariff_plans:
        changing_tariff_plan(print, None, tariff_plan, bad_id, good_id)
