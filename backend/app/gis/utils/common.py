from sys import stdout

from typing import Optional, Iterable, Mapping

from bson import ObjectId
from uuid import uuid1, UUID

from random import random
from hashlib import md5

from pytz import timezone, UTC
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # class
from dateutil.parser import parse as parse_date

from pprint import pprint, pformat


MONTH_NAMES: list = [
    "[МЕСЯЦ]",   # нулевой индекс
    "Январь",    # 01
    "Февраль",   # 02
    "Март",      # 03
    "Апрель",    # 04
    "Май",       # 05
    "Июнь",      # 06
    "Июль",      # 07
    "Август",    # 08
    "Сентябрь",  # 09
    "Октябрь",   # 10
    "Ноябрь",    # 11
    "Декабрь"    # 12
]


def last_month_day(date_time: datetime = None) -> int:
    """Номер последнего дня месяца"""
    if date_time is None:
        date_time = get_time()

    from calendar import monthrange
    return monthrange(date_time.year, date_time.month)[1]


def is_between(moment: datetime = None,
        earlie: datetime = None, later: datetime = None,
        including: bool = True) -> bool:
    """
    Дата и время попадают в заданный интервал времени?

    Вызов без аргументов возвращает True!

    :param moment: определенный момент времени или текущий
    :param earlie: начало интервала или текущего дня
    :param later: конец интервала или текущего дня
    :param including: включая начало и конец интервала
    """
    now = datetime.now()  # текущие дата и время БЕЗ временной зоны

    if not moment:  # момент не определен?
        moment = now  # текущие момент времени

    if not earlie:  # начало интервала не указано?
        earlie = moment.replace(hour=0, minute=0, second=0,
            microsecond=0)  # начало дня момента времени
    elif earlie > moment:  # момент не настал?
        return False

    if not later:  # конец интервала не указан?
        later = moment.replace(hour=23, minute=59, second=59,
            microsecond=999999)  # конец дня момента времени
    elif later < moment:  # момент упущен?
        return False

    assert earlie <= later, "Начало временного интервала позднее его окончания"

    return (earlie <= moment <= later) if including \
        else (earlie < moment < later)


def get_time(moment: datetime = None, midnight: bool = False,
        **delta) -> datetime:
    """
    Текущие дата и время БЕЗ информации о временной зоне (для MongoDB)

    ГИС ЖКХ принимает дату (и время) как с временной зоной, так и без нее
    ГИС ЖКХ возвращает дату (и время) БЕЗ информации о временной зоне

    Возможные аргументы delta (разницы во времени):
        years, months, weeks, days, hours, minutes, seconds, milliseconds,
        microseconds (или ms)
    """
    delta_keys: set = {
        # стандартные аргументы timedelta:
        'weeks', 'days', 'hours', 'minutes', 'seconds',
        'milliseconds', 'microseconds',  # миллисекунда = 1000 микросекунд
        'years', 'months', 'ms'  # WARN дополнительные аргументы
    }

    assert not delta or set(delta) & delta_keys, \
        "Некорректный аргумент сдвига времени"

    if moment is None:
        date_time = datetime.now()  # текущее время без временной зоны
    elif isinstance(moment, str):
        date_time = parse_date(moment)  # WARN parser_info по умолчанию
    else:
        assert isinstance(moment, datetime)
        date_time = moment

    if midnight:  # полночь (сброс времени)?
        date_time = date_time.replace(hour=0, minute=0, second=0, microsecond=0)

    if 'years' in delta:  # годы?
        date_time += relativedelta(years=delta.pop('years'))
    if 'months' in delta:  # месяцы?
        date_time += relativedelta(months=delta.pop('months'))

    if 'ms' in delta:  # микросекунды?
        date_time = date_time.replace(microsecond=delta.pop('ms'))

    if delta:  # задан сдвиг времени?
        return date_time + timedelta(**delta)

    return date_time


def get_celery_tz(override: str = None):

    if override:
        return timezone(override)

    from processing.celery.config import CELERY_CONFIG

    if CELERY_CONFIG.get('enable_utc', False):
        return UTC  # ~ timezone('UTC')

    tz = CELERY_CONFIG.get('timezone', 'UTC')  # 'Europe/Moscow'
    if isinstance(tz, str):
        tz = timezone(tz)

    return tz


