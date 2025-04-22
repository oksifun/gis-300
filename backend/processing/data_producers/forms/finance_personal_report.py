from datetime import datetime
from fractions import Fraction
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta
from mongoengine import ValidationError

from app.area.models.area import Area
from app.house.models.house import House
from app.personnel.models.personnel import Worker
from lib.helpfull_tools import DateHelpFulls, by_mongo_path
from lib.helpfull_tools import DateHelpFulls as dhf
from app.accruals.cipca.source_data.areas import find_result
from processing.data_producers.associated.services import PENALTY_SERVICE_TYPE, \
    ADVANCE_SERVICE_TYPE
from processing.data_producers.balance.services.fpr import (
    ServicesBalanceFprReport
)
from processing.models.billing.account import Account
from processing.models.billing.privilege import Privilege
from processing.models.billing.family_role_catalogue import FamilyRoleCatalogue
from processing.models.billing.settings import Settings
from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.responsibility import Responsibility
from processing.models.billing.tenant_data import TenantData

# Русские именования по типам комнат
ROOM_TYPES = {
    'wc': 'санузел',
    'hall': 'прихожая',
    'garage': 'гараж',
    'toilet': 'туалет',
    'storey': 'этажная площадка',
    'living': 'жилая комната',
    'kitchen': 'кухня',
    'corridor': 'коридор',
    'bathroom': 'ванная',
}

PROPERTY_TYPE = {
    'private': 'Частная собственность',
    'government': 'Госсобственность',
    'municipal': 'Муниципальная собственность',
}

PrivilegeDocumentTypes = (
    ('hero', 'Удостоверение Героя СССР, РФ'),
    ('medal_glory', 'Удостоверение к ордену Славы'),
    ('hero_labour_ussr', 'Удостоверение Героя Соц. Труда'),
    ('medal_labour_glory', 'Удостоверение к ордену  Трудовой Славы'),
    ('hero_labour', 'Удостоверение Героя Труда РФ'),
    ('gdw_disabled', 'Удостоверение инвалида ВОВ'),
    ('privilege_disabled', 'Удостоверение инвалида о '
                           'праве на льготы (Афганистан, Чечня и т.п.)'),
    ('gdw_participant', 'Удостоверение участника ВОВ'),
    ('gdw_veteran', 'Удостоверение ветерана ВОВ'),
    ('gdw_freelancer', 'Удостоверение вольнонаемного в период ВОВ'),
    ('gdw_partisan', 'Удостоверение партизана в период ВОВ'),
    ('medal_leningrad_defence', 'Удостоверение награжденного медалью '
                                '"За оборону Ленинграда"'),
    ('privilege_moscow_defence', 'Справка о праве на льготы участника '
                                 'обороны Москвы'),
    ('medal_moscow_defence', 'Удостоверение к медали "За оборону Москвы"'),
    ('sign_leningrad_siege', 'Удостоверение к знаку '
                             '"Жителю блокадного Ленинграда"'),
    ('privilege_veteran', 'Свидетельство о праве на льготы '
                          'ветерана боевых действий'),
    ('veteran_war', 'Удостоверение ветерана боевых действий'),
    ('veteran_war_relative', 'Удостоверение члена семьи погибшего '
                             'военнослужащего, умершего (погибшего) ИВОВ, '
                             'УВОВ, ветерана боевых действий'),
    ('pension_earner_lost', 'Справка о пенсии по потере кормильца '
                            '(ст. 21 закона РФ "О ветеранах")'),
    ('concentration_camp', 'Удостоверение несовершеннолетнего '
                           'узника концлагеря '),
    ('rehabilitated', 'Свидетельство  реабилитированного'),
    ('repressions1', 'Свидетельство пострадавшего от политических репрессий'),
    ('repressions2', 'Удостоверение пострадавшего от политических репрессий'),
    ('chernobyl_diseased', 'Удостоверение перенесшего лучевую '
                           'болезнь вследствие аварии на ЧАЭС'),
    ('chernobyl_liquidator', 'Удостоверение ликвидатора '
                             'последствий аварии на ЧАЭС'),
    ('chernobyl_victim', 'Удостоверение пострадавшего '
                         'вследствие аварии на ЧАЭС'),
    ('veteran_especial_risk', 'Удостоверение ветерана '
                              'подразделения особого риска'),
    ('especial_risk_relative', 'Справка о потере кормильца из числа лиц '
                               'подразделений особого риска'),
    ('mayak_victim', 'Удостоверение пострадавшего '
                     'вследствие аварии на ПО "МАЯК"'),
    ('mayak_liquidator', 'Удостоверение ликвидатора '
                         'последствий аварии на ПО "МАЯК"'),
    ('semipalatinsk_victim', 'Удостоверение пострадавшего от '
                             'ядерных испытаний на Семипалатинском полигоне'),
    ('donor', 'Справка о сдаче крови или плазмы'),
    ('donor_moscow', 'Удостоверение почетного донора Москвы'),
    ('donor_russian', 'Удостоверение почетного донора СССР, России'),
    ('large_family', 'Удостоверение многодетной семьи'),
    ('medical_certificate', 'Справка МСЭ (ВТЭК)'),
    ('labour_veteran', 'Удостоверение ветерана труда'),
    ('veteran', 'Удостоверение ветерана военной службы'),
    ('privilege_certificate1', 'Удостоверение о праве на льготы'),
    ('privilege_certificate2', 'Свидетельство о праве на льготы'),
    ('privilege_certificate3', 'Справка о праве на льготы '),
    ('pension', 'Пенсионное удостоверение'),
    ('school_certificate', 'Справка из школы для детей старше 16 лет'),
    ('marriage', 'Свидетельство о браке'),
    ('council_document', 'Распорядительный документ Главы районной Управы'),
    ('public_care', 'Справка органов опеки'),
    ('pension_insurance', 'Справка ПФР о назначении страховой пенсии'),
)
PrivilegeDocumentTypes = {x[0]: x[1] for x in PrivilegeDocumentTypes}


