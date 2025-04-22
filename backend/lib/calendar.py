import csv
from datetime import datetime
from functools import lru_cache

import requests
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta

from lib.helpfull_tools import DateHelpFulls as dhf
from processing.models.billing.calendar_document import Calendar
from processing.models.logging.calendar import CalendarDownloadingLog
from settings import GOV_ACCOUNT


class CalendarError(Exception):
    pass


_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) ' \
              'AppleWebKit/537.36 (KHTML, like Gecko) ' \
              'Chrome/106.0.0.0 ' \
              'YaBrowser/22.11.3.838 ' \
              'Yowser/2.5 Safari/537.36'
_DEFAULT_HEADERS = {
    'Content-Type': 'application/json; charset=utf-8',
    'User-Agent': _USER_AGENT,
}

def smart_delta(date: datetime, operation: str, days: int):
    """
    Умное вычитание/сложение дней с учетом выходных и праздников.
    То есть учитывая только рабочие календарные дни.
    :param date: дата
    :param operation: операция (+, -)
    :param days: количество дней, которое нужно отнять или прибавить
    """
    if operation not in {'+', '-'}:
        raise ValueError('Операция должна быть задана: "+" или "-"!')

    # Проверим, переход года и учтем это
    years = tuple({
        date.year,
        (
            date + relativedelta(months=days % 30 + 1)
            if operation == '+'
            else date - relativedelta(months=days % 30 + 1)
        ).year
    })
    # Подгрузим календари нужных годов
    calendar = _get_calendar_by_years(years)
    if not calendar:
        raise CalendarError(f'Не найдены календари за {years}')

    # Теперь сама операция
    while days != 0:
        if operation == '+':
            date = date + relativedelta(days=1)
        else:
            date = date - relativedelta(days=1)
        # Убедимся, что не попали в праздник
        holidays = calendar[date.year][str(date.month)]['holidays']
        # И если так, то делакем еще вычитание, не трогая счетчик
        if str(date.day) in holidays:
            continue
        days -= 1

    return date


def get_working_calendar(year: int = datetime.now().year):
    """ Получение происзодственного календаря с гос. услуг """

    log = CalendarDownloadingLog(year=year, state='wip')
    log.save()

    try:
        # Получение общих сведений о запрашиваемом раздле календаря
        calendar_info = _get_data('/7708660670-proizvcalendar/')
        # Получение каких то версий, необходимо для дальнейших запросов
        # (берем последнюю)
        versions = _get_data('/7708660670-proizvcalendar/version/')
        last_ver = max(
            {x['created'] for x in versions},
            key=lambda x: parse(x)
        )
        _add_log(log, 'Последняя версия обнаружена')
        # Получение каких-то коммитов по работке с календарем среди которых
        # есть ссылки файлы
        """ Этот метод больше не работает, придется напрямую передавать
        имя файла. Зато они сделали json 
        https://data.gov.ru/api/json/dataset/7708660670-proizvcalendar/version/20191112T155500/content/?access_token=
        если вдруг захочется переписать парсер.
        
        commits = _get_data('/7708660670-proizvcalendar/version/' + last_ver)
        # Возьмем самое последнее изменение
        last_commit = max(commits, key=lambda x: parse(x['updated']))
        calendar_csv = requests.get(last_commit['source']).content
        """
        calendar_csv = requests.get(
            _make_url('/7708660670-proizvcalendar/', csv_file=True),
            headers=_DEFAULT_HEADERS,
        ).content
        _add_log(log, 'Календарь скачан из коммита в виде .csv')
        calendar = _read_csv(calendar_csv.decode(), year)
        if not calendar:
            raise CalendarError('Не удалось распарсить файл. Он пустой!')

        _add_log(log, 'Парсинг успешно завершен', 'ready')
        return dict(calendar=calendar, description=calendar_info['description'])

    except Exception as error:
        _add_log(log, str(error), 'failed')
        raise error


@lru_cache()  # Для кэширования результата, чтоб не дрючить базу
def _get_calendar_by_years(years):
    fld = 'year', 'map'
    calendar = {
        x['year']: x['map']
        for x in Calendar.objects(year__in=years).only(*fld).as_pymongo()
    }
    return calendar


def _make_url(section_url, csv_file=False):
    token = f'?access_token={GOV_ACCOUNT["token"]}'
    if csv_file:
        base_url = 'https://data.gov.ru/opendata'
        return base_url + section_url + \
               f'{GOV_ACCOUNT["csv_file"]}?' \
               f'encoding={GOV_ACCOUNT["encoding"]}&' \
               f'access_token={GOV_ACCOUNT["token"]}'
    base_url = 'https://data.gov.ru/api/json/dataset'
    return base_url + section_url + token


def _get_data(url):
    response = requests.get(
        _make_url(url),
        headers=_DEFAULT_HEADERS,
    )
    return response.json()


def _read_csv(csv_file: str, year: int):
    fl = tuple(csv.reader(csv_file, delimiter=',', quotechar='"'))
    # Надем текущий год и создадим массив данных
    # TODO Дебильнее парсинга не придумаешь, но я не смог разобраться почему
    #  считывание идет не очень хорошим образом
    # Пересборка удобный вид
    for num, row in enumerate(fl):
        # Это означает конец строки
        if (fl[num - 1], fl[num - 2]) == ([], []):
            # Узнаем год - это 4 списка, идущих подряд и в которых по 1 цифре
            row_year = int(
                f'{row[0]}{fl[num + 1][0]}{fl[num + 2][0]}{fl[num + 3][0]}'
            )
            # Если искомый год совпал,
            # получим все выходные дни для каждого месяца, кроме звездочных
            if row_year == year:
                # Срез выходных помесячно
                # (не забываем идти через 1 значение,
                # потому что там списки с запятми)
                holidays_map = fl[num + 5:num + 29:2]
                # Соберем словарь, исключая дни,
                # помеченные звездочкой (короткие)
                return {
                    str(num): dict(
                        name=dhf.MONTHS_NAMES[num],
                        holidays=tuple(
                            x.strip('+')
                            for x in x[0].split(',')
                            if '*' not in x
                        )
                    )
                    for num, x in enumerate(holidays_map, start=1)
                }


def _add_log(model, msg, state=None):
    model.log.append(str(msg))
    if state:
        model.state = state
    model.save()