def dt_in_celery_tz(**delta) -> datetime:
    """
    Дата и время во временной зоне Celery

    :param delta: изменение (дельта) текущих даты и времени в формате timedelta:
        days,seconds,microseconds,milliseconds,minutes,hours,weeks: float
    """
    # альтернативный вариант: get_celery_tz().localize(datetime.now())
    now = datetime.now(get_celery_tz())

    return now + timedelta(**delta) if delta else now


def local_time(moment: datetime = None,
        tz=timezone('Europe/Moscow')) -> datetime:
    """Дата и время в определенной временной зоне"""
    if not moment:  # не определенное время?
        moment = datetime.now()  # текущий момент времени

    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        moment = moment.replace(tzinfo=UTC)  # временная зона по умолчанию

    return moment.astimezone(tz)


def mongo_time(moment: datetime) -> datetime:
    """Дата и время без временной зоны (для MongoDB)"""
    return local_time(moment).replace(tzinfo=None)


def tuple_eta(time: tuple, date: tuple = None) -> datetime:
    """
    Estimated Time of Arrival - самое раннее время выполнения задачи

    Если задано время в прошлом, то задача выполнится при первой же возможности!

    :param time: время в формате (час, минута, секунда)
    :param date: дата в формате (год, месяц, день)
    :return: дата и время с учетом временной зоны (UTC)
    """
    now = dt_in_celery_tz()

    if date is None:
        date = (now.year, now.month, now.day)

    if len(time) < 3:
        time = time + (0,)*(3 - len(time))  # (14, 0, 0)

    eta = datetime(*date, *time, tzinfo=None)
    eta = eta.astimezone(get_celery_tz())

    if eta < now:
        tm = now + timedelta(days=1)  # tomorrow
        eta = eta.replace(day=tm.day, month=tm.month, year=tm.year)

    return eta


def delta_eta(days=0, hours=0, minutes=0, seconds=0) -> datetime:
    """
    Дата и время с указанным сдвигом относительно текущего времени

    :return: дата и время с учетом временной зоны
    """
    now = dt_in_celery_tz()
    eta = now + timedelta(days=days,
        hours=hours, minutes=minutes, seconds=seconds)
    return eta.astimezone(get_celery_tz())


def total_seconds(**kwargs) -> int:

    return int(timedelta(**kwargs).total_seconds())


def get_min_time() -> datetime:
    """Минимальная дата и время ГИС ЖКХ"""
    return datetime(year=1000, month=1, day=1,  # TODO или 0 год?
        hour=0, minute=0, second=0, microsecond=0)


def get_max_time() -> datetime:
    """Максимальная дата и время ГИС ЖКХ"""
    return datetime(year=5000, month=1, day=1,
        hour=0, minute=0, second=0, microsecond=0)


def get_period(including: datetime = None, months: int = 0,
        first_day: bool or None = True) -> datetime:
    """
    Получить (текущий) расчетный период

    По умолчанию (без аргументов) - первый день текущего месяца (полночь)

    :param including: период должен включать указанную дату
    :param months: отрицательное значение означает предыдущий месяц
    :param first_day: True (по умолчанию) - первый день месяца
        False - последний день месяца, None - не изменять день месяца
    """
    # WARN в периоде всегда присутствует время 00:00:00.000Z ~ MongoDB.Date
    if including is None:
        period = datetime.now()
    elif isinstance(including, str):
        period = parse_date(including)  # WARN parser_info по умолчанию
    else:
        period = including

    if months:  # сдвиг по месяцам?
        period += relativedelta(months=months)

    if first_day is True:  # первый день месяца?
        period = period.replace(day=1,
            hour=0, minute=0, second=0, microsecond=0)  # начало дня
    elif first_day is False:  # последний день месяца?
        period += relativedelta(months=1, days=-1,
            day=1,  # WARN выполняется до сдвига месяца и дня
            hour=23, minute=59, second=59, microsecond=999)  # конец дня
    else:  # first_day = None - не изменять день месяца (без времени)!
        period = period.replace(hour=0, minute=0, second=0, microsecond=0)

    return period