def __create_table(table, worksheet):
    """Сотворение таблицы"""
    for coordinate, data, config in table:
        worksheet.merge_range(coordinate, data, config)


def _get_property_share(p_history, date_on):
    for p in p_history:
        if p['value'][0] == 0 and p['value'][1] == 0:
            p['value'][1] = 1
    total = sum([
        (-1 if x['op'] == 'red' else 1) * Fraction(*x['value'])
        for x in p_history
        if x['value'] and (x.get('date') or date_on) <= date_on
    ])
    return total.numerator / total.denominator


def _get_mates(month, provider_id, area_id):
    mates = Account.objects.as_pymongo().filter(
        area__id=area_id, is_deleted__ne=True
    )
    resp = Responsibility.objects.as_pymongo().filter(__raw__={
        'account.area._id': area_id,
        'provider': provider_id,
        '$and': [
            {'$or': [
                {'date_from': None},
                {'date_from': {'$lt': month + relativedelta(months=1)}}
            ]},
            {'$or': [{'date_till': None}, {'date_till': {'$gte': month}}]},
        ]
    })
    resp_areas = {
        r['account']['area']['_id']: r['account']['_id']
        for r in resp
    }
    result = find_result(mates, month, resp_areas)
    return result


def _get_privilegers(mates, date):
    """
    Получение льготников
    :type mates: list: проживающие
    :return: list: список льготников и оснований для льгот
    """
    # Сами льготники
    privilegers = {}
    # Список id всех льгот
    all_privs = []
    for mate in mates:
        if mate.get('privileges'):
            privs = [p['privilege'] for p in mate['privileges']
                     if (p.get('date_till') or datetime.max) >= date]
            all_privs.extend(privs)
            privilegers.update({mate['str_name']: dict(privs=privs,
                                                       _id=mate['_id'])})

    privileges = Privilege.objects(id__in=list(set(all_privs))).as_pymongo()
    if not privileges:
        return
    privileges = {x['_id']: x["title"] for x in privileges}

    # Получение основания для льготы
    reasons_query = TenantData.objects(
        tenant__in=[x["_id"] for x in privilegers.values()]
    ).exclude('id', 'passport', 'id_docs').as_pymongo()
    reasons = {r['tenant']: r.get('privilege_docs') for r in reasons_query}

    # Устанавливаем льготы льготникам
    for p in privilegers:
        privil_row = []
        # Основания для льгот
        tenant_reasons = reasons.get(privilegers[p]['_id'], {})
        for priv_id in privilegers[p]['privs']:
            privil = []
            privil.append(privileges[priv_id])
            # Подбор основания для льготы из списка оснований
            if tenant_reasons:
                for reason in tenant_reasons:
                    if priv_id == reason['privilege']:
                        privilege_reason = [
                            PrivilegeDocumentTypes[reason['doc_type']],
                            reason.get('series', ''),
                            reason.get('number', ''),
                            reason.get('issuer', ''),
                            DateHelpFulls.pretty_date_converter(
                                reason['date_from'],
                                with_day=True
                            ) if reason['date_from'] else '',
                        ]
                        privil.extend([' '.join(map(str, privilege_reason))])
                        break
            if len(privil) < 2:
                privil.extend(['Документ не найден'])
            privil_row.append(privil)
        privilegers[p] = privil_row
    return privilegers


def _get_family_roles(tenant_id, mates):
    """
    Получение родственных связей проживающих для жителя
    :param tenant_id: id жителя относительного которго проверяется родство
    :param mates: dict: сожители
    :return: модифицирует словарь mates новым полем role
    """
    # id ролей сожителей
    roles = list({
        y['role']
        for x in mates if x.get('family')
        for y in x['family'].get('relations', [])
    })
    if not roles:
        return mates
    family_roles = list(FamilyRoleCatalogue.objects(id__in=roles).as_pymongo())
    family_roles_dict = {role['_id']: role for role in family_roles}
    # Добавим роли сожителям
    for mate in mates:
        rel_list = by_mongo_path(mate, 'family.relations')
        if rel_list:
            for rel in rel_list:
                if rel['related_to'] == tenant_id:
                    mate.update(
                        dict(role=family_roles_dict[rel['role']]['title'])
                    )
    return mates


def _add_info_to_accruals(
        balance_in,
        debit,
        viscera,
        credit
):
    """
    Получение дополнительных данных о начислениях ЖКУ
    по статьям коммунальных и жилищных услуг
    :param: tenant_id: ObjectId
    :return: list: список начисленного по услугам для таблицы
    """
    # Создание словаря тарифных планов
    s_types = set(viscera) | set(credit) | set(balance_in)
    tariff_plan = TariffPlan.objects(
        id__in=tuple({
            t
            for s in viscera.values() if s.get('tariff_plan')
            for t in s['tariff_plan']
        })
    ).only('group', 'tariffs').as_pymongo()

    tariffs = {
        tariff['service_type']: tariff
        for tariff in [y for x in tariff_plan for y in x['tariffs']]
        # if str(tariff['group'])[-1] in ('0', '1')  # TODO Задний проход
    }
    tariffs[PENALTY_SERVICE_TYPE] = {'title': 'Пени', 'units': ''}
    tariffs[ADVANCE_SERVICE_TYPE] = {'title': 'Аванс', 'units': ''}
    # Суммирование по тарифным планам
    services = []
    if viscera:
        for s_id in s_types:
            service = dict(service_type=s_id)
            service['balance_in'] = balance_in.get(s_id, 0)
            service['on_period'] = credit.get(s_id, dict(payment=0))['payment']
            debit_summary = debit.get(s_id, dict(first=0, second=0))
            debit_summary = debit_summary['first']
            credit_summary = credit.get(s_id, dict(payment=0, advance_storno=0))
            credit_summary = (
                    credit_summary['payment'] + credit_summary['advance_storno']
            )
            service['balance_out'] = (
                    service['balance_in'] + debit_summary - credit_summary
            )
            service['viscera'] = viscera.get(s_id, {})
            service['value'] = debit.get(s_id, dict(first=0))['first']
            if tariffs.get(s_id):
                service['units'] = tariffs[s_id]['units']
                service['title'] = tariffs[s_id]['title']
            else:
                service['units'] = ''
                service['title'] = ''
            services.append(service)
    return services


