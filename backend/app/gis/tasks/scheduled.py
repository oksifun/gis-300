from bson import ObjectId

from app.gis.workers.config import gis_celery_app
from settings import GIS

from app.gis.models.choices import GisRecordStatusType, IDLE_RECORD_STATUSES
from app.gis.models.gis_record import GisRecord
from app.gis.models.guid import GUID
from app.gis.models.gis_queued import GisQueued, QueuedType

from app.gis.utils.common import sb, get_time
from app.gis.utils.houses import get_provider_metering_house_ids

from app.gis.tasks.async_operation import fetch_result
from app.gis.tasks.gis_task import GisTask

from app.gis.services.house_management import HouseManagement
from app.gis.services.device_metering import DeviceMetering
from app.gis.services.bills import Bills


@gis_celery_app.task(name='gis.reanimate', ignore_result=True)
def reanimate(saved_days_ago: int = 2, acked_hours_ago: int = 24):
    """
    Получить результат(ы) невыполненных операций

    :param saved_days_ago: последняя активность (сохранение) менее [дней] назад
    :param acked_hours_ago: получено (в обработке) ГИС ЖКХ более [часов] назад,
        по нормативу запрос обрабатывается не более суток!
    """
    task = GisTask(name='gis.reanimate')
    try:
        if not GIS.get('reanimate_exec'):  # не перезапускать просроченные?
            raise PermissionError(
                "Перезапуск просроченных операций не выполняется"
            )

        task.operations = GisRecord.objects(__raw__={  # записи об операциях
            'saved': {'$gt': get_time(days=-saved_days_ago)},
            'acked': {'$lt': get_time(hours=-acked_hours_ago)},
            'status': GisRecordStatusType.EXECUTING,  # Выполняется
        }).order_by('saved').distinct('id')

        if not task.operations:  # нет подлежащих перезапуску?
            raise ValueError(
                "Отсутствуют подлежащие перезапуску просроченные операции"
            )

        eta = get_time(hours=-3, minutes=3)  # 01:15:00 WARN UTC
        for record_id in task.operations:
            eta = get_time(eta, seconds=5)  # 01:15:05, 01:15:10,...
            fetch_result.apply_async(
                args=(record_id, True),  # форсированный запуск операции
                eta=eta,  # последовательный запуск операций с интервалом
            )
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


@gis_celery_app.task(name='gis.scheduled', ignore_result=True)
def scheduled(types: list or tuple = GisQueued.ORDERED_TYPES):
    """
    Выгрузить в ГИС ЖКХ данные созданных и измененных объектов

    :param types: типы подлежащих выгрузке объектов (или все)
    """
    def _get_operation(object_type: str):

        if object_type in {QueuedType.HOUSE, QueuedType.AREA}:
            return HouseManagement.importHouseUOData
        elif object_type in {QueuedType.TENANT, *GUID.ACCOUNT_TAGS}:
            return HouseManagement.importAccountData
        elif object_type in {QueuedType.AREA_METER, QueuedType.HOUSE_METER}:
            return HouseManagement.importMeteringDeviceData
        elif object_type in {QueuedType.ACCRUAL, QueuedType.ACCRUAL_DOC}:
            raise TypeError("Выгрузка (документов) начислений"
                " выполняется отдельно от других типов объектов")
        else:
            raise NotImplementedError("Операция для объекта"
                f" типа {sb(object_type)} не определена")

    task = GisTask(name='gis.scheduled')
    try:
        if not GIS.get('export_changes'):  # не выгружать изменения?
            raise PermissionError("Выгрузка изменений в ГИС ЖКХ не выполняется")

        # 'ObjectType': ProviderId: HouseId: ObjectId: saved
        distributed: dict = GisQueued.distributed(*types)
        if not distributed:  # нет подлежащих выгрузке?
            # raise ValueError(
            #     "Отсутствуют подлежащие выгрузке в ГИС ЖКХ изменения"
            # )
            return  # WARN не сохраняем пустые записи о выполнении

        for _object_type, provider_houses in distributed.items():
            operation = _get_operation(_object_type)  # класс операции

            for provider_id, housed_objects in provider_houses.items():
                task.add_provider(provider_id)
                for house_id, queued_objects in housed_objects.items():
                    task.add_house(house_id)
                    _import = operation(provider_id, house_id,
                        is_scheduled=True, update_existing=True)
                    task.operations.append(_import.record_id)
                    _import(*queued_objects)  # ~ keys (values = saved)
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