def fmt_period(period: datetime,  # или date или str
        with_day: bool = False, genitive_case: bool = False) -> str:
    """
    Название периода для форматированного вывода

    :param period: период в виде даты (со временем)
    :param with_day: возвращать день
    :param genitive_case: название месяца в родительном падеже
    """
    if not period:  # период не указан?
        period = get_period()  # текущий период
    elif isinstance(period, str):
        period = parse_date(period)  # : datetime

    if isinstance(period, datetime):
        period = period.date()  # отбрасываем время

    month_name: str = MONTH_NAMES[period.month]  # индекс списка = номер месяца
    if with_day or genitive_case:  # в родительном падеже?
        month_name = month_name.lower() + 'а' if month_name[-1] == 'т' \
            else month_name[:-1].lower() + 'я'  # март+а и август+а, но ма[й]+я

    return f"{period.day} {month_name} {period.year}" \
        if with_day else f"{month_name} {period.year}"


def time_from_uuid(uuid) -> datetime:
    """Извлекаем дату и время из идентификатора (UUID v.1)"""
    # 0x01b21dd213814000 is the number of 100-ns intervals between the
    # UUID epoch 1582-10-15 00:00:00 and the Unix epoch 1970-01-01 00:00:00
    return datetime.fromtimestamp(
        (UUID(uuid).time - 0x01b21dd213814000) * 100
        / 1e9)


def get_guid() -> UUID:
    """Новый уникальный идентификатор v.1 (содержит метку времени создания)"""
    return uuid1()


def get_uuid_from(seed: str) -> UUID:

    coder = md5()  # хэширующая функция
    coder.update(seed.encode('utf-8'))  # обновляем "соль"

    return UUID(coder.hexdigest())


def as_object_id(object_id: str) -> ObjectId:
    """
    Получить идентификатор объекта в MongoDB из строки

    WARN ObjectId(None) создает идентификатор на основе (текущих) даты и времени
    """
    return ObjectId(object_id)


def as_guid(uuid: str) -> Optional[UUID]:
    """Преобразовать строку в уникальный идентификатор (UUID)"""
    if not uuid:
        return None
    elif isinstance(uuid, UUID):
        return uuid

    try:
        return UUID(uuid)  # преобразуем в GUID
    except (ValueError, TypeError):
        return None  # TODO error?


def get_random(maximum: int, minimum: int = 0):

    return minimum + random() * (maximum - minimum)


def pct_of(have, must) -> int:
    """Доля (процент) первого от второго"""
    if not have:  # None, 0 или пустая коллекция
        return 0
    elif hasattr(have, '__len__'):
        have: int = len(have)

    if not must:  # None, 0 или пустая коллекция
        return 100
    elif hasattr(must, '__len__'):
        must: int = len(must)

    return int(have / must * 100)


def split_list(array, limit: int = 100) -> list:
    """Разделить массив на несколько частей и вернуть как список списков"""
    if not isinstance(array, (list, tuple)):  # не список или кортеж?
        array: list = [*array]  # преобразуем в список

    return [array[i:i+limit] for i in range(0, len(array), limit)]


def merge(items: list, name: str):
    """Объединить вложенные списки с именем атрибута или ключом словаря"""
    return sum([iter_item.get(name, []) if isinstance(iter_item, dict)
        else getattr(iter_item, name, []) for iter_item in items], [])


def concat(*array_s: Iterable) -> list:
    """
    Собрать элементы вложенных массивов в общий список

    [1,2,3], [4,5,6] -> [1,2,3,4,5,6]
    """
    assert len(array_s) > 1, "Требуется более одного массива для объединения"
    return [item for items in array_s for item in items]


def deep_update(base: dict, update: dict):
    """Рекурсивное обновление словаря"""
    assert isinstance(base, dict) and isinstance(update, dict), \
        "Некорректные данные для рекурсивного обновления словаря"

    for key, value in update.items():
        base_value = base.get(key)

        if isinstance(value, dict):
            if isinstance(base_value, dict):  # обновляем словарь?
                deep_update(base_value, value)
            else:  # заменяем НЕ словарь - словарем!
                base[key] = value.copy()  # копия словаря (НЕ ссылка)
        elif isinstance(value, list) and isinstance(base_value, list):
            base[key] = base_value + value  # append
        else:
            base[key] = value

    return base  # возвращаем обновленный словарь (передан по ссылке)


def ahead_iter(iterable) -> tuple:
    """
    Получить элементы множества по одному с признаком последнего

    :returns: (item, last?), last = True - последний элемент
    """
    iterator = iter(iterable)
    last = next(iterator)  # получаем первое значение

    for current in iterator:  # начиная со второго значения
        yield last, False  # возвращаем предыдущее (не последнее) значение
        last = current  # запоминаем текущее значение

    yield last, True  # возвращаем последнее значение множества