def get_fin_data(
        tenant_id,
        provider,
        date_from=None,
        date_till=None,
        current_account=None,
        binds=None
):
    """
    Сбор данных для справки 'Копия ФЛС для Москвы'
    :param date_from: начало периода
    :param current_account: аккаунт с текущей сессии
    :param date_till: дата на которую формируем справку
    :param tenant_id: id лицевого счета
    :param provider: object Provider
    :param binds: привязки
    :return: отчет xlsx
    """
    provider_id = provider.pk
    tenant = Account.objects(id=tenant_id).as_pymongo().get()
    area = Area.objects(id=tenant['area']['_id']).as_pymongo().get()
    house = House.objects(id=tenant['area']['house']['_id']).as_pymongo().get()

    # Вытягиваем должность и имя выдающего справку
    if current_account:
        accountant = dict(current_account.to_mongo())
    else:
        accountant = Worker.objects(
            provider__id=provider_id, position__code='acc1',
            is_dismiss__ne=True,
            is_deleted__ne=True,
        ).only('short_name', 'position.name').as_pymongo().first()
    if not accountant:
        raise ValidationError('У организации не указан главный бухгалтер.')

    # Совместно проживающие
    tenant_mates = _get_mates(
        date_till, provider_id, area['_id']
    ).get(tenant_id)
    if not tenant_mates:
        raise ValidationError(' не имеет "статусов жильца"')
    # Получаем родственные связи
    _get_family_roles(tenant_id, tenant_mates['mates'])
    # Начисления по услугам
    sector = Settings.objects(
        house=house['_id'],
        provider=provider_id
    ).distinct('sectors.sector_code')
    sb = ServicesBalanceFprReport(
        date_from=date_from,
        date_till=date_till,
        tenant_id=tenant_id,
        sectors=sector if sector else ['rent', 'capital_repair'],
        account_types=None,
        by_bank=None,
        area_types=None,
        is_developer=None,
        binds=binds
    )
    balance_in = sb.get_service_balance()
    debit, viscera = sb.get_service_debit()
    credit = sb.get_service_credit()
    accruals_table = _add_info_to_accruals(balance_in, debit, viscera, credit)
    # Льготы
    privilegers = _get_privilegers(tenant_mates['mates'], date_till)
    # Дополнительная площадь
    additional_square = sum([
        area.get('area_loggias', 0),
        area.get('area_balconies', 0),
        area.get('area_corridors', 0),
        area.get('area_cupboards', 0),
        area.get('area_pantries', 0),
    ])

    data = dict(
        header=dict(
            tenant_name=tenant['str_name'],
            account_number=tenant['number'],
            street=house['street_only'],
            address='{}{}, {}'.format(
                (house['zip_code'] + ', ') if house.get('zip_code') else '',
                area['house']['address'],
                area['str_number_full']
            ),
            room_count=len([
                r for r in area['rooms']
                if r['number'] and r.get('type') == 'living']
            ) if area.get('rooms') else 0,
            square=area['area_total'],
            registred=tenant_mates['summary']['registered'],
            living=tenant_mates['summary']['living'],
            house_number=house['number'],
            bulk=house.get('bulk') or '',
            area_number=area['str_number'],
            phone=', '.join(
                ['+7 ({}) {}'.format(x['code'], x['number'])
                 for x in tenant['phones']]
            ) if tenant.get('phones') else '',
            provider=provider.str_name,
            property_type=tenant['statuses']['ownership']['type']
            if tenant.get('statuses')
               and tenant['statuses'].get('ownership')
               and tenant['statuses']['ownership'].get('type')
            else 'private',
            is_privilege='Да' if privilegers else 'Нет',
            certificate=by_mongo_path(
                tenant,
                'statuses.ownership.certificate.supporting_documents'
            )
        ),
        area_explication=dict(
            rooms=area.get('rooms', []),
            square_common=area['area_total'],
            square_living=area.get('area_living', 0),
            square_additional=additional_square,
            square_full=area['area_total'] + additional_square,
            square_balconies=area.get('area_balconies', 0),
            square_corridors=area.get('area_corridors', 0),
            square_cupboards=area.get('area_cupboards', 0),
            square_loggias=area.get('area_loggias', 0),
            square_pantries=area.get('area_pantries', 0),
        ),
        mates=tenant_mates,
        privilegers=privilegers,
        account_balance=sum([x['balance_out'] for x in accruals_table]),
        accountant_name=accountant.get('short_name'),
        accountant_pos=by_mongo_path(accountant, 'position.name'),
        date_from=date_from,
        date=date_till - relativedelta(days=1),
        accruals_table=accruals_table
    )
    return data


