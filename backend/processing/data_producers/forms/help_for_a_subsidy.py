from datetime import datetime
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from app.house.models.house import House
from app.personnel.models.personnel import Worker
from lib.helpfull_tools import DateHelpFulls, by_mongo_path
from processing.data_producers.forms.finance_personal_report import (
    _get_mates, __create_table
)
from processing.models.billing.account import Account
from processing.models.billing.accrual import Accrual
from processing.models.billing.tariff_plan import TariffPlan
from processing.models.document_counter import DocumentCounter


def _get_acc_balance(tenant_id, provider_id, date):
    from processing.data_producers.balance.base import AccountBalance
    balance = AccountBalance(tenant_id, provider_id).get_date_balance(
        date,
        ['rent']
    )
    return balance


def _get_accruals(tenant_id, date_from, date_till):
    """
    Получение данных о начислениях ЖКУ
    по статьям коммунальных и жилищных услуг
    :param: tenant_id: ObjectId
    :return: list: список начисленного по услугам для таблицы
    """
    year_ago = date_from - relativedelta(years=1)
    accruals = None
    while date_from != year_ago:
        accruals = Accrual.objects(__raw__={
            'account._id': tenant_id,
            'sector_code': {'$in': ['rent']},
            'doc.date': {'$gte': DateHelpFulls.begin_of_month(date_from),
                         '$lte': date_till},
            'is_deleted': {'$ne': True},
            # 'month': DateHelpFulls.begin_of_month(date_till)
        }).as_pymongo()
        if accruals:
            break
        else:
            date_from = date_from - relativedelta(months=1)
    if not accruals:
        return

    # Создание словаря тарифных планов
    tariff_plans = TariffPlan.objects(
        id__in=[acr['tariff_plan'] for acr in accruals]
    ).as_pymongo()
    tariffs = {}
    for tariff_plan in tariff_plans:
        for tariff in tariff_plan['tariffs']:
            if str(tariff['group'])[-1] in ('0', '1'):
                tariffs.setdefault(tariff['service_type'], tariff)

    # Суммирование по тарифным планам
    services = []
    for accrual in accruals:
        for service in accrual['services']:
            if service['service_type'] in tariffs:
                services.append({
                    'service_type': service['service_type'],
                    'units': tariffs[service['service_type']]['units'],
                    'norm': tariffs[service['service_type']]['norm'],
                    'title': tariffs[service['service_type']]['title'],
                    'value': service['value'],
                    'privileges': -service['totals']['privileges'],
                    'total': service['value'] + service['totals']['privileges'],
                    'tariff': service['tariff'],
                })
    return services, date_from


def _get_doc_counter(provider_id):
    """Получение счетчика документа (общий порядковый номер)"""
    document = DocumentCounter.objects(
        provider=provider_id, document_name='subsidy')
    # Если документа нет, создаем новый
    if not document:
        dc = DocumentCounter(
            provider=provider_id, document_name='subsidy'
        )
        dc.increase_count()
        dc.save()
        return 1
    else:
        # Верменм счетчик и увеличим значения в базе на 1
        document = document.get()
        counter = document.get_document_count() + 1
        document.increase_count()
        document.save()
        return counter


