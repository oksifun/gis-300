from datetime import datetime, date
from math import ceil
from copy import deepcopy
from io import BytesIO
import xlsxwriter as xls
from dateutil.relativedelta import relativedelta

from app.celery_admin.workers.config import celery_app
from app.requests.models.choices import RequestStatus
from app.requests.models.request import Request, RequestLogs
from app.messages.core.email.extended_mail import RegularMail
from processing.models.billing.provider.main import Provider
from settings import CELERY_SOFT_TIME_MODIFIER, SUPPORT_MAIL

bytes_object = BytesIO()
TIME_LIFE_LOG = relativedelta(months=1)
DATE_MIN_APPLICATION = relativedelta(days=60)
DATE_MAX_APPLICATION = relativedelta(days=5)
STATUS_ON = True


@celery_app.task(
    soft_time_limit=60 * 120 * CELERY_SOFT_TIME_MODIFIER,
)
def excel_report_requests() -> str:
    """
    Функция для отправки письма с отчетом в файле Excel.
    В данной конфигурации создается отчет с автоматическим определением
    количества строк и страниц. Файл сохраняется в буфере после отправляется
    получателю. В случае если отчет оказывается пустым, отправляется письмо
    без вложения с уведомление, что отчет пуст.

    Для тестирования необходимо:
        Поменять адрес доставки писем в send_ready_full_report,
        send_empty_report. И поменять метод поиска в overdue_applications.
        И вызвать как функцию.
    """
    # Чистим старые логи.
    clear_logs()

    # Отключение функционала. Если необходимо.
    if STATUS_ON is False:
        return 'Functionality disabled'

    # Получаем все заявки из логов.
    applications_in_logs = RequestLogs.objects(
        status=True
    ).only(
        'request_id'
    ).as_pymongo()
    logs_id = [i.get('request_id') for i in applications_in_logs]

    # Получение всех необработанных заявок которых нет в логах.
    overdue_applications = Request.objects(
        id__nin=logs_id,
        common_status=RequestStatus.ACCEPTED,
        created_at__gte=date.today() - DATE_MIN_APPLICATION,
        created_at__lte=date.today() - DATE_MAX_APPLICATION,
        is_deleted__ne=True,
    ).only(
        'number',
        'house__address',
        '_type',
        'provider',
        'body'
    ).as_pymongo()

    # Если не найдено "неотработанных" заявок.
    if not overdue_applications:
        return send_empty_report()

    # Создаем файл, стили, определяем кол-во столбцов и нужное кол-во страниц.
    file = create_new_file_xlsx()
    style = create_cell_format(file)
    len_data = len(overdue_applications)
    max_column = maximum_number_of_page_columns(amount_data=len_data)
    number_of_page = ceil(len_data / max_column)
    worksheets = create_new_worksheets(file=file, needs_pages=number_of_page)

    # Заполняем и форматируем все страницы.
    for page in worksheets:
        cells_formating(worksheet=page, style=style, columns=max_column)
        create_header(worksheet=page, style=style)

    # Получаем данные в "удобном" виде.
    new_data = data_reassembly(
        pages=worksheets,
        data=overdue_applications,
        max_column=max_column,
        last_column=len_data
    )

    # Если нет данных.
    if not new_data:
        return send_empty_report()

    # Заполняем страницы данными.
    for data in new_data:
        # Если доходим до словаря "Данные для отправки", то инициируем отправку.
        data_send = data.get('Data_to_send')
        if data_send:
            # Закрываем и сохраняем файл.
            close_new_file_xlsx(file)
            # Отправляем документ.
            return send_ready_full_report(
                number_of_objects=len_data, providers=data_send)
        for page, da in data.items():
            for count, i in enumerate(da):
                page.write_row(row=(count + 1), col=0, data=i)