def create_base_sheet(worksheet, configs, tenant_data):
    """Лист 1 - Общая информация"""

    # Конфиги колонок  и рядов
    # Высоты ячеек
    empty_row_height = 7  # пустые строки
    table_ceil_height_expl = 12  # таблица экспликации площади
    table_ceil_height_family = 25  # таблица члены семьи
    table_ceil_height_privil = 32  # таблица льготников

    # Для рядов
    # сначала для всех
    for row in range(100):
        worksheet.set_row(row, 20)
    # Индивидуально для шапки (она статическая)
    for row in (0, 2, 4, 7, 9, 11, 13, 15, 17):
        worksheet.set_row(row, empty_row_height)

    # Для колонок
    worksheet.set_column("A:A", 0.5)
    worksheet.set_column("B:E", 2)
    worksheet.set_column("F:H", 2.7)
    worksheet.set_column("I:P", 2)
    worksheet.set_column("Q:V", 3)
    worksheet.set_column("W:BB", 2)

    # Категории данных
    header = tenant_data['header']
    expl_data = tenant_data['area_explication']

    # Шапка
    head_data = (
        ('B2:J2', "Управляющая организация:", configs["normal_left"]),
        ('K2:AJ2', header['provider'], configs["normal_left_border"]),
        ('E4:Q4', "ФИНАНСОВО-ЛИЦЕВОЙ СЧЕТ №", configs["title"]),
        ('R4:AJ4', header['account_number'], configs["t_bold_ceil_center_bot"]),

        ('B6:G6', "Ф.И.О. собственника", configs["normal_left"]),
        ('H6:R6', header['tenant_name'], configs["normal_left_border"]),
        ('S6:X6', "Основание заселения", configs["normal_left"]),
        ('Y6:AJ6', '', configs["normal_left_border"]),

        ('B7:C7', "Улица", configs["normal_left"]),
        ('D7:L7', header['street'], configs["normal_left_border"]),
        ('M7:N7', ", дом", configs["normal_left"]),
        ('O7:P7', header['house_number'], configs["normal_left_border"]),
        ('Q7:R7', ", корп.", configs["normal_left"]),
        ('S7:T7', header['bulk'], configs["normal_left_border"]),
        ('U7:W7', ", кв.", configs["normal_left"]),
        ('X7:Y7', header['area_number'], configs["normal_left_border"]),
        ('Z7:AB7', ", телефон", configs["normal_left"]),
        ('AC7:AJ7', header['phone'], configs["normal_left_border"]),

        ('B9:J9', "Документ на квартиру:", configs["normal_left"]),
        ('K9:AJ9', header['certificate'], configs["normal_left_border"]),

        ('B11:G11', "Вид собственности:", configs["normal_left"]),
        ('H11:P11', PROPERTY_TYPE[header['property_type']],
         configs["normal_left"]),
        ('R11:Y11', "Предоставляются льготы:", configs["normal_left"]),
        ('Z11:AJ11', header['is_privilege'], configs["normal_left"]),

        # Площадь квартиры
        ('B13:H13', "Площадь квартиры", configs["title"]),
        ('B15:D15', "Общая:", configs["normal_left"]),
        ('E15:G15', '{} м²'.format(expl_data['square_common']),
         configs["normal_left"]),
        ('I15:K15', "Жилая:", configs["normal_left"]),
        ('L15:N15', '{} м²'.format(expl_data['square_living']),
         configs["normal_left"]),
        ('P15:S15', "Дополнительная:", configs["normal_left"]),
        ('T15:V15', '{} м²'.format(expl_data['square_additional']),
         configs["normal_left"]),
        ('X15:Z15', "Полная:", configs["normal_left"]),
        ('AA15:AC15', '{} м²'.format(expl_data['square_full']),
         configs["normal_left"]),

        ('B17:K17', "Экспликация площади квартиры", configs["title"]),
    )
    __create_table(head_data, worksheet)

    # Таблица 'Экспликация площади квартиры'
    # Заголовки столбцов
    a_t_start = 19
    worksheet.set_row(a_t_start - 1, table_ceil_height_expl)
    table_titles = (
        ('B{r}:K{r}'.format(r=a_t_start),
         "Наименование площади", configs["table_title_ceil"]),
        ('L{r}:O{r}'.format(r=a_t_start),
         "Площадь", configs["table_title_ceil"]),
        ('P{r}:AJ{r}'.format(r=a_t_start),
         "Комментарий", configs["table_title_ceil"]),
    )
    __create_table(table_titles, worksheet)

    # Данные таблицы
    expl_sum = 0.  # Итоговая сумма
    table_config = configs['table_number']
    for room in expl_data['rooms']:
        if room['square'] != 0:
            worksheet.set_row(a_t_start, table_ceil_height_expl)  # ширина яч.
            a_t_start += 1
            room_name = ROOM_TYPES.get(room.get('type'), '').capitalize()
            room_square = room['square']
            comment = ''
            expl_sum += room_square

            worksheet.merge_range(
                'B{r}:K{r}'.format(r=a_t_start), room_name, table_config
            )
            worksheet.merge_range(
                'L{r}:O{r}'.format(r=a_t_start), room_square, table_config
            )
            worksheet.merge_range(
                'P{r}:AJ{r}'.format(r=a_t_start), comment, table_config
            )
    # Итого по таблице
    worksheet.set_row(a_t_start, table_ceil_height_expl)  # ширина ячейки
    a_t_start += 1
    worksheet.merge_range(
        'B{r}:K{r}'.format(r=a_t_start), 'Итого', configs['table_number']
    )
    worksheet.merge_range(
        'L{r}:O{r}'.format(r=a_t_start),
        expl_sum,
        configs['table_number_bold']
    )

    # Жильцы
    mates_summary = tenant_data['mates']['summary']
    mates = tenant_data['mates']['mates']
    worksheet.set_row(a_t_start, empty_row_height)  # ширина пустот
    a_t_start += 2
    worksheet.merge_range(
        'B{r}:K{r}'.format(r=a_t_start), "Жильцы", configs["title"]
    )
    a_t_start += 1
    # Количество временно проживающих
    temporary = len(
        [1 for mate in mates
         if by_mongo_path(mate, 'statuses.living.[0].value.is_temporary')]
    )
    mates_data = (
        ('B{r}:I{r}'.format(r=a_t_start),
         "Зарегистрировано:", configs["normal_left"]),
        ('J{r}:L{r}'.format(r=a_t_start),
         '{} чел.'.format(mates_summary['registered']),
         configs["normal_left"]),

        ('P{r}:S{r}'.format(r=a_t_start),
         "Проживает:",
         configs["normal_left"]),
        ('T{r}:V{r}'.format(r=a_t_start),
         '{} чел.'.format(mates_summary['living']),
         configs["normal_left"]),

        ('X{r}:AD{r}'.format(r=a_t_start),
         "В том числе временно:",
         configs["normal_left"]),
        ('AE{r}:AJ{r}'.format(r=a_t_start),
         '{} чел.'.format(temporary),
         configs["normal_left"]),
    )
    __create_table(mates_data, worksheet)

    # Члены семьи проживающих на данной площади
    worksheet.set_row(a_t_start, empty_row_height)  # ширина пустот
    a_t_start += 2
    worksheet.merge_range(
        'B{r}:P{r}'.format(r=a_t_start),
        "Члены семьи проживающих на данной площади",
        configs["title"]
    )
    worksheet.set_row(a_t_start, table_ceil_height_family)  # ширина ячейки
    a_t_start += 1
    # Таблица
    table_config = configs["table_title_ceil"]
    table_mates_titles = (
        ('B{r}:E{r}'.format(r=a_t_start), "Дата прибытия", table_config),
        ('F{r}:H{r}'.format(r=a_t_start), "Проживает", table_config),
        ('I{r}:L{r}'.format(r=a_t_start), "Дата выбытия", table_config),
        ('M{r}:P{r}'.format(r=a_t_start), "Цель прибытия", table_config),
        ('Q{r}:V{r}'.format(r=a_t_start), "Ф.И.О.", table_config),
        ('W{r}:Z{r}'.format(r=a_t_start), "Дата рождения", table_config),
        ('AA{r}:AJ{r}'.format(r=a_t_start), "Родственные отношения",
         table_config),
    )
    __create_table(table_mates_titles, worksheet)

    # Данные таблицы
    t_config = configs["table_bold_ceil_center"]
    for mate in mates:
        worksheet.set_row(a_t_start, table_ceil_height_family)  # ширина ячейки
        # Бывает, что поле пустое
        living = by_mongo_path(mate, 'statuses.registration')
        if living:
            living = living[0]
            # Временное проживание
            temporary = by_mongo_path(living, 'value.is_temporary')
            # Проживает
            is_living = mate['summary'].get('living', False)
        else:
            temporary = is_living = ''
        # Дата рождения
        birth_date = mate.get('birth_date')
        birth_date = birth_date.strftime('%d.%m.%Y') if birth_date else ''
        # Дата заселения
        reg_start = mate['summary'].get('reg_start')
        reg_start = reg_start.strftime('%d.%m.%Y') if reg_start else ''
        if not (reg_start and living):
            continue
        a_t_start += 1

        table_mate = (
            ('B{r}:E{r}'.format(r=a_t_start), reg_start, t_config),
            ('F{r}:H{r}'.format(r=a_t_start),
             "Да" if is_living else "Нет",
             t_config),
            ('I{r}:L{r}'.format(r=a_t_start),
             living.get('date_till', '') if living else '',
             t_config),
            ('M{r}:P{r}'.format(r=a_t_start),
             'Постоянно' if not temporary else 'Временно',
             t_config),
            ('Q{r}:V{r}'.format(r=a_t_start), mate["str_name"], t_config),
            ('W{r}:Z{r}'.format(r=a_t_start), birth_date, t_config),
            ('AA{r}:AJ{r}'.format(r=a_t_start), mate.get('role'), t_config)
        )
        __create_table(table_mate, worksheet)

    # Таблица собственников
    worksheet.set_row(a_t_start, empty_row_height)  # ширина пустот
    a_t_start += 2
    worksheet.set_row(a_t_start, table_ceil_height_family)  # ширина ячейки
    t_config = configs["table_title_ceil"]
    table_mates_titles = (
        ('B{r}:V{r}'.format(r=a_t_start),
         "Собственник (фамилия, имя, отчество)",
         t_config),
        ('W{r}:Z{r}'.format(r=a_t_start), "Дата рождения", t_config),
        ('AA{r}:AJ{r}'.format(r=a_t_start), "Доля собственности", t_config),
    )
    __create_table(table_mates_titles, worksheet)

    t_config = configs["table_bold_ceil_center"]
    for mate in mates:
        owner_status = mate['statuses'].get('ownership')
        if owner_status:  # and owner_status.get('is_owner'):
            birth_date = mate.get('birth_date')
            birth_date = birth_date.strftime('%d.%m.%Y') if birth_date else ''
            # Доля собственности
            try:
                p_s = owner_status['property_share']
                p_s = (
                    1
                    if (p_s[0] == p_s[1] == 1)
                    else '{}/{}'.format(p_s[0], p_s[1])
                )
            except IndexError:
                p_s = _define_property(owner_status['property_share'])
            # Не включать в список собственников жильцов,
            # доля собственности которых равна 0/1.
            if p_s == '0/1':
                continue
            worksheet.set_row(a_t_start,
                              table_ceil_height_expl)  # ширина ячейки
            a_t_start += 1
            table_mates = (
                ('B{r}:V{r}'.format(r=a_t_start), mate["str_name"], t_config),
                ('W{r}:Z{r}'.format(r=a_t_start), birth_date, t_config),
                ('AA{r}:AJ{r}'.format(r=a_t_start), p_s, t_config),
            )
            __create_table(table_mates, worksheet)

    # Таблица "Лготники"
    worksheet.set_row(a_t_start, empty_row_height)  # ширина пустот
    a_t_start += 2
    t_config = configs["table_title_ceil"]
    table_privil_titles = (
        ('B{r}:K{r}'.format(r=a_t_start), "Льготник", t_config),
        ('L{r}:W{r}'.format(r=a_t_start), "Категория льготника", t_config),
        ('X{r}:AJ{r}'.format(r=a_t_start), "Основание для льготы", t_config),
    )
    __create_table(table_privil_titles, worksheet)

    privilegers = tenant_data['privilegers']
    t_config = configs["table_bold_ceil_center"]
    if privilegers:
        for name, privs in privilegers.items():
            for priv, reason in privs:
                a_t_start += 1
                table_privil = (
                    ('B{r}:K{r}'.format(r=a_t_start), name, t_config),
                    ('L{r}:W{r}'.format(r=a_t_start), priv, t_config),
                    ('X{r}:AJ{r}'.format(r=a_t_start), reason, t_config),
                )
                # ширина ячейки
                worksheet.set_row(
                    a_t_start - 1, table_ceil_height_privil
                )
                __create_table(table_privil, worksheet)

    # Подвал документа
    # Сумма задолжности
    worksheet.set_row(a_t_start, empty_row_height)  # ширина пустот
    a_t_start += 2
    worksheet.merge_range('B{r}:P{r}'.format(r=a_t_start),
                          "Информация о задолженности",
                          configs["title"])
    a_t_start += 1
    balance = tenant_data['account_balance']
    if balance > 0:
        ceil_data = 'Сумма задолженности по лицевому счету на {date} ' \
                    'составляет: {debt} руб.'.format(
            date=tenant_data['date'].strftime('%d.%m.%Y'),
            debt=round(balance / 100, 2) if balance else 0.
        )
    elif balance < 0:
        ceil_data = 'Сумма переплаты по лицевому счету ' \
                    'на {date} составляет: {debt} руб.'.format(
            date=tenant_data['date'].strftime('%d.%m.%Y'),
            debt=round(abs(balance) / 100, 2) if balance else 0.
        )
    else:
        ceil_data = 'На {date} по лицевому счету задолженности нет'.format(
            date=tenant_data['date'].strftime('%d.%m.%Y')
        )

    worksheet.merge_range('B{r}:Z{r}'.format(r=a_t_start),
                          ceil_data,
                          configs["normal_left"])

    # Остальная часть
    worksheet.set_row(a_t_start, empty_row_height)  # ширина пустот
    a_t_start += 2
    footer = (
        ('B{r}:F{r}'.format(r=a_t_start), "Копия верна", configs["title"]),
        ('H{r}:P{r}'.format(r=a_t_start), tenant_data['accountant_pos'],
         configs["normal_c_border"]),
        ('R{r}:V{r}'.format(r=a_t_start), "", configs["normal_left_border"]),
        ('X{r}:AF{r}'.format(r=a_t_start), tenant_data['accountant_name'],
         configs["normal_c_border"]),
        # Подписи под чертой
        ('H{r}:P{r}'.format(r=a_t_start + 1),
         "должность", configs["normal_center"]),
        ('R{r}:V{r}'.format(r=a_t_start + 1),
         "подпись", configs["normal_center"]),
        ('X{r}:AF{r}'.format(r=a_t_start + 1),
         "расшифровка подписи", configs["normal_center"]),
        ('E{r}:F{r}'.format(r=a_t_start + 2),
         "М.П.", configs["normal_center"])
    )
    __create_table(footer, worksheet)


