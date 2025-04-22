""" Набор полезных функций, классов, методов """
import itertools
import sys
import traceback
from typing import List
import string
from dateutil.relativedelta import relativedelta
from jinja2 import Environment, FileSystemLoader


class DateHelpFulls:
    """
    Полезности для работы с датой и временем
    """
    MONTHS_NAMES = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    @staticmethod
    def pretty_date_converter(date, with_day=False, genitive=False):
        """
        Получает строчку день и месяц из даты
        :param date: datetime object: дата
        :param with_day: bool: указывать день в возвращаемой дате
        :param genitive: bool: Делает месяц в родительном падеже
        :return: str: день и месяц
        """
        months = DateHelpFulls.MONTHS_NAMES
        day = date.strftime("%d")
        month = months.get(int(date.strftime("%m")))
        year = date.strftime("%Y")
        if genitive:
            if month[-1].lower() == 'т':
                month = month + 'а'
            else:
                month = month[:-1] + 'я'
        if with_day:
            return "{} {} {}".format(day, month, year)
        else:
            return "{} {}".format(month, year)

    @staticmethod
    def end_of_month(date):
        """
        Возвращает самый конец месяца переданной даты.
        Например: 2018-03-01 00:00:00 --> 2018-03-31 23:59:59.999999
        :param date: datetime obj
        :return: datetime obj
        """
        return (DateHelpFulls.begin_of_month(date)
                + relativedelta(months=1)
                - relativedelta(microseconds=1))

    @staticmethod
    def begin_of_month(date):
        """
        Возвращает самое начало месяца переданной даты.
        Например: 2018-03-01 04:07:06 --> 2018-01-1 00:00:00
        :param date: datetime obj
        :return: datetime obj
        """
        return date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def end_of_day(date):
        """
        Возвращает самый конец дня переданной даты.
        Например: 2018-03-01 04:07:06 --> 2018-03-01 23:59:59.999999
        :param date: datetime obj
        :return: datetime obj
        """
        return date.replace(hour=23, minute=59, second=59, microsecond=999999)

    @staticmethod
    def start_of_day(date):
        """
        Возвращает самое начало дня переданной даты.
        Например: 2018-03-01 04:07:06 --> 2018-03-01 00:00:00
        :param date: datetime obj
        :return: datetime obj
        """
        return date.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def start_of_year(date):
        """
        Возвращает начало года переданной даты.
        Например: 2018-03-01 04:07:06 --> 2018-01-01 00:00:00
        :param date: datetime obj
        :return: datetime obj
        """
        return date.replace(month=1, day=1, hour=0,
                            minute=0, second=0, microsecond=0)

    @staticmethod
    def get_days_from_period(period):
        """
        Получение списка дат (дней) из переданного диапазона дат
        :param period: [datetime, datetime]
        :return:
        """
        days = {
            day
            for day in [
                min(period[0], period[-1]) + relativedelta(days=x)
                for x in range(abs((period[-1] - period[0]).days) + 1)
            ]
        }
        return days

    @staticmethod
    def get_hours_from_period(period):
        """
        Получение списка дат (часов) из переданного диапазона дат
        :param period: [datetime, datetime]
        :return:
        """
        days = {
            day
            for day in [
                min(period[0], period[-1]) + relativedelta(hours=x)
                for x in range(abs((period[-1] - period[0]).days) * 24)
            ]
        }
        return days


def by_mongo_path(dict_obj: dict, query_key_text: str, default=None) -> dict:
    """
    Преобразует путь к полю в БД к запросу в словарь
    :param dict_obj: dict: словарь для которого нужно получить значение
    :param query_key_text: str: поле из БД вида 'area.house.address'
                                            или 'area.house.[5].address',
                                            если нужно взять объект из списка
                                            по индексу
    :param default: то, чт овернется по умолчанию
    :return: значение словаря, например: dict_obj[area][house][address]
             или dict_obj[area][2][address] (где 2 - индекс списка)
    """
    query_key_text = query_key_text.split('.')
    for key in query_key_text:
        try:
            if all([key.startswith('['), key.endswith(']')]):
                key = int(key[1:-1]) if key[1:-1].isdigit() else key
                dict_obj = dict_obj[key]
                continue
            dict_obj = dict_obj[key]
        except (AttributeError, IndexError, KeyError, TypeError):
            return default
    return dict_obj


def separate_list_on_parts(list_: list, parts_num: int) -> list:
    """
    Делит список на равные части (последняя может быть больше/меньше)
    :param list_: исходный список элементов
    :param parts_num: на сколько поделить
    :return: список списков
    """
    part_length = len(list_) // parts_num
    return [
        (
            list_[part * part_length:(part + 1) * part_length]
            if part + 1 < parts_num
            else list_[part * part_length:]
        )
        for part in range(parts_num)
    ]


def list_zip_sum(list_of_lists: (list, tuple)) -> list:
    """
    Складывает элементы вложенных списков, переданного списка,
    в соответсвии с их порядковым номером
    и возвращает список с суммой по каждому порядковому номеру.
    Пример:
        list_of_lists = [[0, 0, 10], [85, 5, 5], [-5, 0, 10]]
        result = [80, 5, 25]
    :param list_of_lists:
    :return: list
    """
    return list(map(lambda *args: sum(args), *list_of_lists))


def exel_column_letter_generator(start_from: str = None):
    """
    Генерация списка букв колонок в Exel
    :param start_from: str - буква с которой начнется формирование списка
    :return: list - список из диапазона букв
    """
    alphabet = list(string.ascii_uppercase)
    alphabet.extend(
        [f'{x[0]}{x[1]}' for x in itertools.product(alphabet, repeat=2)]
    )
    # Выбираем с какой буквы начать
    start_from = alphabet.index(start_from) if start_from in alphabet else None
    if start_from is not None:
        return alphabet[start_from:]
    else:
        return alphabet


def exception_detail_info(msg: str = ''):
    """
    Возвращает более детальную информацию об ошибке в блоке,
    в который интегрирована эта функция
    :param msg: сообщение, которое необходимо добавить
    :return: детали об ошибке и строка в которой она произошла
    """

    error_info = sys.exc_info()
    if error_info[2]:
        tb = traceback.extract_tb(sys.exc_info()[2])[-1]
        detail_info = (
            f"line №{tb.lineno}: {tb.line}; func_name: {tb.name}; msg: {msg}"
        )
        return detail_info
    return ''


def get_mail_templates(names: List[str], template_path: str = '') -> list:
    """
    Загрузка шаблонов для писем из имеющихся у Jinja
    :param names: список полных имен шаблонов
    :param template_path: путь к шаблонам
    :return загруженные шаблоны
    """
    if not template_path:
        template_path = './templates/jinja/mail'
    # Загрузка окружения для их наследования
    env = Environment(loader=FileSystemLoader(template_path))
    templates = [env.get_template(template_name) for template_name in names]
    return templates


def divide_and_conquer(array, count):
    """
    :param array: передаваемый список
    :param count: колличечество элементов в дробленном списке
    :return: раздбробелнный список списков по равным частям (кроме возможно
    последнего)
    """
    return [array[i:i+count] for i in range(0, len(array), count)]