def data_reassembly(
        pages: list,
        data: list,
        max_column: int,
        last_column: int) -> list:
    """
    Форматирование данных для дальнейшего разложения по страницам.
    Данные собираются по страницам. У страниц есть максимальное количество
    колонок с данными. Когда собрался массив, который равняется максимальному
    количеству колонок, страница переворачивается и собирается следующая.

    :param pages: Список со страницами. Экземпляр класса Worksheet.
    :param data: Список с заявками. Вида: list(dict(), dict()).
    :param max_column: Максимальное количество столбцов с данными на странице.
    :param last_column: Последняя строка. Необходимо для последней страницы.

    :returns: Данные вида: list(
            dict(страница_1: list(list(заявка_1), list(заявка_2), ....),
            dict(страница_2: list(list(заявка_n), list(заявка_n), ....),
            dict(страница_3: list(list(заявка_n), list(заявка_n), ....),
            .....
            dict(Data_to_send={Провайдер: кол-во заявок}).
        ).
    :raises Exception: Исключение ряда/объекта. Если возникает, то
    ряд/объект пропускается.
    """
    # Готовый отчет.
    ready_full_report = []
    # Готовая страница.
    ready_page = []
    # Текущая страница.
    number_page = 0
    for count, application in enumerate(data):
        try:
            number_record = count + 1
            application_id = application.get('number', 'Не найдена')
            house = application['house'].get('address', 'Не найден')
            application_description = application.get('body')
            provider_name = \
                application['provider'].get('str_name', 'Провайдер не указан')

            application_type = None
            if len(application['_type']) == 0:
                application_type = 'Не опознана'

            elif application['_type'][0] == 'AreaRequest':
                application_type = 'Квартирная заявка'

            elif application['_type'][0] == 'HouseRequest':
                application_type = 'Общедомовая заявка'

        # Обработчик исключений при сборке ряда/объекта.
        except Exception as error:
            RequestLogs(
                request_id=application.get('_id'),
                status=False,
                description=f'Exception: {type(error)} => {error}'
            ).save()
            continue

        else:
            # Готовая строка.
            ready_page.append(
                [
                    number_record,
                    application_id,
                    application_type,
                    provider_name,
                    house,
                    application_description
                ]
            )

            # Записываем 'удачный' лог.
            RequestLogs(
                request_id=application.get('_id'),
                status=True,
                description='Successfully'
            ).save()

            # Новая страница.
            if number_record % max_column == 0 or \
                    number_record == last_column:
                page = pages[number_page]
                array_data = deepcopy(ready_page)
                ready_full_report.append({page: array_data})
                number_page += 1
                ready_page.clear()

    # Добавляем к списку с данными словарь с провайдером и количеством заявок.
    ready_full_report.append(get_providers_and_number_of_applications(
        data=data,
        string=True,
    ))
    return ready_full_report


def get_providers_and_number_of_applications(
        data: list, string: bool = False) -> dict or str:
    """
    Уникальный список провайдеров и кол-во заявок этого провайдера.

    :param data: Список с заявками. Вида: dict(Dict_mail=dict(), dict()).
    :param string: Какой объект нужен на выходе. Для писем, чтобы были переносы
    после каждого объекта необходим тег <br>.

    :returns:
    Если string = False -> dict(Data_to_send=dict(Провайдер: кол-во заявок)).
    Если string = True -> dict(Data_to_send=str(Провайдер: кол-во заявок <br>)).
    """
    providers_applications = dict()
    if string is True:
        providers_applications = ''
    providers_id_list = list(i['provider']['_id'] for i in data)
    providers_id_set = set(deepcopy(providers_id_list))

    for provider_id in providers_id_set:
        provider_object = Provider.objects(
            id=provider_id
        ).only(
            'str_name'
        ).as_pymongo()
        provider_name = provider_object[0].get('str_name', 'УК не опознана')
        amount = providers_id_list.count(provider_id)
        if isinstance(providers_applications, dict):
            providers_applications.update({provider_name: amount})
        elif isinstance(providers_applications, str):
            providers_applications += f"{provider_name}: {amount}, <br>"
    return dict(Data_to_send=providers_applications)


def send_ready_full_report(number_of_objects: int, providers: list) -> str:
    """
    Отправка готового отчета с вложением.

    :param number_of_objects: Количество необработанных заявок.
    :param providers: Список организаций у полученных заявок.
    :returns: Статус об отправке письма с отчетом. И кол-во объектов в отчете.
    """
    date_now = datetime.now()
    attachment = dict(
        name=f'Отчет по не обработанным заявкам за {date_now.date()}.xlsx',
        bytes=bytes_object.getvalue(),
        type='doc',
        subtype='xlsx'
    )
    ready_report_mail_params = dict(
        addresses=SUPPORT_MAIL,
        subject='Отчет по наличию необработанных новых заявок',
        body=f'Готовый отчет во вложении. <br>'
             f'Организации у которых есть необработанные заявки:<br>'
             f'{providers}',
        # Параметры.
        instantly=True,
        remove_after_send=True
    )
    letter = RegularMail(attachments=[attachment], **ready_report_mail_params)
    letter.send()
    return f'Report send. Number of objects = {number_of_objects}.'