def create_balance_sheet(worksheet, configs, tenant_data):
    """Лист 2 - ОСВ"""

    # Формирование содержимого файла xlsx отчёта
    # Конфиги колонок и рядов
    # Высоты ячеек
    empty_row_height = 7  # пустые строки
    table_ceil_height = 22  # строки таблицы

    # Для рядов
    # сначала для всех
    for row in range(50):
        worksheet.set_row(row, 15)
    # Индивидуально для шапки (она статическая)
    for row in (1, 8):
        worksheet.set_row(row, empty_row_height)
    # индивидуально по строкам
    worksheet.set_row(10, 20)

    # Для колонок
    # сначала для всех
    worksheet.set_column("B:AZ", 2.3)
    # индивидуально
    worksheet.set_column("A:A", 0.2)

    # Шапка
    header = tenant_data['header']
    head_data = (
        ('B1:AP1',
         "Копия финансово-лицевого счета №{}".format(header['account_number']),
         configs["b_title"]),

        ('B3:H3', "Адрес", configs["b_normal_left"]),
        ('I3:Z3', header['address'], configs["b_table_bold_ceil"]),

        ('B4:H4', "Собственник (наниматель)", configs["b_normal_left"]),
        ('I4:Z4', header['tenant_name'], configs["b_table_bold_ceil"]),

        ('B5:H5', "Площадь лицевого счета", configs["b_normal_left"]),
        ('I5:J5', header['square'], configs["b_normal_right"]),

        ('B6:H6', "Зарегистрировано", configs["b_normal_left"]),
        ('I6:J6', header['registred'], configs["b_normal_right"]),

        ('B7:H7', "Проживает", configs["b_normal_left"]),
        ('I7:J7', header['living'], configs["b_normal_right"]),

        ('K5:S5', "кв.м.", configs["b_normal_left"]),
        ('K6:S6',
         "чел. на ({})".format(tenant_data['date'].strftime('%d.%m.%Y')),
         configs["b_normal_left"]),
        ('K7:S7', "чел.", configs["b_normal_left"])
    )
    __create_table(head_data, worksheet)

    # Таблица
    # Заголовки столбцов
    table_titles = (
        ('B10:K11', "Услуга", configs["b_table_title_ceil"]),
        ('L10:N11', "Ед.изм.", configs["b_table_title_ceil"]),
        ('O10:Q11', "Тариф", configs["b_table_title_ceil"]),
        ('R10:T11', "Объем", configs["b_table_title_ceil"]),
        (
            'U10:W11',
            "Долг на {}".format(tenant_data['date_from'].strftime('%d.%m.%Y')),
            configs["b_table_title_ceil"]
        ),
        ('X11:Z11', "Стоимость", configs["b_table_title_ceil"]),
        ('AA11:AC11', "Перерасч.", configs["b_table_title_ceil"]),
        ('AD11:AG11', "Льготы", configs["b_table_title_ceil"]),
        ('AH11:AJ11', "Всего", configs["b_table_title_ceil"]),
        ('AK10:AM11', "Оплачено в периоде", configs["b_table_title_ceil"]),
        (
            'AN10:AP11',
            "Долг на {}".format(tenant_data['date'].strftime('%d.%m.%Y')),
            configs["b_table_title_ceil"]
        ),
        ('X10:AJ10', "Начислено", configs["b_table_title_ceil"]),
    )
    __create_table(table_titles, worksheet)

    # Данные таблицы
    special_round = lambda x: round(x / 100, 2) or ''
    t_st = 11
    service_data = tenant_data['accruals_table']
    t_c_n = configs["b_table_number"]  # Для числовых ячеек таблицы
    # Аккумуляторы для "Итого"
    total_all = sum([x['value'] for x in service_data])
    total_privileges = sum(
        [-x['viscera'].get('privileges', 0) for x in service_data]
    )
    total_recalc = sum(
        [x['viscera'].get('recalculations', 0) for x in service_data]
    )
    total_value = total_all - total_privileges - total_recalc

    total_balance_in = sum([x['balance_in'] for x in service_data])
    total_on_period = sum([x['on_period'] for x in service_data])
    # Только если есть начисления
    if service_data:
        for service in sorted(service_data, key=lambda x: x['title']):
            worksheet.set_row(t_st, table_ceil_height)  # ширина яч.
            t_st += 1
            # Суммируем
            tariff = service['viscera'].get('tariff', 0)
            consumption = service['viscera'].get('consumption', '')
            recalculations = service['viscera'].get('recalculations', 0)
            privileges = service['viscera'].get('privileges', 0)
            service_table = (
                # Услуга
                ('B{r}:K{r}'.format(r=t_st),
                 service['title'],
                 configs["b_t_title_left"]),
                # Ед. изм.
                ('L{r}:N{r}'.format(r=t_st),
                 service['units'],
                 configs["b_t_title_center"]),
                # Тариф
                ('O{r}:Q{r}'.format(r=t_st),
                 special_round(tariff),
                 t_c_n),
                # Норма потребления (Объем)
                ('R{r}:T{r}'.format(r=t_st),
                 consumption,
                 configs['b_table_number_norm']),
                # Входное сальдо
                ('U{r}:W{r}'.format(r=t_st),
                 special_round(service['balance_in']),
                 t_c_n),
                # Начисления
                ('X{r}:Z{r}'.format(r=t_st),
                 special_round(service['value'] - privileges - recalculations),
                 t_c_n),
                # Перерасчет
                ('AA{r}:AC{r}'.format(r=t_st),
                 special_round(recalculations),
                 t_c_n),
                # Льготы
                ('AD{r}:AG{r}'.format(r=t_st),
                 special_round(-privileges),
                 t_c_n),
                # Всего
                ('AH{r}:AJ{r}'.format(r=t_st),
                 special_round(service['value']),
                 t_c_n),
                # Оплачено в периоде
                ('AK{r}:AM{r}'.format(r=t_st),
                 special_round(service['on_period']),
                 t_c_n),
                # Выходное сальдо
                ('AN{r}:AP{r}'.format(r=t_st),
                 special_round(service['balance_out']),
                 t_c_n),
            )
            __create_table(service_table, worksheet)

    # Итого по таблице
    worksheet.set_row(t_st, table_ceil_height)  # ширина ячейки
    t_st += 1
    final = (
        ('B{r}:T{r}'.format(r=t_st), 'ИТОГО: ', configs['b_t_title_right']),
        ('U{r}:W{r}'.format(r=t_st), special_round(total_balance_in), t_c_n),
        ('X{r}:Z{r}'.format(r=t_st), special_round(total_value), t_c_n),
        ('AA{r}:AC{r}'.format(r=t_st), special_round(total_recalc), t_c_n),
        ('AD{r}:AG{r}'.format(r=t_st), special_round(total_privileges), t_c_n),
        ('AH{r}:AJ{r}'.format(r=t_st), special_round(total_all), t_c_n),
        ('AK{r}:AM{r}'.format(r=t_st), special_round(total_on_period), t_c_n),
        ('AN{r}:AP{r}'.format(r=t_st),
         special_round(tenant_data['account_balance']),
         t_c_n)
    )
    __create_table(final, worksheet)

    # Подвал
    worksheet.set_row(t_st, empty_row_height)  # ширина ячейки
    t_st += 2
    # Состояние баланса
    balance = tenant_data['account_balance']
    balance_text = "Задолженность за ЖКУ на"
    # Если сальдо больше 0
    if balance > 0:
        balance_state = '{debt} руб.'.format(
            debt=round(balance / 100, 2)
        )
    else:
        balance_state = 'Отсутствует'

    footer_data = (
        ('B{r}:L{r}'.format(r=t_st), balance_text,
         configs["b_normal_left"]),
        ('N{r}:V{r}'.format(r=t_st),
         DateHelpFulls.pretty_date_converter(
             tenant_data['date'],
             with_day=True,
             genitive=True
         ),
         configs["b_table_bold_ceil_center"]),
        ('X{r}:AP{r}'.format(r=t_st), balance_state,
         configs["b_table_bold_ceil_center"]),

        ('K{r}:Q{r}'.format(r=t_st + 2), tenant_data['accountant_pos'],
         configs["b_normal_left"]),
        ('R{r}:AB{r}'.format(r=t_st + 2), "", configs["b_table_bold_ceil"]),
        ('AD{r}:AP{r}'.format(r=t_st + 2), tenant_data['accountant_name'],
         configs["b_normal_left"]),
    )
    __create_table(footer_data, worksheet)


