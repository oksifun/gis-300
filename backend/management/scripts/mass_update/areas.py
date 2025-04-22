import datetime

from bson import ObjectId

from app.area.models.area import Area, AreaTeleComunication
from processing.models.logging.custom_scripts import CustomScriptData


def put_radio_or_antenna(logger, task, house_id, date_from,
                         field_name='radio_count', number_from=None,
                         number_till=None):
    """
    Скрипт проставляет в квартиры радиоточку или антенну. Информация обновляется
    в первой по списку комнате. Комнаты не добавляются, если их нет.
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param date_from: дата, с которой добавить радиоточку
    :param field_name: что добавлять радиоточку или антенну - имя поля в базе
    :param number_from: номер квартиры, начиная с которой отбирать
    :param number_till: номер квартиры, по которую отбирать
    """
    house_id = ObjectId(house_id)
    if isinstance(date_from, str):
        date_from = datetime.datetime.strptime(date_from, '%d.%m.%Y')
    match_query = {'house._id': house_id, '_type': 'LivingArea'}
    if number_from is not None:
        match_query['number'] = {'$gte': int(number_from)}
    if number_till is not None:
        match_query.setdefault('number', {})
        match_query['number']['$lte'] = int(number_till)
    areas = Area.objects(__raw__=match_query)
    CustomScriptData(
        task=task.id if task else None,
        coll='Area',
        data=list(areas.as_pymongo())
    ).save()
    logger('Найдено квартир {}'.format(areas.count()))
    updated = 0
    for area in areas._iter_results():
        if hasattr(area, 'rooms') and area.rooms:
            updated += 1
            setattr(
                area.rooms[0],
                field_name,
                [AreaTeleComunication(value=1, date=date_from)]
            )
            area.save()
    logger('обновлено', updated)