def get_subsidy(tenant_id, provider, date_from, date_till,
                current_account=None):
    """
    Сбор данных для справки на субсидию
    :param current_account: аккаунт с текущей сессии
    :param date_till: datetime: начала временного диапазона
    :param date_from: datetime: конец временного диапазона
    :param tenant_id: id жителя
    :param provider: QuerySet obj
    :return: dict: словарь данных для отчета
    """
    current_date = datetime.now()
    provider_id = provider.pk
    tenant = Account.objects(id=tenant_id).as_pymongo().get()
    house = House.objects(id=tenant['area']['house']['_id']).as_pymongo().get()
    area = Area.objects(id=tenant['area']['_id']).as_pymongo().get()

    # Вытягиваем должность и имя выдающего справку
    if current_account:
        accountant = dict(current_account.to_mongo())
    else:
        accountant = Worker.objects(
            provider__id=provider_id, position__code='acc1',
            is_dismiss__ne=True,
            is_deleted__ne=True,
        ).only('short_name', 'position.name').as_pymongo().first()

    # Счетчик документа
    doc_counter = _get_doc_counter(provider_id)

    # Задолженности
    account_balance = _get_acc_balance(tenant_id, provider_id, date_till)

    # Начисления по услугам
    accruals = _get_accruals(tenant_id, date_from, date_till)
    if accruals:
        accruals_table, accruals_date = accruals
    else:
        accruals_table = []
        accruals_date = date_till if current_date > date_till else current_date

    # Совместно проживающие
    tenant_mates = _get_mates(date_till, provider_id, area['_id'])
    tenant_mates = [tenant_mates[x] for x in tenant_mates][0]

    data = dict(
        header=dict(
            tenant_name=tenant['str_name'],
            address='{}{}, {}'.format(
                (house.get('zip_code') + ', ') if house.get('zip_code') else '',
                area['house']['address'],
                area['str_number_full']),
            provider=provider.str_name,
            room_count=len([r for r in area['rooms']
                            if r['number'] and r['type'] == 'living']),
            square=area['area_total'],
            registred=tenant_mates['summary']['registered'],
            counter=doc_counter
        ),
        accountant=dict(
            name=accountant.get('short_name'),
            position=by_mongo_path(accountant, 'position.name')
        ),
        balance=account_balance,
        accruals_table=accruals_table,
        date=accruals_date
    )

    return data