def create_xlsx(tenant_data):
    """Формирование содержимого файла xlsx отчёта"""

    output = BytesIO()
    workbook = xlsxwriter.Workbook(
        output, {'in_memory': True, 'constant_memory': True}
    )
    # Конфиги стилей данных листа
    font = 'Times New Roman'
    configs = {
        "title": workbook.add_format({
            'bold': 1,
            'font_size': 9,
            'valign': 'bottom',
            'align': 'left',
            'font_name': font
        }),
        "title_center": workbook.add_format({
            'bold': 0,
            'font_size': 9,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font
        }),
        "normal_left": workbook.add_format({
            'font_size': 9,
            'valign': 'bottom',
            'align': 'left',
            'font_name': font,
        }),
        "normal_left_border": workbook.add_format({
            'font_size': 9,
            'valign': 'bottom',
            'align': 'left',
            'font_name': font,
            'bottom': 1,
        }),
        "normal_c_border": workbook.add_format({
            'font_size': 9,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font,
            'bottom': 1,
        }),
        "normal_right": workbook.add_format({
            'font_size': 9,
            'valign': 'bottom',
            'align': 'right',
            'font_name': font,
        }),
        "normal_center": workbook.add_format({
            'font_size': 9,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font,
        }),

        "table_title_ceil": workbook.add_format({
            'bold': 1,
            'font_size': 9,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'shrink': True
        }),
        "table_title_ceil_left": workbook.add_format({
            'font_size': 9,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'left',
            'font_name': font,
            'border': 1
        }),
        "table_bold_ceil": workbook.add_format({
            'bold': 1,
            'font_size': 9,
            'valign': 'bottom',
            'align': 'left',
            'font_name': font,
            'bottom': 1,
            'italic': 1
        }),
        "table_bold_ceil_center": workbook.add_format({
            'bold': 0,
            'text_wrap': True,
            'font_size': 9,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'shrink': True
        }),
        "t_bold_ceil_center_bot": workbook.add_format({
            'bold': 1,
            'text_wrap': True,
            'font_size': 9,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font,
            'bottom': 1
        }),
        "table_number": workbook.add_format({
            'font_size': 9,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'num_format': '0.00',
            'bold': 0
        }),
        "table_number_bold": workbook.add_format({
            'font_size': 9,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'num_format': '0.00',
            'bold': 1
        }),
        "b_title": workbook.add_format({
            'bold': 0,
            'font_size': 12,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font
        }),
        "b_title_bold_border": workbook.add_format({
            'bold': 1,
            'font_size': 10,
            'valign': 'bottom',
            'align': 'right',
            'font_name': font,
            'bottom': 1
        }),
        "b_title_center": workbook.add_format({
            'bold': 0,
            'font_size': 10,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font
        }),
        "b_normal_left": workbook.add_format({
            'font_size': 10,
            'valign': 'bottom',
            'align': 'left',
            'font_name': font,
            'shrink': 1
        }),
        "b_normal_right": workbook.add_format({
            'font_size': 10,
            'valign': 'bottom',
            'align': 'right',
            'font_name': font,
        }),
        "b_normal_center": workbook.add_format({
            'font_size': 10,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font,
        }),

        "b_table_title_ceil": workbook.add_format({
            'bold': 1,
            'font_size': 9,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'shrink': 1
        }),
        "b_t_title_right": workbook.add_format({
            'bold': 1,
            'font_size': 10,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'right',
            'font_name': font,
            'border': 1
        }),
        "b_t_title_center": workbook.add_format({
            'bold': 0,
            'font_size': 10,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1
        }),
        "b_t_title_left": workbook.add_format({
            'font_size': 10,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'left',
            'font_name': font,
            'border': 1,
            'shrink': 1
        }),
        "b_table_bold_ceil": workbook.add_format({
            'bold': 0,
            'font_size': 10,
            'valign': 'bottom',
            'align': 'left',
            'font_name': font,
            'shrink': 1
            # 'bottom': 1,
        }),
        "b_table_bold_ceil_center": workbook.add_format({
            'bold': 1,
            'font_size': 10,
            'valign': 'bottom',
            'align': 'center',
            'font_name': font,
            'bottom': 1
        }),
        "b_table_number": workbook.add_format({
            'font_size': 9,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'num_format': '0.00',
            'bold': 0,
            'shrink': 1
        }),
        "b_table_number_norm": workbook.add_format({
            'font_size': 10,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': font,
            'border': 1,
            'num_format': '0.00',
            'bold': 0
        }),
    }
    # Создание листа 1 с общей информацией
    worksheet = workbook.add_worksheet('Общая информация')
    worksheet.fit_to_pages(1, 0)
    create_base_sheet(worksheet, configs, tenant_data)

    # Создание листа 2 с информацией "ОСВ"
    worksheet = workbook.add_worksheet('Начисления и оплаты по услугам')
    worksheet.fit_to_pages(1, 0)
    create_balance_sheet(worksheet, configs, tenant_data)
    workbook.close()
    return output


def get_moscow_finance_report(tenant_id,
                              current_provider,
                              date_from=None,
                              date_till=None,
                              current_account=None,
                              binds=None):
    # Если не переданы, возьмем данные за прошлый месяц
    if not (date_from and date_till):
        date_till = datetime.now()
        date_from = dhf.start_of_day(
            date_till - relativedelta(months=1)
        )
        date_till = dhf.start_of_day(date_till) + relativedelta(days=1)
    else:
        date_from = dhf.start_of_day(date_from)
        date_till = dhf.start_of_day(date_till) + relativedelta(days=1)
    finance_report = get_fin_data(
        tenant_id=tenant_id,
        provider=current_provider,
        date_from=date_from,
        date_till=date_till,
        current_account=current_account,
        binds=binds
    )
    return create_xlsx(finance_report)


def _define_property(ps):
    # TODO это какой-то костыль, но локально ситуация не видна,
    #  а делать что-то нужно
    if not ps:
        return '0/0'

    ps_len = len(ps)
    if ps_len == 1 and 1 in ps:
        return '1/1'

    return f'ошибка!!!! {ps}'
