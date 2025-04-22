import datetime

from bson import ObjectId

from app.meters.models.meter import AreaMeter
from lib.type_convert import str_to_bool
from processing.models.logging.custom_scripts import CustomScriptData


def change_meters_check_date(logger, task, house_id, check_date,
                             update_all_fields=False, first_area_number=None,
                             last_area_number=None, interval=None):

    """
    Проставляет дату проверки счеткиков

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param check_date: дата проверки
    :param update_all_fields: условия для выбора по умолчанию, False,
    какие поля заполнять, если True, то поля last_check_date,
    first_check_date, installation_date примут значение check_date.
    Если False, только last_check_date примет занчение check_date
    :param first_area_number: номер квартиры
    :param last_area_number: номер квартиры
    :param interval: период с указанной даты
    """
    def check_number(area_number):
        area_number = area_number.lower()
        area_type = 'LivingArea'
        if 'н' in area_number:
            area_number = area_number.replace('н', '')
            area_type = 'NotLivingArea'
        elif 'п' in area_number:
            area_number = area_number.replace('п', '')
            area_type = 'ParkingArea'
        if area_number.isdigit():
            area_number = int(area_number)
        return area_number, area_type

    house_id = ObjectId(house_id)
    check_date = datetime.datetime.strptime(check_date, '%d.%m.%Y')
    first_area_type = None
    last_area_type = None

    if first_area_number:
        first_area_number, first_area_type = check_number(first_area_number)
    if last_area_number:
        last_area_number, last_area_type = check_number(last_area_number)
    if interval:
        try:
            interval = int(interval)
        except Exception:
            raise Exception(f'Неверно задан интервал {interval}')

    if update_all_fields:
        update_all_fields = str_to_bool(update_all_fields)

    if first_area_type == last_area_type:
        area_type = first_area_type
    else:
        raise Exception(
            f'Помещения {first_area_type} и {last_area_type} разного типа',
        )

    if first_area_number and last_area_number:
        query = {
            'area.house._id': house_id,
            'area._type': area_type,
            'area.number': {
                "$gte": first_area_number,
                "$lte": last_area_number,
            },
            'working_finish_date': None,
        }
    elif not first_area_number and not last_area_number:
        query = {
            'area.house._id': house_id,
            'working_finish_date': None,
        }
    else:
        raise Exception(
            f'Помещения {first_area_type} и {last_area_type} разного типа',
        )

    all_meters = AreaMeter.objects(__raw__=query)
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=list(all_meters.as_pymongo())
    ).save()
    logger('найдено {}'.format(all_meters.count()))
    for area_meter in all_meters._iter_results():
        try:
            if update_all_fields:
                area_meter.check_history[-1].check_date = check_date
                area_meter.installation_date = check_date
            else:
                area_meter.check_history[-1].check_date = check_date
            if interval:
                area_meter.check_history[-1].expiration_date_check = check_date
            area_meter.save()
        except Exception as e:
            logger(
                'Ошибка в квартире {}. {}'.format(
                    area_meter.area.number,
                    e
                )
            )