def send_empty_report() -> str:
    """
    Если отчет пустой. Отправляем письмо где указываем что
    нет просроченных заявок.

    :returns: Статус об отправке пустого письма.
    """
    empty_report_mail_params = dict(
        addresses=SUPPORT_MAIL,
        subject='Отчет по наличию необработанных новых заявок',
        body=f'На момент формирования отчета новых заявок нет.',
        # Параметры.
        instantly=True,
        remove_after_send=True,
    )
    letter = RegularMail(**empty_report_mail_params)
    letter.send()
    return "Empty email send."


def create_new_file_xlsx(
        file_name: str = 'Report.xlsx',
        create_in_memory: bool = True) -> xls.Workbook:
    """
    Создание файла Excel. Для отправки необходимо создавать в памяти.
    Если необходим сам файл, то необходимо указать create_in_memory == False и
    присвоить имя файлу file_name.

    :param file_name: Название файла. По умолчанию Report.xlsx.
    :param create_in_memory: True-Создание в памяти. False-Будет создан файл.
    :returns: Файл. Экземпляр класса Workbook.
    """
    if create_in_memory:
        return xls.Workbook(bytes_object, options={'in_memory': True})
    else:
        return xls.Workbook(filename=file_name)


def clear_logs() -> int:
    """
    Очистка логов дата создания которых <= месяца.

    :returns: Количество удаленных объектов.
    """
    return RequestLogs.objects(
        created__lte=date.today() - TIME_LIFE_LOG
    ).delete()


def create_cell_format(file: xls.Workbook) -> dict:
    """
    Создание стилей для ячеек.

    :param file: Файл. Экземпляр класса Workbook.
    :returns: Словарь с экземплярами класса Worksheet.
    """

    alignment = file.add_format()
    alignment.set_align('center')

    return dict(
        ali_centre=alignment
    )


def create_new_worksheets(file: xls.Workbook, needs_pages: int = 1) -> list:
    """
    Создание страниц в файле Excel.

    :param file: Файл. Экземпляр класса Workbook.
    :param needs_pages: Нужное количество страниц. По умолчанию одна страница.
    :returns: Список страниц. Экземпляры класса Worksheet.
    """
    pages = []
    for number_page in range(needs_pages):
        page = file.add_worksheet(name=f'Страница {number_page + 1}')
        pages.append(page)
    return pages


def maximum_number_of_page_columns(amount_data: int) -> int:
    """
    Автоматическое определение количество столбцов данных на странице.

    :param amount_data: Общее количество заявок.
    :returns: Количество столбцов с данными на одной странице.
    """
    if 0 <= amount_data <= 100:
        return 25
    elif 100 <= amount_data <= 250:
        return 50
    elif 250 <= amount_data <= 500:
        return 100
    elif 500 <= amount_data <= 1000:
        return 200
    elif 1000 <= amount_data <= 5000:
        return 500
    elif 5000 <= amount_data <= 10000:
        return 1000
    else:
        return 10000


def cells_formating(
        worksheet: xls.Workbook.worksheet_class,
        style: dict,
        columns: int = 0) -> None:
    """
    Добавляем свойства ячейкам для данных.

    :param worksheet: Страница. Экземпляр класса Worksheet.
    :param style: Стили. Словарь с экземплярами класса Workbook.
    :param columns:  Максимальное количество столбцов с данными на странице.
    """
    worksheet.set_column(first_col=0, last_col=0, width=7, cell_format=None)
    worksheet.set_column(
        first_col=1, last_col=1, width=17, cell_format=style.get('ali_centre'))
    worksheet.set_column(
        first_col=2, last_col=2, width=20, cell_format=style.get('ali_centre'))
    worksheet.set_column(first_col=3, last_col=3, width=35, cell_format=None)
    worksheet.set_column(first_col=4, last_col=4, width=100, cell_format=None)
    worksheet.set_column(first_col=5, last_col=5, width=200, cell_format=None)

    for column in range(columns + 1):
        worksheet.set_row(row=column, height=30)


def create_header(worksheet: xls.Workbook.worksheet_class, style) -> None:
    """
    Заполняем шапку и добавляем свойства ячейкам.

    :param worksheet: Страница. Экземпляр класса Worksheet.
    :param style: Стили. Экземпляр класса Workbook.
    """
    header_row = (
        'П/н', '№ заявки', 'Тип', 'Организация', 'Адрес', 'Описание заявки')
    worksheet.write_row(
        row=0, col=0, data=header_row, cell_format=style.get('ali_centre'))


def close_new_file_xlsx(file: xls.Workbook) -> None:
    """
    Закрытие файла.

    :param file: Файл. Экземпляр класса Workbook.
    """
    return file.close()