def create_subsidy_xlsx(tenant_data):
    # Формирование содержимого файла xlsx отчёта
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    worksheet.fit_to_pages(1, 0)

    # Конфиги стилей данных листа
    font = 'Times New Roman'
    configs = {
        "title": workbook.add_format({'bold': 0,
                                      'font_size': 10,
                                      'valign': 'bottom',
                                      'align': 'right',
                                      'font_name': font
                                      }),
        "title_bold_border": workbook.add_format({'bold': 1,
                                                  'font_size': 10,
                                                  'valign': 'bottom',
                                                  'align': 'right',
                                                  'font_name': font,
                                                  'bottom': 1
                                                  }),
        "title_center": workbook.add_format({'bold': 0,
                                             'font_size': 10,
                                             'valign': 'bottom',
                                             'align': 'center',
                                             'font_name': font
                                             }),
        "normal_left": workbook.add_format({'font_size': 10,
                                            'valign': 'bottom',
                                            'align': 'left',
                                            'font_name': font,
                                            }),
        "normal_right": workbook.add_format({'font_size': 10,
                                             'valign': 'bottom',
                                             'align': 'right',
                                             'font_name': font,
                                             }),
        "normal_center": workbook.add_format({'font_size': 10,
                                              'valign': 'bottom',
                                              'align': 'center',
                                              'font_name': font,
                                              }),

        "table_title_ceil": workbook.add_format({'bold': 1,
                                                 'font_size': 10,
                                                 'text_wrap': True,
                                                 'valign': 'vcenter',
                                                 'align': 'center',
                                                 'font_name': font,
                                                 'border': 1
                                                 }),
        "t_title_right": workbook.add_format({'bold': 1,
                                              'font_size': 10,
                                              'text_wrap': True,
                                              'valign': 'vcenter',
                                              'align': 'right',
                                              'font_name': font,
                                              'border': 1
                                              }),
        "t_title_center": workbook.add_format({'bold': 0,
                                               'font_size': 10,
                                               'text_wrap': True,
                                               'valign': 'vcenter',
                                               'align': 'center',
                                               'font_name': font,
                                               'border': 1
                                               }),
        "t_title_left": workbook.add_format({'font_size': 10,
                                             'text_wrap': True,
                                             'valign': 'vcenter',
                                             'align': 'left',
                                             'font_name': font,
                                             'border': 1
                                             }),
        "table_bold_ceil": workbook.add_format({'bold': 1,
                                                'font_size': 10,
                                                'valign': 'bottom',
                                                'align': 'left',
                                                'font_name': font,
                                                'bottom': 1,
                                                'italic': 1
                                                }),
        "table_bold_ceil_center": workbook.add_format({'bold': 1,
                                                       'font_size': 10,
                                                       'valign': 'vcenter',
                                                       'align': 'center',
                                                       'font_name': font,
                                                       'bottom': 1
                                                       }),
        "table_number": workbook.add_format({'font_size': 10,
                                             'valign': 'vcenter',
                                             'align': 'center',
                                             'font_name': font,
                                             'border': 1,
                                             'num_format': '0.00',
                                             'bold': 0
                                             }),
        "table_number_norm": workbook.add_format({'font_size': 10,
                                                  'valign': 'vcenter',
                                                  'align': 'center',
                                                  'font_name': font,
                                                  'border': 1,
                                                  'num_format': '0.00',
                                                  'bold': 0
                                                  }),

    }

    # Конфиги колонок и рядов
    # Высоты ячеек
    empty_row_height = 7  # пустые строки
    table_ceil_height = 30  # строки таблицы

    # Для рядов
    # сначала для всех
    for row in range(50):
        worksheet.set_row(row, 20)
    # Индивидуально для шапки (она статическая)
    for row in (1, 6, 8):
        worksheet.set_row(row, empty_row_height)
    # индивидуально по строкам
    worksheet.set_row(3, 40)
    worksheet.set_row(9, 40)

    # Для колонок
    # сначала для всех
    worksheet.set_column("B:AZ", 1.6)
    # индивидуально
    worksheet.set_column("A:A", 0.2)

    # Шапка
    header = tenant_data['header']
    head_data = (
        ('M1:Z1', "Справка на субсидию № ", configs["title"]),
        ('AA1:AJ1', header['counter'], configs["table_bold_ceil_center"]),
        ('B3:D3', "Дана:", configs["normal_left"]),
        ('E3:AN3', header['tenant_name'], configs["table_bold_ceil"]),
        ('AO3:AQ3', "(фио),", configs["normal_left"]),
        ('B4:O4', "проживающему(ей) по адресу:", configs["normal_left"]),
        ('P4:AP4', header['address'], configs["table_bold_ceil"]),
        ('B5:J5', "Управляющая компания:", configs["normal_left"]),
        ('K5:AP5', header['provider'], configs["table_bold_ceil"]),
        ('B6:H6', "Количество комнат:", configs["normal_left"]),
        ('I6:K6', header['room_count'], configs["table_bold_ceil_center"]),
        ('M6:R6', "Общая площадь:", configs["normal_left"]),
        ('S6:U6', header['square'], configs["table_bold_ceil_center"]),
        ('W6:AI6', "Количество зарегистрированных:", configs["normal_left"]),
        ('AJ6:AL6', header['registred'], configs["table_bold_ceil_center"]),
        ('B8:AR8', "ЖКУ за {}".format(
            DateHelpFulls.pretty_date_converter(tenant_data['date'])),
         configs["title_center"]),
    )
    __create_table(head_data, worksheet)

    # проставить точки, запяточки в шапке
    head_dots = (
        ('AQ4', ",", configs["normal_left"]),
        ('AQ5', ",", configs["normal_left"]),
        ('L6', ".", configs["normal_left"]),
        ('V6', ".", configs["normal_left"]),
        ('AM6', ".", configs["normal_left"]),
    )
    for coordinate, data, config in head_dots:
        worksheet.write(coordinate, data, config)

    # Таблица
    # Заголовки столбцов
    table_titles = (
        ('B10:K10', "УСЛУГА", configs["table_title_ceil"]),
        ('L10:O10', "ЕД.ИЗМ.", configs["table_title_ceil"]),
        ('P10:S10', "ТАРИФ", configs["table_title_ceil"]),
        ('T10:Y10', "НОРМА ПОТРЕБЛЕНИЯ", configs["table_title_ceil"]),
        ('Z10:AE10', "НАЧИСЛЕНИЕ", configs["table_title_ceil"]),
        ('AF10:AJ10', "СУММА ЛЬГОТ", configs["table_title_ceil"]),
        ('AK10:AP10', "ИТОГО", configs["table_title_ceil"]),
    )
    __create_table(table_titles, worksheet)

    # Данные таблицы
    t_st = 10
    service_data = tenant_data['accruals_table']
    t_c_n = configs["table_number"]  # Для числовых ячеек таблицы
    # Аккумуляторы для "Итого"
    total_value = 0
    total_privileges = 0
    total_all = 0
    # Только если есть начисления
    if service_data:
        for service in service_data:
            worksheet.set_row(t_st, table_ceil_height)  # ширина яч.
            t_st += 1
            # Суммируем
            total_value += service['value']
            total_privileges += service['privileges']
            total_all += service['total']
            service_table = (
                # Услуга
                ('B{r}:K{r}'.format(r=t_st),
                 service['title'], configs["t_title_left"]),
                # Ед. изм.
                ('L{r}:O{r}'.format(r=t_st),
                 service['units'], configs["t_title_center"]),
                # Тариф
                ('P{r}:S{r}'.format(r=t_st),
                 round(service['tariff'] / 100, 2) or '', t_c_n),
                # Норма потребления
                ('T{r}:Y{r}'.format(r=t_st),
                 service['norm'] or '', configs['table_number_norm']),
                # Начисления
                ('Z{r}:AE{r}'.format(r=t_st),
                 round(service['value'] / 100, 2) or '', t_c_n),
                # Сумма льгот
                ('AF{r}:AJ{r}'.format(r=t_st),
                 round(service['privileges'] / 100, 2) or '', t_c_n),
                # Итого
                ('AK{r}:AP{r}'.format(r=t_st),
                 round(service['total'] / 100, 2) or '', t_c_n),
            )
            __create_table(service_table, worksheet)

    # Итого по таблице
    worksheet.set_row(t_st, table_ceil_height)  # ширина ячейки
    t_st += 1
    final = (
        ('B{r}:Y{r}'.format(r=t_st), 'ИТОГО: ', configs['t_title_right']),
        ('Z{r}:AE{r}'.format(r=t_st), round(total_value / 100, 2) or '', t_c_n),
        ('AF{r}:AJ{r}'.format(r=t_st),
         round(total_privileges / 100, 2) or '', t_c_n),
        ('AK{r}:AP{r}'.format(r=t_st), round(total_all / 100, 2), t_c_n) or '',
    )
    __create_table(final, worksheet)

    # Подвал
    worksheet.set_row(t_st, empty_row_height)  # ширина ячейки
    t_st += 2
    # Состояние баланса
    balance = tenant_data['balance']
    balance_text = "Задолженность за ЖКУ на"
    # Если сальдо больше 0
    if balance > 0:
        balance_state = '{debt} руб.'.format(
            debt=round(balance / 100, 2)
        )
    else:
        balance_state = 'Отсутствует'

    foter_data = (
        ('B{r}:L{r}'.format(r=t_st), balance_text,
         configs["normal_left"]),
        ('N{r}:V{r}'.format(r=t_st),
         DateHelpFulls.pretty_date_converter(
             datetime.now(), with_day=True, genitive=True),
         configs["table_bold_ceil_center"]),
        ('X{r}:AQ{r}'.format(r=t_st), balance_state,
         configs["table_bold_ceil_center"]),

        ('K{r}:Q{r}'.format(r=t_st + 2), tenant_data['accountant']['position'],
         configs["normal_left"]),
        ('R{r}:AB{r}'.format(r=t_st + 2), "", configs["table_bold_ceil"]),
        ('AD{r}:AQ{r}'.format(r=t_st + 2), tenant_data['accountant']['name'],
         configs["normal_left"]),
    )
    __create_table(foter_data, worksheet)

    workbook.close()
    return output


def get_subsidy_report(tenant_id,
                       current_provider,
                       date_from=None,
                       date_till=None,
                       current_account=None):
    # Если не переданы, возьмем данные за прошлый месяц
    if not (date_from and date_till):
        date_till = DateHelpFulls.end_of_day(datetime.now())
        date_from = DateHelpFulls.start_of_day(
            date_till - relativedelta(months=1)
        )
    subsidy_report = get_subsidy(tenant_id, current_provider,
                                 date_from, date_till,
                                 current_account)
    return create_subsidy_xlsx(subsidy_report)