def aggregate(items, foo=lambda x: x, pre=lambda x: x is not None) -> list:
    """
    Получить список прошедших проверку результатов выполнения функции

    :param items: массив данных
    :param foo: функция изменения элементов массива
    :param pre: предикат отбора элементов массива
    """
    results: list = []

    for item in items:  # : iterable
        result = foo(item)  # по умолчанию без изменений

        if pre(result):  # результат проходит проверку?
            results.append(result)

    return results


def _reverse_d(strict: dict) -> dict:
    """
    Вывернутый наизнанку словарь
    """
    _reversed: dict = {}

    for key, value in strict.items():
        _reversed.setdefault(str(value), []).append(key)

    return _reversed  # value: [ key,... ]


def json(obj, indent: int = 4) -> str:
    """Форматированное (строковое) представление (данных) объекта"""
    from json import dumps

    return dumps(
        obj,
        indent=indent,
        default=str,  # конвертер по умолчанию
        sort_keys=False
    )


def sb(text: str, none: str = '') -> str:
    """
    Фигурные кавычки (елочки) вокруг текста
    """
    if text is None:  # значение отсутствует (не пустая строка)?
        return none  # подменяем

    if not text.startswith('«'):
        text = f"«{text}"
    if not text.endswith('»'):
        text = f"{text}»"

    return text


def dt_from(iso_date: str) -> Optional[datetime]:

    # MongoDB.ISODate("2021-09-30T14:39:24.896000")
    DATE_TIME_TEMPLATES: list = [
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%fZ',
    ]

    if not iso_date:
        return None
    elif isinstance(iso_date, datetime):
        return iso_date

    for template in DATE_TIME_TEMPLATES:
        try:
            result = datetime.strptime(iso_date, template)
        except ValueError:
            continue
        else:
            return result

    raise ValueError(f"Не удалось преобразовать в дату {iso_date}")


def jn(iterable: Iterable, delimiter: str = '\n\t', separator: str = ': ',
        empty: str = 'ОТСУТСТВУЮТ') -> str:
    """Объединить данные в строку с разделителем"""
    if isinstance(iterable, Mapping):
        return delimiter.join(f"{key}{separator}{value}"
            for key, value in iterable.items()) or empty

    return delimiter.join(iterable) or empty


def sp(iterable, separator: str = '\n\t', delimiter: str = ', ',
        empty: str = 'ОТСУТСТВУЮТ') -> str:
    """Строковое представление набора элементов"""
    MAX_LINE_WIDTH: int = 120  # максимальная длина строки

    line: str = ''
    lines: list = []

    for item in iterable:
        word: str = str(item)  # repr?

        if not line:
            line = word
        elif len(line) + len(delimiter) + len(word) > MAX_LINE_WIDTH:
            lines.append(line)
            line = word
        else:
            line += delimiter + word

    lines.append(line)  # последний элемент

    return separator + (separator.join(lines) or empty)


def pr(data) -> None:
    """Красивый (форматированный) вывод в консоль (stdout)"""
    data_type: str = type(data).__name__

    stdout.write(f"{data_type}: ")

    from typing_extensions import OrderedDict
    if isinstance(data, OrderedDict):
        data = dict(data)

    pprint(data, stream=stdout,
        indent=1, width=240, compact=True)  # compact - в строку


def pf(subject) -> str:
    """Представление документа в виде строк(и)"""
    return pformat(subject,
        indent=1, width=240, compact=True)  # compact - в строку


def reset_logging():
    """Сбросить параметры базового (root) журнала"""
    from logging import basicConfig, NOTSET

    basicConfig(
        # format='%(message)s',
        level=NOTSET,  # рекомендуется NOTSET
        stream=stdout,  # по умолчанию (красный) stderr
    )


def is_ascii(string: str) -> bool:
    """Строка содержит только символы ASCII?"""
    return all(ord(char) < 128 for char in string)  # WARN 0-127 ~ UTF-8


def is_latin1(string: str) -> bool:
    """Строка содержит только символы Latin-1 (ISO 8859-1)?"""
    return all(ord(char) < 256 for char in string)  # WARN 0-255 ~ UTF-8