@gis_celery_app.task(name='gis.conducted', ignore_result=True)
def conducted():  # AccrualDoc
    """
    Выгрузить подготовленные (закрытые) документы начислений в ГИС ЖКХ
    """
    task = GisTask(name='gis.conducted')
    try:
        if not GIS.get('export_changes'):  # не выгружать изменения?
            raise PermissionError("Выгрузка изменений в ГИС ЖКХ не выполняется")

        distributed: dict = GisQueued.distributed(QueuedType.ACCRUAL_DOC)
        if not distributed:  # нет подлежащих выгрузке?
            raise ValueError(
                "Отсутствуют подлежащие выгрузке в ГИС ЖКХ документы начислений"
            )

        for object_type, provider_houses in distributed.items():
            for provider_id, housed_documents in provider_houses.items():
                task.add_provider(provider_id)
                for house_id, documents in housed_documents.items():
                    task.add_house(house_id)
                    for accrual_doc_id in documents:  # ~ keys
                        _import = Bills.importPaymentDocumentData(
                            provider_id, house_id, is_scheduled=True)
                        task.operations.append(_import.record_id)
                        _import.document(accrual_doc_id)  # начисления документа
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


@gis_celery_app.task(name='gis.resurrect', ignore_result=True)
def resurrect(saved_days_ago: int = 5):
    """
    Повторно отправить задачи в работу с ошибками от ГИС
    вида 500 Internal Server Error или Timeout Error

    :param saved_days_ago: последняя активность (сохранение) менее [дней] назад
    """
    task = GisTask(name='gis.resurrect')
    try:
        if not GIS.get('resurrect_errors'):  # не перезапускать ошибочные?
            raise PermissionError(
                "Перезапуск ошибочных операций не выполняется"
            )

        error_limit = 'Исчерпан лимит получения результата обработки сообщения'
        error_retry = (
            'EXP001000: Произошла ошибка при передаче данных. Попробуйте '
            'осуществить передачу данных повторно. В случае, если повторная '
            'передача данных не проходит - направьте обращение в службу '
            'поддержки пользователей ГИС ЖКХ.'
        )
        error_send_request = ('Превышено ограничение по времени выполнения '
                              'задачи отправки запроса операции')
        error_fetch_result = ('Превышено ограничение по времени выполнения '
                              'задачи получения результата операции')

        error_messages = [
            error_limit,
            error_retry,
            error_send_request,
            error_fetch_result
        ]
        task.operations = GisRecord.objects(__raw__={
            "status": GisRecordStatusType.ERROR,  # статус Ошибка
            "error": {"$in": error_messages},  # перечисленные ошибки
            'saved': {'$gt': get_time(days=-saved_days_ago)},
        }).order_by('saved').distinct("_id")

        if not task.operations:  # нет подлежащих перезапуску?
            raise ValueError(
                "Отсутствуют подлежащие перезапуску ошибочные операции"
            )

        for record_id in task.operations:
            # Готовим задачу к перезапуску
            gis_record: GisRecord = GisRecord.objects(pk=record_id).first()
            gis_record.update(
                set__retries=0,  # обнуляем количество попыток
                unset__message_guid=1,  # удаляем id запроса
                unset__ack_guid=1,  # удаляем id ответа
                unset__acked=1,  # удаляем дату ответа
                set__options__is_resurrected=True,  # помечаем, как восставшую
            )
            # Перезапускаем задачу
            from app.gis.tasks.async_operation import send_request
            send_request.delay(record_id, True)  # форсированный запуск операции
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


