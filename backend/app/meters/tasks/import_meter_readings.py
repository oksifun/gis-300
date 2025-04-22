from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from app.celery_admin.workers.config import celery_app
from app.messages.tasks.users_tasks import update_meters_messages
from app.meters.core.readings.parsers import (
    IMPORT_READINGS_METER_TYPES_CHOICES, MeterDataType, parse_readings_file
)
from app.meters.models.choices import ImportReadingsTaskStatus
from app.meters.models.meter import Meter, AreaMeter, MeterEmbeddedArea, \
    MeterDataValidationError, ReadingsValidationError, MeterCheckEmbedded
from app.meters.models.tasks import ImportMeterReadingsTask, \
    TempMeterDataReadings, NotFoundMeter, FailMeter, FailReading
from app.personnel.models.personnel import Worker
from lib.gridfs import delete_file_in_gridfs


@celery_app.task(
    soft_time_limit=10*60,
    rate_limit='10/s',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def parse_meter_readings(self, task_id, file_id, house_id, period, account_id):
    task = ImportMeterReadingsTask.objects(id=task_id).first()
    task.status = ImportReadingsTaskStatus.PARSING
    task.description = 'парсинг файла'
    task.save()

    # Парсим и валидируем данные из файла
    data = parse_readings_file(file_id, task)
    task.description = 'проверка счетчиков'
    task.save()
    bads = {'count': 0, 'meters': []}

    # Проверяем все ли счетчики есть в базе и собираем список не найденных
    for meter_type in IMPORT_READINGS_METER_TYPES_CHOICES:
        match = {
            'area.house._id': ObjectId(house_id),
            'is_automatic': True,
            'serial_number': {
                '$in': [
                    x['serial_number']
                    for x in data
                    if x['meter_type'] == meter_type[0]
                ],
            },
            'area.str_number': {
                '$in': [
                    x['area_number']
                    for x in data
                    if x['meter_type'] == meter_type[0]
                ],
            },
            'working_start_date': {
                '$lt': period + relativedelta(months=1),
            },
            '$or': [
                {'working_finish_date': None},
                {'working_finish_date': {'$gte': period}},
            ],
            'is_deleted': {'$ne': True},
        }
        pipeline = [
            {'$match': match},
            {'$project': {
                'serial_number': 1,
                'area': 1,
            }},
        ]
        mm_ids = [m['_id'] for m in Meter.objects.aggregate(*pipeline)]
        mm = AreaMeter.objects(pk__in=mm_ids)
        meters = {}
        for m in mm:
            meters.setdefault(m.area.str_number, [])
            meters[m.area.str_number].append(m)
        for el in [x for x in data if x['meter_type'] == meter_type[0]]:
            mm = meters.get(el['area_number'], [])
            for m in mm:
                if el['serial_number'] == m.serial_number:
                    el['meter'] = m.id
                    break
            if not el.get('meter'):
                bads['meters'].append(el)
    data = list(filter(lambda x: 'meter' in x, data))

    # Временно сохраняем показания по найденным счетчикам
    task.description = 'временное сохранение показаний'
    task.save()
    for meter in data:
        reading = TempMeterDataReadings(**meter)
        if isinstance(meter['values'], list):
            reading.values = meter['values']
        else:
            reading.values = [meter['values']]
        if isinstance(meter.get('points', 0), list):
            reading.points = meter['points']
        else:
            reading.points = [meter.get('points', 0)]
        reading.task_id = task_id
        reading.save()

    # Готовим ненайденные счетчики к записи в задачу
    task.description = 'подготовка ненайденных счетчиков'
    task.save()
    for bad in bads['meters']:
        if isinstance(bad['values'], list):
            bad['values'] = ', '.join(map(str, bad['values']))
        else:
            bad['values'] = str(bad['values'])
        if isinstance(bad.get('points'), list):
            bad['points'] = ', '.join(map(str, bad.get('points', 0)))
        else:
            bad['points'] = str(bad.get('points', 0))
        bad['house_consumption'] = str(bad.get('house_consumption', 0))

    # Обновляем задачу
    if data:
        task.status = ImportReadingsTaskStatus.PARSED
    else:
        task.status = ImportReadingsTaskStatus.FAILED
    task.found = len(data)
    task.not_found = len(bads['meters'])
    task.not_found_meters = [NotFoundMeter(**bad) for bad in bads['meters']]
    task.save()

    delete_file_in_gridfs(file_id)
    update_meters_messages.delay(house_id, account_id, 'checked')


@celery_app.task(
    soft_time_limit=30*60,
    rate_limit='10/s',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def save_meter_readings(self, task_id, create_new_meters, account_id):
    account = Worker.objects(pk=account_id).get()
    task = ImportMeterReadingsTask.objects(id=task_id).first()
    house_id, period, bads = (
        task.house_id,
        task.period,
        task.not_found_meters,
    )
    task.status = ImportReadingsTaskStatus.SAVING
    task.save()
    # Создаем новые счетчики
    if create_new_meters and bads:
        areas = Area.objects(
            house__id=house_id,
            number__in=[x['area_number'] for x in bads]
        )
        areas_numbers = {str(area['number']): area for area in areas}
        for bad in bads:
            area = areas_numbers.get(bad['area_number'])
            if not area:
                continue
            meter = AreaMeter(
                _type=['HeatAreaMeter'],
                area=MeterEmbeddedArea(id=area.pk),
                serial_number=bad['serial_number'],
                is_automatic=True,
                working_finish_date=None,
                installation_date=period,
                initial_values=[0],
                check_history=[
                    MeterCheckEmbedded(
                        working_start_date=period,
                        check_date=period,
                        expiration_date_check=6,
                    ),
                ]
            )
            try:
                meter.save()
            except MeterDataValidationError as err:
                task.fail_meters.append(
                    FailMeter(
                        serial_number=bad['serial_number'],
                        error=str(err)
                    )
                )
                task.save()
            except Exception:
                task.fail_meters.append(
                    FailMeter(
                        serial_number=meter.serial_number,
                        error='Неизвестная ошибка',
                    ),
                )
                task.save()

    # Читаем временные данные и обновляем показания счетчиков
    data = TempMeterDataReadings.objects(task_id=task_id)
    for reading in data:
        meter = AreaMeter.objects(id=reading.meter).first()
        try:
            meter.add_readings(
                period=period,
                values=reading.values,
                creator=account._type[0].lower(),
                actor_id=account.id,
                values_are_deltas=reading.data_type == MeterDataType.deltas,
                points=reading.points,
            )
        except ReadingsValidationError as err:
            task.fail_readings.append(
                FailReading(
                    meter=reading.meter,
                    serial_number=reading.serial_number,
                    error=str(err),
                ),
            )
            task.save()
        try:
            meter.save()
        except MeterDataValidationError as err:
            task.fail_meters.append(
                FailMeter(
                    serial_number=meter.serial_number,
                    error=str(err),
                ),
            )
            task.save()
        except Exception:
            task.fail_meters.append(
                FailMeter(
                    serial_number=meter.serial_number,
                    error='Неизвестная ошибка',
                ),
            )
            task.save()
    task.status = ImportReadingsTaskStatus.FINISHED
    task.save()
    TempMeterDataReadings.objects(task_id=task_id).delete()
    update_meters_messages.delay(house_id, account.id, 'saved')
    return {'saved': len(data)}