@gis_celery_app.task(name='gis.gathered', ignore_result=True)
def gathered():  # Meter.readings
    """
    Выгрузить в ГИС ЖКХ полученные показания ПУ
    """
    task = GisTask(name='gis.gathered')
    try:
        # находим идентификаторы домов с (сегодняшним) днем окончания приема
        distributed = get_provider_metering_house_ids(at_end_day=True)
        if not distributed:  # нет подлежащих загрузке?
            raise ValueError(
                "Нет завершивших сегодня прием показаний (домов) организаций"
            )
        for provider_id, house_ids in distributed.items():
            task.add_provider(provider_id)
            for house_id in house_ids:
                task.add_house(house_id)
                # WARN без предварительной загрузки данных отсутствующих ПУ
                _export = DeviceMetering.exportMeteringDeviceHistory(
                    provider_id, house_id, is_scheduled=True)
                task.operations.append(_export.record_id)
                _export.house_meterings()  # всех видов ПУ за текущий период
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


@gis_celery_app.task(name='gis.collected', ignore_result=True)
def collected():  # Meter.readings
    """
    Загрузить из ГИС ЖКХ переданные показания ПУ
    """
    task = GisTask(name='gis.collected')
    try:
        if not GIS.get('export_changes'):  # не выгружать изменения?
            raise PermissionError("Выгрузка изменений в ГИС ЖКХ не выполняется")

        # находим идентификаторы домов с (сегодняшним) днем начала приема
        distributed = get_provider_metering_house_ids()
        if not distributed:  # нет подлежащих выгрузке?
            raise ValueError(
                "Нет начавших сегодня прием показаний (домов) организаций"
            )
        for provider_id, house_ids in distributed.items():
            task.add_provider(provider_id)
            for house_id in house_ids:
                task.add_house(house_id)
                _import = DeviceMetering.importMeteringDeviceValues(
                    provider_id, house_id, is_scheduled=True)
                task.operations.append(_import.record_id)
                _import.area_meterings()  # ИПУ за текущий период

        # находим идентификаторы домов с подлежащими выгрузке ОДПУ
        provider_houses: dict = get_provider_metering_house_ids(
            *distributed,  # те же организации со днем начала приема
            is_collective=True  # подлежат выгрузке показания ОДПУ
        )
        for provider_id, house_ids in provider_houses.items():
            task.add_provider(provider_id)
            for house_id in house_ids:
                task.add_house(house_id)
                _import = DeviceMetering.importMeteringDeviceValues(
                    provider_id, house_id, is_scheduled=True)
                task.operations.append(_import.record_id)
                _import.house_meterings()  # ОДПУ за текущий период
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


@gis_celery_app.task(name='gis.cleanup', ignore_result=True)
def cleanup(older: int = 2, newer: int = None):
    """
    Удалить неактуальные записи об операциях

    :param older: сохраненные ранее указанного числа месяцев
    :param newer: сохраненные позднее указанного числа месяцев,
        None - все записи об операциях, сохраненные ранее older
    """
    # TODO удалить ненужные GisTask

    task = GisTask(name='gis.cleanup')
    try:
        assert older and (not newer or older < newer)  # -o > -n

        before = get_time(months=-older, midnight=True)
        after = get_time(months=-newer, midnight=True) if newer else None

        # WARN # удаляем записи о неактуальных (старых) операциях
        task.operations = GisRecord.purge(before, after)

        MAXIMUM_REQUEST_HOURS: int = 72  # часа

        before = get_time(hours=-MAXIMUM_REQUEST_HOURS)  # тот же after
        # WARN удаляем записи о бесперспективных (не начавшихся) операциях
        task.operations += GisRecord.purge(before, after, *IDLE_RECORD_STATUSES)
    except Exception as error:
        task.error = str(error)
    finally:
        task.save()


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    # cleanup(); exit()

    GisQueued._DELETE_RECYCLED = False
    GisQueued._DEFAULT_MIN_DELAY = 0

    # scheduled(); exit()
    conducted(); exit()
    # collected(); exit()
    # gathered(); exit()
