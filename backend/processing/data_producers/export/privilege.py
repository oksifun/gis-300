import datetime
import os
import xml.dom.minidom
import xml.etree.ElementTree as xmlET
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta
from mongoengine import DoesNotExist, NotUniqueError

import settings
from lib.archive import create_zip_file_in_gs
from lib.helpfull_tools import by_mongo_path
from app.accruals.cipca.source_data.areas import \
    get_areas_calculation_data, \
    get_mates
from processing.data_producers.associated.base import get_binded_houses
from app.house.models.house import House
from processing.models.billing.account import Account
from processing.models.billing.accrual import Accrual
from processing.models.billing.privilege import Privilege
from processing.models.billing.log import LogDbf
from processing.models.billing.tenant_data import TenantData
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES
from processing.models.references.moscow_gcjs import MoscowGCJSProviderData


class NoSettingsFound(Exception):
    pass


class NoAccruals(Exception):
    pass


def int_to_text(value, count):
    if not value:
        value = 0
    return str(value).rjust(count, '0')[0: count]


def str_to_text(value, count):
    if not value:
        value = ''
    return value.ljust(count)[0: count]


def float_to_text(value, count, count2):
    if not value:
        value = 0.0
    return str(round(
        value * (10 ** count2)
    )).rjust(count + count2, '0')[0: (count + count2)]


def date_to_text(value, count):
    if not value:
        return '0' * count
    return value.strftime('%d%m%Y').ljust(count, '0')[0: count]


def month_to_text(value, count):
    if not value:
        return '0' * count
    return value.strftime('%m%Y').ljust(count)[0: count]


def int_to_ptext(value, count):
    if not value:
        value = 0
    return str(value)[0: count]


def str_to_ptext(value, count):
    if not value:
        value = ' '
    return value[0: count]


def float_to_ptext(value, count, count2):
    if not value:
        value = 0
    return str(round(value * (10 ** count2)))[0: (count + count2)]


def date_to_ptext(value, count):
    if not value:
        return '0'
    return value.strftime('%d%m%Y')[0: count]


def month_to_ptext(value, count):
    if not value:
        return '0'
    return value.strftime('%m%Y')[0: count]


SEX_CODE = {
    'male': 'М',
    'female': 'Ж',
    'М': 'М',
    'Ж': 'Ж',
}
PROPERTY_CODE = {
    'private': 3,
    'government': 1,
    'municipal': 1,
}
ORG_TYPE_CODE = {
    'УК': 6,
    'ТСЖ': 4,
    'ЖСК': 3,
}
STOVE_CODE = {
    'electric': 2,
    'gas': 1,
}
INTERCOM_CODE = {
    'intercom': 3,
    'unlock': 2,
}
CALC_METHOD_CODE = {
    'meter': 2,
    'average': 0,
    'norma': 0,
    'norma_wom': 0,
    'meter_wo': 0,
    'nothing': 0,
    'house_meter': 1,
}
SERVICE_CODE = {
    '526234c0e0e34c4743822341': 35,  # хв
    '5936af7ccd3024006a086e66': 32,  # хв для гв
    # отоп
    '526234c0e0e34c4743822338': {
        'default': 33,
        CALC_METHOD_CODE['meter']: 73
    },
    '526234c0e0e34c4743822326': 33,  # отоп
    '526234c0e0e34c474382232f': 34,  # гв
    '526234c0e0e34c474382234d': 34,  # гв
    '526234c0e0e34c4743822335': 36,  # кан
    '526234c0e0e34c4743822334': 36,  # кан
    '526234c0e0e34c4743822333': 36,  # кан
    '526234c0e0e34c4743822344': 157,  # ээ день
    '526234c0e0e34c4743822346': 158,  # ээ ночь
    '526234c0e0e34c4743822345': 154,  # ээ однотарифная
    '56fa5c01401aac2a8a522e95': 154,  # ээ пик
    '56fa5c0c401aac2a8a522e96': 155,  # ээ полупик
    '526234c0e0e34c474382233d': 2,  # сои
    '526234c0e0e34c474382233a': 10,  # пзу
    '526234c0e0e34c4743822325': 193,  # кап.ремонт
    '526234c0e0e34c474382232e': 256,  # вывоз мусора
    # '5a2f42f0f6a3ff0001495834': 11,  # добровольное страхование
}
ID_DOC_CODE = {
    'passport': 1,
    'birth': 2,
    'warrior_officer': 3,
    'warrior_officer_reserve': 4,
    'warrior_soldier': 4,
    'alien_guest': 5,
    'other': 9
}
PRIVILEGE_DOC_TYPE_CODE = {
    'hero': 1,
    'medal_glory': 2,
    'hero_labour_ussr': 3,
    'medal_labour_glory': 4,
    'hero_labour': 5,
    'gdw_disabled': 10,
    'privilege_disabled': 11,
    'gdw_participant': 12,
    'gdw_veteran': 13,
    'gdw_freelancer': 14,
    'gdw_partisan': 15,
    'medal_leningrad_defence': 16,
    'privilege_moscow_defence': 17,
    'medal_moscow_defence': 18,
    'sign_leningrad_siege': 19,
    'privilege_veteran': 20,
    'veteran_war': 21,
    'veteran_war_relative': 22,
    'pension_earner_lost': 23,
    'concentration_camp': 24,
    'rehabilitated': 40,
    'repressions1': 41,
    'repressions2': 42,
    'chernobyl_diseased': 50,
    'chernobyl_liquidator': 51,
    'chernobyl_victim': 52,
    'veteran_especial_risk': 53,
    'especial_risk_relative': 54,
    'mayak_victim': 55,
    'mayak_liquidator': 56,
    'semipalatinsk_victim': 57,
    'donor': 68,
    'donor_moscow': 99,
    'donor_russian': 70,
    'large_family': 71,
    'medical_certificate': 72,
    'labour_veteran': 73,
    'veteran': 74,
    'privilege_certificate1': 75,
    'privilege_certificate2': 76,
    'privilege_certificate3': 77,
    'pension': 78,
    'school_certificate': 79,
    'marriage': 80,
    'council_document': 81,
    'public_care': 82,
    'pension_insurance': 83,
}
DEBTS_COUNT_MAX = 99


class PrivilegesExportMoscow:

    def __init__(self, provider_id, month, sector_code, provider_name=None):
        self.provider_name = provider_name
        self.provider = provider_id
        self.export_phone_number = True
        self.month = month
        self.sector_code = ([sector_code]
                            if not isinstance(sector_code, list)
                            else sector_code)
        self.org_type = 'УК'
        self.categories = {}
        self.gcjs_settings = list(MoscowGCJSProviderData.objects.filter(
            provider=provider_id,
        ))
        if not self.gcjs_settings:
            raise DoesNotExist()

    def get_files_data(self, strings_data, gcjs_settings):
        """
        Преобразует конечные данные в байты, а также формирует наименования
        файлов
        """
        result = []
        for k, v in strings_data.items():
            filename = self._get_filename(k, gcjs_settings)
            encoding = 'utf-8' if filename.split('.')[-1] == 'xml' else' cp866'
            result.append({
                'filename': filename,
                'bytes': v.encode(encoding=encoding)
            })
        return result

    def save_to_files(self, data, path=''):
        """
        Сохраняет данные в файлы на диске
        """
        for d in data:
            p = path if path.endswith('.txt') else path + d['filename']
            with open(p, 'wb') as f:
                f.write(d['bytes'])

    def get_type1_strings(self, data, gcjs_settings):
        """
        Преобразует данные льготников в строки в соответствии с шаблоном файлов
        ГЦЖС "ТИП1", "ТИП2", "ТИП3" и "ТИП4"
        """
        result = []
        total_type1_count = len(data)
        total_type2_count = 0
        total_type3_count = 0
        total_type3_value = 0
        for d in data.values():
            strings, t2_count, t3_count, t3_value = self._get_tenant_strings(d)
            result.extend(strings)
            total_type2_count += t2_count
            total_type3_count += t3_count
            total_type3_value += t3_value
        result.append('4{}{}{}{}{}'.format(
            int_to_text(gcjs_settings.contract_number or 0, 7),
            int_to_text(total_type1_count, 8),
            int_to_text(total_type2_count, 8),
            int_to_text(total_type3_count, 8),
            float_to_text(total_type3_value, 10, 2),
        ))
        # Для Сводная ведомость (отчет о выпадающих доходах).xlsx
        self.xlsx_consolidation_report_summary_writes = len(result)
        self.xlsx_consolidation_report_check_sum = total_type3_value
        return result

    def get_type1_xml(self, data, gcjs_settings):
        """
        Преобразует данные льготников в строки в соответствии с шаблоном файлов
        нового типа (.xml)
        """
        # Подсчет контрольных сумм
        total_type1_count = 0
        total_type2_count = 0
        total_type3_count = 0
        total_type3_value = 0.
        for tenant in (x for x in data.values()):
            total_type1_count += 1
            for prv in tenant['privileges']:
                total_type2_count += 1
                for accrual in prv.get('accruals', []):
                    total_type3_count += 1
                    total_type3_value += accrual['value']
        total_type3_value = round(total_type3_value, 2)

        xml_file = self._create_xml(
            data=data,
            contract_number=gcjs_settings.contract_number,
            total_type1_count=total_type1_count,
            total_type2_count=total_type2_count,
            total_type3_count=total_type3_count,
            total_type3_value=total_type3_value
        )
        # Для Сводная ведомость (отчет о выпадающих доходах).xlsx
        self.xlsx_consolidation_report_summary_writes = total_type1_count
        self.xlsx_consolidation_report_check_sum = total_type3_value
        return xml_file

    def _create_xml(self, data, contract_number,
                    total_type1_count, total_type2_count,
                    total_type3_count, total_type3_value):
        """
        Метод создания XML файла.
        Ниже представлены схемы, где есть имя поле и значение/функция,
         которая применится к переданным данным
        """

        root_name = 'Report'
        # Общие поля
        tenant_identifiers = (
            ('SNILS', lambda x: x['snils']),
            ('Name1', lambda x: x['last_name']),
            ('Name2 ', lambda x: x['first_name']),
            ('Name3', lambda x: x['patronymic_name']),
            ('Gender', lambda x: x['sex']),
            (
                'Birthday',
                lambda x: (
                    x['birth_date'].strftime('%Y-%m-%d')
                    if x['birth_date'] else ''
                )
            ),
            ('OwnSquare ', lambda x: '0'),  # TODO Можно дополнить
        )

        # Схема сборки XML
        title_schema = (
            ('DateCreate', datetime.datetime.now().strftime('%Y-%m-%d')),
            ('Dognum', contract_number or ''),
            ('ReportType', 0),
            ('BnfMonth', self.month.strftime('%Y-%m-%d')),
            ('Check1', total_type1_count),
            ('Check2', total_type2_count),
            ('Check3', total_type3_count),
            ('Check4', total_type3_value),
        )
        beneficiary_schema = (
            ('MoID', lambda x: x['district_code']),
            ('PayID ', lambda x: '0'),
            ('NUMLS', lambda x: x['householder_number']),
            *tenant_identifiers,
            ('StreetID', lambda x: x["street_code"]),
            ('HouseNum', lambda x: x['house_number']),
            ('CorpusNum ', lambda x: x['house_bulk']),
            ('BuildingNum', lambda x: x['house_structure']),
            ('Flat', lambda x: x['flat_number']),
            ('Phone', lambda x: x['phone_number']),
            ('OccupType', lambda x: '1'),
            ('OwnProperty', lambda x: x['property_type']),
            ('PPLReg', lambda x: x['mates_registered']),
            ('PPLCnt', lambda x: x['mates_living']),
            ('TotalSquare   ', lambda x: x['area_total']),
            ('LivingSquare', lambda x: x['area_living']),
            ('RegType', lambda x: x['living_type']),
            ('LivingType', lambda x: x['living_type']),
            ('DocType', lambda x: x.get('id_doc_type', '')),
            ('DocSeries', lambda x: x.get('id_doc_series', '')),
            ('DocNumber', lambda x: x.get('id_doc_number', '')),
            ('DocDate', lambda x: (
                x['id_doc_date'].strftime('%Y-%m-%d')
                if x.get('id_doc_date')
                else ''
            )),
            ('DocOrg', lambda x: x.get('id_doc_issuer', '')),
            # Вложенные поля
            # FamilyMembers
            (
                'FamilyMembers',  # Родительское имя
                '__nested__',  # Говорит, что поле вложенное
                'FamilyMember',  # Имя чайлда
                # TODO Нарочно убрано privileges.[0].accounts и
                #  поставлена заглушка
                'PLUG',  # Путь к интересующему полю данных
                # Поля для каждого чайлда и то, что должны вернуть
                (
                    *tenant_identifiers,
                    ('FamilyRelation', self.__get_family_relation),
                )
            ),
            # Categories
            (
                'Categories',  # Родительское имя
                '__nested__',  # Говорит, что поле вложенное
                'Category',  # Имя чайлда
                'privileges',  # Путь к интересующему полю данных
                # Поля для каждого чайлда и то, что должны вернуть
                (
                    ('BenefitID', lambda x: x['privilege_code']),
                    # Documents
                    (
                        'Documents',  # Родительское имя
                        '__nested__',  # Говорит, что поле вложенное
                        'Document',  # Имя чайлда
                        'docs',  # Путь к интересующему полю данных
                        # Поля для каждого чайлда и то, что должны вернуть
                        (
                            ('DocType',
                             lambda x: PRIVILEGE_DOC_TYPE_CODE[x['doc_type']]),
                            ('DocSeries', lambda x: (x.get('series') or '')),
                            ('DocNumber', lambda x: x['number']),
                            (
                                'DocDate',
                                lambda x: (
                                    x['date_from'].strftime('%Y-%m-%d')
                                    if x.get('date_from')
                                    else ''
                                )
                            ),
                            ('DocOrg', lambda x: x['issuer']),
                        )
                    ),
                    (
                        'Services',  # Родительское имя
                        '__nested__',  # Говорит, что поле вложенное
                        'Service',  # Имя чайлда
                        'accruals',  # Путь к интересующему полю данных
                        # Поля для каждого чайлда и то, что должны вернуть
                        (
                            ('KBK', lambda x: ''),
                            ('ServiceID', lambda x: x['service_code']),
                            ('Tariff', lambda x: x['tariff']),
                            ('ConsumerQty',
                             lambda x: x['privilege_count']),
                            (
                                'Quant',
                                lambda x: f'{x["privilege_consumption"]:.6f}'
                            ),
                            ('BnfSquare', lambda x: x['privilege_area']),
                            ('Summa', lambda x: x['value']),
                            ('TotalQuant',
                             lambda x: f'{x["privilege_consumption"]:.6f}'),
                        )
                    ),
                ),
            ),
        )
        # Создание корня
        attributes = {
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns": "http://www.jaxb.msp/report/IncomeReport"
        }
        root = xmlET.Element(root_name, attrib=attributes)
        # Создание шапки
        for row in title_schema:
            self.__set_xml_row(root, row)

        # Построение тела документа
        beneficiaries = xmlET.SubElement(root, 'Beneficiaries')
        for tenant in (x for x in data.values()):
            beneficiary = xmlET.SubElement(beneficiaries, 'Beneficiary')
            for row in beneficiary_schema:
                self._create_schema(beneficiary, row, tenant)

        # Сохранение
        tree = xmlET.ElementTree(root)
        buffer = BytesIO()
        tree.write(buffer, encoding='utf-8')

        # Приведем к красивому и удобочитаемому виду
        dom = xml.dom.minidom.parseString(buffer.getvalue().decode('utf-8'))
        pretty_xml_as_string = dom.toprettyxml()

        return pretty_xml_as_string

    def _create_schema(self, level, row, data):
        """Построение схемы"""

        if '__nested__' not in row:
            self.__set_xml_row_value(level, row, data)
        else:
            level = xmlET.SubElement(level, row[0])
            for nested_field in by_mongo_path(data, row[3], []):
                sub_level = xmlET.SubElement(level, row[2])
                for sub_row in row[4]:
                    self._create_schema(sub_level, sub_row, nested_field)

    def __set_xml_row(self, xml_obj, row):
        """Устанавливает значение из схемы"""
        attr = xmlET.SubElement(xml_obj, row[0])
        attr.text = str(row[1])

    def __set_xml_row_value(self, xml_obj, row, data_obj):
        """Устанавливает значение, примения к нему функцию"""
        attr = xmlET.SubElement(xml_obj, row[0])
        attr.text = str(row[1](data_obj))

    def __get_family_relation(self, data):
        """Получение значений для раздела FamilyRelation"""
        return ''  # TODO Реализовать, если нужно

    def get_p1a_strings(self, data, org_code):
        """
        Преобразует данные начислений в строки в соответствии с шаблоном файлов
        ГЦЖС "Приложение 1А"
        """
        date = datetime.datetime.now().strftime('%d%m%Y')
        result = []
        for d in data.values():
            result.append('{}\t{}\t{}\t{}'.format(
                date,
                org_code,
                org_code,
                '\t'.join(
                    [s[1](d.get(s[0], ''), *s[2]) for s in self.P_1A_SCHEMA]
                )
            ))
        self.xlsx_type_a_cs1 = sum([v['accrual_total_value']
                                    for k, v in data.items()])
        self.xlsx_type_a_cs2 = sum([v['accrual_total_value_privilege']
                                    for k, v in data.items()])
        self.xlsx_type_a_len = len(result)
        return result

    def get_p1b_strings(self, data, org_code):
        """
        Преобразует данные начислений в строки в соответствии с шаблоном файлов
        ГЦЖС "Приложение 1Б"
        """
        date = datetime.datetime.now().strftime('%d%m%Y')
        result = []
        for d in data.values():
            for a in d.get('accruals', []):
                result.append('{}\t{}\t{}'.format(
                    date,
                    org_code,
                    '\t'.join([
                        s[1](a.get(s[0]) or d.get(s[0], ''), *s[2])
                        for s in self.P_1B_SCHEMA
                    ])
                ))
        self.xlsx_type_b_cs1 = self._accruals_summation(data,
                                                        sum_key="value")
        self.xlsx_type_b_cs2 = self._accruals_summation(
            data,
            sum_key="value_privilege"
        )
        self.xlsx_type_b_len = len(result)
        return result

    def get_p1v_strings(self, data, org_code):
        """
        Преобразует данные начислений в строки в соответствии с шаблоном файлов
        ГЦЖС "Приложение 1В"
        """
        date = datetime.datetime.now().strftime('%d%m%Y')
        result = []
        for d in data.values():
            for m in d.get('mates', []):
                result.append('{}\t{}\t{}'.format(
                    date,
                    org_code,
                    '\t'.join([
                        s[1](m.get(s[0], ''), *s[2])
                        for s in self.P_1V_SCHEMA
                    ])
                ))
        self.xlsx_type_v_len = len(result)
        return result

    def get_strings(self, gcjs_settings, data):
        """
        Преобразует данные в строки по всем возможным шаблонам файлов ГЦЖС
        """
        return {
            'type1': '\n'.join(self.get_type1_strings(
                data['privilegers'], gcjs_settings
            )),
            'p1a': '\n'.join(self.get_p1a_strings(
                data['householders'], gcjs_settings.provider_code
            )),
            'p1b': '\n'.join(self.get_p1b_strings(
                data['householders'], gcjs_settings.provider_code
            )),
            'p1v': '\n'.join(self.get_p1v_strings(
                data['householders'], gcjs_settings.provider_code
            )),
        }

    def _cut_not_found_areas(self, tenants, areas):
        return {k: v for k, v in tenants.items() if v['area']['_id'] in areas}

    def get_raw_data(self, houses_ids, house_codes, export_settings):
        """
        Получает исходные данные по льготникам, жителям, квартирам, начислениям
        """
        privilegers = self._get_tenants(houses_ids)
        self.categories = self._extract_privileges(privilegers)
        houses = self._get_houses(privilegers)
        areas = self._get_areas_accrualed(houses)
        privilegers = self._cut_not_found_areas(privilegers, areas)
        if not areas:
            return {'privilegers': {}, 'householders': {}}

        householders = self._get_householders(areas)
        accruals = self._get_accruals(householders)
        # данные льготников
        self._prepare_area_data(privilegers, areas, export_settings)
        self._mates_to_privilegers(householders, privilegers)
        self._prepare_tenants_data(privilegers)
        self._prepare_house_data(privilegers, houses, house_codes)
        self._prepare_privilege_accruals(privilegers, accruals)
        # данные плательщиков
        self._prepare_area_data(householders, areas, export_settings)
        self._prepare_tenants_data(householders)
        self._prepare_house_data(householders, houses, house_codes)
        self._prepare_accruals(householders, accruals)
        householders = {k: v for k, v in householders.items() if v['accruals']}
        self._prepare_debts(householders)
        householders = {
            k: v for k, v in householders.items()
            if v['debts_count'] < DEBTS_COUNT_MAX
        }
        return {'privilegers': privilegers, 'householders': householders}

    def _get_binded_houses(self, houses_ids):
        binded = get_binded_houses(self.provider)
        return list(set(binded) & set(houses_ids))

    def _get_tenants(self, houses_ids):
        houses = self._get_binded_houses(houses_ids)
        aggregation_pipeline = [
            {
                '$match': {
                    'area.house._id': {'$in': houses},
                    'is_privileged': True,
                    'is_deleted': {'$ne': True},
                    '_type': 'PrivateTenant',
                },
            },
            {
                '$lookup': {
                    'from': 'AreaBind',
                    'localField': 'area._id',
                    'foreignField': 'area',
                    'as': 'bind',
                },
            },
            {
                '$unwind': '$bind',
            },
            {
                '$match': {
                    'bind.provider': self.provider,
                    'bind.close': None,
                },
            },
            {
                '$group': {
                    '_id': '$_id',
                    'last_name': {'$first': '$last_name'},
                    'first_name': {'$first': '$first_name'},
                    'patronymic_name': {'$first': '$patronymic_name'},
                    'privileges': {'$first': '$privileges'},
                    'phone_numbers': {'$first': '$phone_numbers'},
                    'snils': {'$first': '$snils'},
                    'area': {'$first': '$area'},
                    'sex': {'$first': '$sex'},
                    'number': {'$first': '$number'},
                    'family': {'$first': '$family'},
                    'birth_date': {'$first': '$birth_date'},
                    'registration': {'$first': '$statuses.registration'},
                    'payer_code': {'$first': '$privileges_info.kodpol'},
                },
            },
        ]
        tenants = list(Account.objects.aggregate(*aggregation_pipeline))
        tenants = [x for x in tenants if self._has_registration(x)]
        result = {}
        for tenant in tenants:
            active_privileges = []
            if not tenant.get('privileges'):
                continue
            for p in tenant['privileges']:
                if (
                        (p.get('date_from') or self.month)
                        <= self.month
                        <= (p.get('date_till') or self.month)
                ):
                    active_privileges.append(p)
            if active_privileges:
                tenant['privileges'] = active_privileges
                result[tenant['_id']] = tenant
        return result

    def _has_registration(self, tenant):
        # Проверка регистрации льготника
        # на определенный период
        for reg_data in tenant['registration']:
            if reg_data['date_from'] <= self.month:
                date_till = reg_data.get('date_till')
                if not date_till:
                    return True
                else:
                    if date_till >= self.month:
                        return True

    def _get_householders(self, areas):
        hh_mates = get_mates(
            self.month,
            self.provider,
            areas,
            extra_tenant_data=True,
        )
        hhs = (
            y
            for x in hh_mates.values()
            for y in x['mates']
            if y['summary']['is_householder'] and 'PrivateTenant' in y['_type']
        )
        result = {}
        for hh in hhs:
            hh_data = hh_mates[hh['_id']]
            hh['mates_registered'] = hh_data['summary']['registered']
            hh['mates_living'] = hh_data['summary']['living']
            hh['mates_total'] = len(hh_data['mates'])
            hh['mates'] = hh_data['mates']
            result[hh['_id']] = hh
        return result

    def _get_houses(self, tenants):
        ids = {t['area']['house']['_id'] for t in tenants.values()}
        houses = House.objects.filter(id__in=list(ids)).as_pymongo()
        return {h['_id']: h for h in houses}

    def _get_areas_of_tenants(self, tenants):
        ids = {t['area']['_id'] for t in tenants.values()}
        return get_areas_calculation_data(self.month, list(ids))

    def _get_areas_accrualed(self, houses):
        ids = Accrual.objects.filter(
            __raw__={
                'account.area.house._id': {'$in': list(houses.keys())},
                'month': self.month,
                'sector_code': {'$in': self.sector_code},
                'owner': self.provider,
                'is_deleted': {'$ne': True},
            },
        ).distinct(
            'account.area._id',
        )
        return get_areas_calculation_data(
            self.month,
            list(ids),
            area_type='LivingArea',
        )

    def _get_accruals(self, tenants):
        accruals = Accrual.objects.filter(
            __raw__={
                'month': self.month,
                'sector_code': {'$in': self.sector_code},
                'account._id': {'$in': list(tenants.keys())},
                'owner': self.provider,
                'is_deleted': {'$ne': True}
            }
        ).as_pymongo()
        return list(accruals)

    def _prepare_house_data(self, tenants, houses, gcjs_settings):
        for t in tenants.values():
            h = houses[t['area']['house']['_id']]
            t['house_number'] = h['number']
            t['house_bulk'] = h.get('bulk', '')
            t['house_structure'] = h['structure']
            t['housing_fund'] = ORG_TYPE_CODE[self.org_type]
            for setting in gcjs_settings:
                if setting.house.id == h['_id']:
                    t['district_code'] = setting.district_code
                    t['street_code'] = setting.street_code
                    t['street_code_BTI'] = setting.street_code_BTI
                    t['house_code_BTI'] = setting.house_code_BTI

    def _prepare_area_data(self, tenants, areas, gcjs_settings):
        for t in tenants.values():
            t['flat_number'] = str(t['area']['number'])
            t['area_total'] = areas[t['area']['_id']]['area_total']
            t['area_living'] = areas[t['area']['_id']]['area_living']
            t['living_type'] = 2 if t['area'].get('is_shared') else 1
            t['stove_type'] = STOVE_CODE.get(
                areas[t['area']['_id']].get('stove_type', 'electric'), 2
            )
            if gcjs_settings.intercom_export:
                t['intercom_type'] = INTERCOM_CODE.get(
                    areas[t['area']['_id']].get('intercom'), 0
                )

    def _prepare_tenants_data(self, tenants):
        t_data = TenantData.objects.filter(
            tenant__in=list(tenants.keys())).as_pymongo()
        t_data = {t['tenant']: t for t in t_data}
        for t in tenants.values():
            if not t.get('payer_code') and t.get('privileges_info'):
                t['payer_code'] = t['privileges_info'].get('kodpol')
            t['month'] = self.month
            t['phone_number'] = 0
            if self.export_phone_number and t.get('phone_numbers'):
                p_num = '8{}{}'.format(
                    t['phone_numbers'][0]['code'],
                    t['phone_numbers'][0]['number']
                )
                if p_num.isdigit():
                    t['phone_number'] = int(p_num)
            t['sex'] = SEX_CODE.get(t.get('sex'))
            if t.get('statuses') and t['statuses'].get('ownership'):
                t['property_type'] = \
                    PROPERTY_CODE[t['statuses']['ownership']['type']]
            else:
                t['property_type'] = 3
            if t['_id'] in t_data:
                # Проверка на наличие паспорта РФ. Если он не задан
                # будет выбран другой документ.
                if t_data[t['_id']].get('passport') \
                        and t_data[t['_id']]['passport'].get('number'):
                    id_doc = t_data[t['_id']]['passport']
                    id_doc['doc_type'] = 'passport'
                elif t_data[t['_id']].get('id_docs'):
                    id_doc = t_data[t['_id']]['id_docs'][0]
                else:
                    id_doc = None
                if id_doc and id_doc.get('number') and id_doc.get('issuer'):
                    t['id_doc_type'] = ID_DOC_CODE.get(id_doc['doc_type'])
                    t['id_doc_series'] = id_doc['series']
                    t['id_doc_number'] = id_doc['number']
                    t['id_doc_date'] = id_doc.get('date')
                    t['id_doc_issuer'] = id_doc['issuer']
                p_docs = {}
                for p_doc in t_data[t['_id']].get('privilege_docs', []):
                    p_docs.setdefault(p_doc.get('privilege'), [])
                    p_docs[p_doc.get('privilege')].append(p_doc)
                for p in t.get('privileges') or []:
                    p['docs'] = []
                    for p_doc in p_docs.get(p['privilege'], []):
                        p_doc['type'] = PRIVILEGE_DOC_TYPE_CODE.get(p_doc['doc_type'], 0)
                        p['docs'].append(p_doc)
            if t.get('mates'):
                for ix, m in enumerate(t['mates'], start=1):
                    m['ix'] = ix
                    m['month'] = self.month
                    m['householder_number'] = t['number']
                    m['owner'] = m['summary'].get('ownership', 0)
                    m['area_total'] = t['area_total'] * \
                                      m['summary'].get('property_share', 0)
                    m['registration_type'] = int(bool(
                        m['summary'].get('registered', 0) +
                        m['summary'].get('registered_const', 0)
                    ))
                    m['registration_date_start'] = m['summary'].get('reg_start')
                    m['registration_date_finish'] = \
                        m['summary'].get('reg_finish')
                    m['living'] = m['summary'].get('living', 0)
                    m['sex'] = SEX_CODE.get(m.get('sex'))
            if t.get('privileges'):
                for p in t['privileges']:
                    category = self.categories.get(p['privilege'])
                    p['privilege_code'] = category[0] if category else None

    def _prepare_privilege_accruals(self, tenants, accruals):
        for a in accruals:
            for s in a['services']:
                if str(s['service_type']) not in SERVICE_CODE:
                    continue
                c_type = CALC_METHOD_CODE.get(s.get('method'), 0)
                for p in s['privileges']:
                    if p['tenant'] not in tenants:
                        continue
                    t = tenants[p['tenant']]
                    t['month'] = self.month
                    for privilege in t['privileges']:
                        privilege.setdefault('accruals', [])
                        if privilege['privilege'] == p['category']:
                            p_data = {
                                'month': self.month,
                                'service_code': self._get_service_code(
                                    service_type=str(s['service_type']),
                                    c_type=c_type
                                ),
                                'tariff': s['tariff'] / 100,
                                'privilege_count': p.get('count', 1),
                                'privilege_consumption': p.get('consumption'),
                                'privilege_area': p.get('area'),
                                'value': -p['value'] / 100,
                                'consumption': s['consumption'],
                                'calculation_type': c_type
                            }
                            privilege['accruals'].append(p_data)

    def _get_service_code(self, service_type: str, c_type: int):
        code_value = SERVICE_CODE.get(service_type, 0)
        if isinstance(code_value, dict):
            code_value = code_value.get(c_type, code_value['default'])
        return code_value

    def _prepare_accruals(self, tenants, accruals):
        keys_dict = dict(
            accrual_total_value='value',
            accrual_total_value_privilege='value_privilege',
            accrual_registered_value='registered_value',
            accrual_registered_value_privilege='registered_value_privilege')
        for t in tenants.values():
            t['month'] = self.month
            for key in keys_dict.keys():
                t[key] = 0
            t['accruals'] = []
        for a in accruals:
            t = tenants[a['account']['_id']]
            a_dict = {}
            for s in a['services']:
                if str(s['service_type']) not in SERVICE_CODE:
                    continue
                val_priv = max(0, s['value'] + s['totals']['privileges'])
                c_type = CALC_METHOD_CODE.get(s.get('method'), 0)
                service_code = self._get_service_code(
                    service_type=str(s['service_type']),
                    c_type=c_type
                )
                s_data = a_dict.setdefault(
                    service_code,
                    {
                        'month': self.month,
                        'service_code': service_code,
                        'tariff': s['tariff'] / 100,
                        'value': 0,
                        'registered_value': 0,
                        'value_privilege': 0,
                        'registered_value_privilege': 0,
                        'consumption': 0,
                        'calculation_type': c_type,
                    }
                )
                s_data['value'] += max(0, s['value'] / 100)
                s_data['registered_value'] += max(0, s['value'] / 100)
                s_data['value_privilege'] += val_priv / 100
                s_data['registered_value_privilege'] += val_priv / 100
                s_data['consumption'] += max(0, s['consumption'])
            for key_t, key_a in keys_dict.items():
                t[key_t] = sum(a[key_a] for a in a_dict.values())
            t['accruals'].extend(list(a_dict.values()))

    def _get_debts(self, tenants):
        # начисления по предыдущий месяц
        a_pipeline = [
            {'$match': {
                'account._id': {'$in': list(tenants.keys())},
                'is_deleted': {'$ne': True},
                'month': {'$lt': self.month - relativedelta(months=1)},
                'sector_code': {'$in': self.sector_code},
                'doc.status': {'$in': ['ready', 'edit']},
                'owner': self.provider,
                'repaid_at': None,
                'unpaid_services': {'$nin': [None, []]}
            }},
            {'$unwind': '$unpaid_services'},
            {'$group': {
                '_id': {'a': '$account._id', 's': '$sector_code'},
                'val': {'$sum': '$unpaid_services.value'},
            }},
            {'$match': {'val': {'$gt': 0}}},
        ]
        debts = list(Accrual.objects.aggregate(*a_pipeline))
        # оплаты по сегодня
        a_pipeline = [
            {'$match': {
                'account._id': {'$in': [d['_id']['a'] for d in debts]},
                'is_deleted': {'$ne': True},
                'sector_code': {'$in': self.sector_code},
                'month': {
                    '$lte': self.month - relativedelta(months=1),
                    '$gte': self.month - relativedelta(months=4),
                },
                'doc.status': {'$in': ['ready', 'edit']},
                'owner': self.provider,
            }},
            {'$unwind': '$unpaid_services'},
            {'$group': {
                '_id': {'a': '$account._id', 's': '$sector_code'},
                'val': {'$sum': '$value'},
                'count': {'$sum': 1},
            }},
            {'$match': {'val': {'$gt': 0}, 'count': {'$gt': 0}}},
        ]
        accruals = list(Accrual.objects.aggregate(*a_pipeline))
        accruals = {
            (a['_id']['a'], a['_id']['s']): a['val'] / a['count']
            for a in accruals
        }
        result = {}
        for d in debts:
            key = (d['_id']['a'], d['_id']['s'])
            if accruals.get(key):
                result[key] = d['val'] / accruals[key]
            else:
                result[key] = 1
        return result

    def _prepare_debts(self, tenants):
        debts = self._get_debts(tenants)
        for t in tenants.values():
            t['debts_count'] = debts.get((t['_id'], 'rent'), 0)

    def _mates_to_privilegers(self, householders, privilegers):
        hh_dict = {
            m['_id']: hh for hh in householders.values() for m in hh['mates']
        }
        for t in privilegers.values():
            t_hh = hh_dict.get(t['_id'])
            if t_hh:
                t['mates_living'] = t_hh['mates_living']
                t['mates_registered'] = t_hh['mates_registered']
                t['mates_total'] = t_hh['mates_total']
                t['householder_number'] = t_hh['number']
            # Если дружки не подтянулись ранее
            else:
                area = {t['area']['_id']: 1}
                # Подтянем дружков дополнительно
                extra_mates = get_mates(
                    self.month,
                    self.provider,
                    area,
                    extra_tenant_data=True,
                )
                extra_mates = {
                    m['_id']: hh
                    for hh in extra_mates.values()
                    for m in hh['mates']
                }
                t_hh = extra_mates[t['_id']]
                t['mates_living'] = t_hh['summary']['registered']
                t['mates_registered'] = t_hh['summary']['living']
                t['mates_total'] = len(t_hh['mates'])
                t['householder_number'] = t['number']

    def _extract_privileges(self, privilegers):
        ids = {
            t['privilege']
            for x in privilegers.values()
            for t in x['privileges']
        }
        privileges = Privilege.objects(id__in=list(ids)).as_pymongo()
        return {
            p['_id']: [p.get('moscow_code'), p.get('title')]
            for p in privileges
        }

    TYPE_1_SCHEMA = (
        ('privileges_count', int_to_text, [2]),
        ('district_code', int_to_text, [3]),
        ('payer_code', int_to_text, [10]),
        ('householder_number', str_to_text, [20]),
        ('snils', str_to_text, [14]),
        ('last_name', str_to_text, [30]),
        ('first_name', str_to_text, [30]),
        ('patronymic_name', str_to_text, [30]),
        ('street_code', int_to_text, [5]),
        ('house_number', str_to_text, [8]),
        ('house_bulk', str_to_text, [6]),
        ('house_structure', str_to_text, [5]),
        ('flat_number', str_to_text, [10]),
        ('phone_number', int_to_text, [10]),
        ('housing_fund', int_to_text, [1]),
        ('living_type', int_to_text, [1]),
        ('property_type', int_to_text, [1]),
        ('mates_registered', int_to_text, [2]),
        ('mates_living', int_to_text, [2]),
        ('area_total', float_to_text, [4, 2]),
        ('area_living', float_to_text, [4, 2]),
        ('sex', str_to_text, [1]),
        ('birth_date', date_to_text, [8]),
        ('id_doc_type', int_to_text, [1]),
        ('id_doc_series', str_to_text, [8]),
        ('id_doc_number', int_to_text, [8]),
        ('id_doc_date', date_to_text, [8]),
        ('id_doc_issuer', str_to_text, [80]),
    )

    TYPE_2_SCHEMA = (
        ('data_count', int_to_text, [2]),
        ('privilege_code', int_to_text, [3]),
        ('doc1', str_to_text, [86]),
        ('doc2', str_to_text, [86]),
        ('doc3', str_to_text, [86]),
    )
    TYPE_2_DOC_SCHEMA = (
        ('type', int_to_text, [2]),
        ('series', str_to_text, [8]),
        ('number', str_to_text, [10]),
        ('date_from', date_to_text, [8]),
        ('date_till', date_to_text, [8]),
        ('issuer', str_to_text, [50]),
    )

    TYPE_3_SCHEMA = (
        ('month', month_to_text, [6]),
        ('service_code', int_to_text, [4]),
        ('tariff', float_to_text, [4, 2]),
        ('privilege_count', int_to_text, [2]),
        ('privilege_consumption', float_to_text, [4, 6]),
        ('privilege_area', float_to_text, [4, 2]),
        ('value', float_to_text, [7, 2]),
        ('consumption', float_to_text, [4, 6]),
        ('calculation_type', int_to_text, [1]),
    )

    P_1A_SCHEMA = (
        ('district_code', int_to_ptext, [3]),
        ('last_name', str_to_ptext, [35]),
        ('first_name', str_to_ptext, [20]),
        ('patronymic_name', str_to_ptext, [20]),
        ('street_code_BTI', int_to_ptext, [9]),
        ('house_number', str_to_ptext, [8]),
        ('house_structure', str_to_ptext, [6]),
        ('house_bulk', str_to_ptext, [5]),
        ('flat_number', str_to_ptext, [10]),
        ('payer_code', int_to_ptext, [10]),
        ('number', str_to_ptext, [20]),
        ('month', month_to_ptext, [6]),
        ('property_type', int_to_ptext, [1]),
        ('living_type', int_to_ptext, [1]),
        ('area_total', float_to_ptext, [9, 2]),
        ('mates_total', int_to_ptext, [2]),
        ('area_living', float_to_ptext, [9, 2]),
        ('intercom_type', int_to_ptext, [1]),
        ('stove_type', int_to_ptext, [1]),
        ('accrual_total_value', float_to_ptext, [9, 2]),
        ('accrual_total_value_privilege', float_to_ptext, [9, 2]),
        ('accrual_registered_value', float_to_ptext, [9, 2]),
        ('accrual_registered_value_privilege', float_to_ptext, [9, 2]),
        ('debts_count', float_to_ptext, [3, 1]),
        ('house_code_BTI', int_to_ptext, [9]),
        ('flat_code_BTI', int_to_ptext, [9]),
    )

    P_1B_SCHEMA = (
        ('number', str_to_ptext, [20]),
        ('payer_code', int_to_ptext, [10]),
        ('month', month_to_ptext, [6]),
        ('service_code', int_to_ptext, [3]),
        ('service_provider_code', int_to_ptext, [4]),
        ('consumption', float_to_ptext, [9, 3]),
        ('tariff', float_to_ptext, [9, 2]),
        ('value', float_to_ptext, [9, 2]),
        ('value_privilege', float_to_ptext, [9, 2]),
        ('registered_value', float_to_ptext, [9, 2]),
        ('registered_value_privilege', float_to_ptext, [9, 2]),
        ('calculation_type', int_to_ptext, [1]),
    )

    P_1V_SCHEMA = (
        ('payer_code', int_to_ptext, [10]),
        ('householder_number', str_to_ptext, [20]),
        ('month', month_to_ptext, [6]),
        ('ix', int_to_ptext, [2]),
        ('last_name', str_to_ptext, [35]),
        ('first_name', str_to_ptext, [20]),
        ('patronymic_name', str_to_ptext, [20]),
        ('birth_date', date_to_ptext, [8]),
        ('sex', str_to_ptext, [1]),
        ('relation', str_to_ptext, [30]),
        ('owner', int_to_ptext, [1]),
        ('area_total', float_to_ptext, [9, 2]),
        ('registration_type', int_to_ptext, [1]),
        ('registration_date_start', date_to_ptext, [8]),
        ('registration_date_finish', date_to_ptext, [8]),
        ('living', int_to_ptext, [1]),
        ('snils', str_to_ptext, [14]),
    )

    def _get_tenant_strings(self, tenant_data):
        tenant_data['privileges_count'] = len(tenant_data['privileges'])
        result = ['1' + ''.join(
            [s[1](tenant_data.get(s[0], ''), *s[2]) for s in self.TYPE_1_SCHEMA]
        )]
        type3_count = 0
        type3_value = 0
        for p in tenant_data['privileges']:
            p['doc1'] = ''
            p['doc2'] = ''
            p['doc3'] = ''
            for ix in range(1, 4):
                if p.get('docs') and ix <= len(p['docs']):
                    doc = p['docs'][ix - 1]
                else:
                    doc = {}
                p['doc{}'.format(ix)] = ''.join([
                    s[1](doc.get(s[0], ''), *s[2])
                    for s in self.TYPE_2_DOC_SCHEMA
                ])
            p['data_count'] = len(p.get('accruals', []))
            type3_count += p['data_count']
            result.append('2' + ''.join(
                [s[1](p.get(s[0], ''), *s[2]) for s in self.TYPE_2_SCHEMA]
            ))
            for a in p.get('accruals', []):
                type3_value += a.get('value', 0)
                # Коды услуг для которых будет всегда один пользующийся
                if a['service_code'] in (33, 154, 155, 158):
                    result.append('3' + ''.join(
                        [s[1](a.get(s[0], '') if s[0] != 'privilege_count'
                              else 1,
                              *s[2])
                         for s in self.TYPE_3_SCHEMA]
                    ))
                else:
                    result.append('3' + ''.join(
                        [s[1](a.get(s[0], ''), *s[2])
                         for s in self.TYPE_3_SCHEMA]
                    ))
        return result, len(tenant_data['privileges']), type3_count, type3_value

    FILE_NAME_PREFIXES = {
        'type1': '0901043',
        'p1a': 'P1',
        'p1b': 'P2',
        'p1v': 'P3',
    }

    def _get_filename(self, data_type, gcjs_settings):
        contract_number = gcjs_settings[0]
        provider_code = gcjs_settings[1]
        if data_type == 'type1':
            name = (
                f"bnf_{0}_{contract_number}_{self.month.strftime('%Y%m')}.xml"
            )
            self.xlsx_typy1_name = name
            return name
        else:
            name = '{}_{}_{}_{}.txt'.format(
                contract_number,
                self.FILE_NAME_PREFIXES[data_type],
                provider_code,
                self.month.strftime('%m%Y')
            )
            if data_type == "p1a":
                self.xlsx_type_a_name = name
            elif data_type == "p1b":
                self.xlsx_type_b_name = name
            elif data_type == "p1v":
                self.xlsx_type_v_name = name
            return name

    def _date_converter(self, date):
        """
        Получает строчку день и месяц из даты
        :param date: datetime object: дата
        :return: str: день и месяц
        """
        months = {
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
        month = int(date.strftime("%m"))
        year = date.strftime("%Y")
        return "{} {}".format(months.get(month), year)

    def _accruals_summation(self, data, sum_key):
        """
        Вычисляет сумму по accruals: value и value_privilege
        для документа типа P2
        """
        result = []
        for key, value in data.items():
            for ac in value["accruals"]:
                result.append(ac[sum_key])
        return sum(result)

    def _privilages_summation(self,
                              group_key,
                              exactly_group,
                              codes,
                              key="value"):
        """
        Вычисляет сумму по услугам для определенной группы льготьников
        из определенной льготной категории
        :param group_key: int - льготная категория
        :param exactly_group: list - список льготников льготной категории
        :param codes: list - список кодов услуг, по которым будет проходить суммирование
        :return: float - сумма по услугам
        """
        result = []
        # Для каждого льготника в группе
        for human in exactly_group:
            # Для каждой льготы человека
            for p in human["privileges"]:
                # Выбираем льготу относящуюся к льготной группе
                if p["privilege_code"] == group_key:
                    # Проходим по всем начислениям льготы
                    accruals = p.get("accruals")
                    # Если есть такое поле
                    if accruals:
                        for a in accruals:
                            if key == "privilege_count":
                                # Коды услуг для которых будет
                                # всегда один пользующийся
                                if a['service_code'] in (33, 154, 155, 158):
                                    result.append(1)
                                else:
                                    result.append(a[key])
                            else:
                                # Если код услуги в списке, то добавляем значение
                                # для будущего суммирования
                                if a["service_code"] in codes:
                                    result.append(a[key])
        return sum(result)

    def get_sorted_privilegers(self, privilegers):
        """
        Группировка жителей по льготным категориям и
        подготовка дял передачи построения отчета в Exel
        """
        # Получаем лист из льготных категорий
        privilegers_groups = list([[g['privilege_code'] for g in
                                    privilegers[x]["privileges"]]
                                   for x in privilegers.keys()])
        raw_list = []
        for elem in privilegers_groups:
            raw_list.extend(elem)
        # Подготовливаем словарь для данных с группами
        privilegers_groups = {x: [] for x in set(raw_list)}
        # Получаем название категорий
        privileges_code_names = {v[0]: v[1] for k, v in self.categories.items()}
        # Словарь для результата
        result = {x: {} for x in privilegers_groups}

        # Группируем льготников
        # для льготной категории
        for group in privilegers_groups:
            # Для каждого льготника из этой категории
            for human in privilegers:
                # Проходим по всем его льготам
                for p in privilegers[human]["privileges"]:
                    # Если код льготы совпал с кодом льготной группы
                    if p['privilege_code'] == group:
                        privilegers_groups[group].append(privilegers[human])

        for group_key in result.keys():
            # Получаем лист льготной группы для удобства
            exactly_group = privilegers_groups[group_key]
            # Количество льготников в группе
            privilegers_count = len(exactly_group)
            # Фактическая занимаемая площадь
            square_de_facto = sum([x["area_total"] for x in exactly_group])
            # Площадь, на которую рассчитываются льготы
            square_calculate = sum([x["area_living"] for x in exactly_group])
            # Содержание и ремонт жилья
            # на площадь: основную + дополнительную по сумме услуг 2, 43, 48
            repairs_2_43_48 = self._privilages_summation(group_key,
                                                         exactly_group,
                                                         [2, 43, 48])
            # на излишки площади по сумме услуг 45, 47
            repairs_45_47 = self._privilages_summation(group_key,
                                                       exactly_group,
                                                       [45, 47])
            # Плата за наем
            # по сумме услуг 1, 153
            recruiting = self._privilages_summation(group_key,
                                                    exactly_group,
                                                    [1, 153])
            # Вывоз бытовых отходов - 7
            rubbish = self._privilages_summation(group_key,
                                                 exactly_group,
                                                 [7])
            # Отопление на основную и дополнительную площадь,
            # а так же излишки площади
            # по сумме услуг 3, 16, 33, 42, 46, 73
            heating = self._privilages_summation(group_key,
                                                 exactly_group,
                                                 [3, 16, 33, 42, 46, 73])
            # Водоснабжение и водоотведение
            # (хол. вода + хол. вода для горячего водоснабжения + канализация)
            # по сумме услуг 5, 15, 32, 35, 36, 56, 67, 75, 76
            water_supply = self._privilages_summation(
                group_key,
                exactly_group,
                [5, 15, 32, 35, 36, 56, 67, 75, 76]
            )
            # Подогрев воды
            # по сумме услуг 4, 34, 74
            water_heating = self._privilages_summation(group_key,
                                                       exactly_group,
                                                       [4, 34, 74])
            # Газ - 6
            gas = self._privilages_summation(group_key, exactly_group, [6])
            # Электроэнергия
            # по сумме услуг 20, 27, 154, 155, 157, 158
            electricity = self._privilages_summation(group_key,
                                                     exactly_group,
                                                     [20, 27, 154, 155, 157, 158])
            category_name = privileges_code_names[group_key]
            # Кол-во пользующихся льготой
            privilege_users = self._privilages_summation(group_key,
                                                         exactly_group,
                                                         [777],
                                                         "privilege_count")

            # Добавим к результирующему словарю
            result[group_key].update(dict(
                privilegers_count=privilegers_count,
                privilege_users=privilege_users,
                square_de_facto=square_de_facto,
                square_calculate=square_calculate,
                repairs_2_43_48=repairs_2_43_48,
                repairs_45_47=repairs_45_47,
                recruiting=recruiting,
                rubbish=rubbish,
                heating=heating,
                water_supply=water_supply,
                water_heating=water_heating,
                gas=gas,
                electricity=electricity,
                category_name=category_name,
                row_summation=sum([repairs_2_43_48, repairs_45_47, recruiting,
                                   rubbish, heating, water_supply,
                                   water_heating, gas, electricity]
                                  ),
                row_summation_delta=0,
            ))
        # Формируем суммы по всем полям категорий
        result.update({"totals": {
            "total_repairs_2_43_48": sum([v["repairs_2_43_48"]
                                          for k, v in result.items()]),
            "total_repairs_45_47": sum([v["repairs_45_47"]
                                        for k, v in result.items()]),
            "total_recruiting": sum([v["recruiting"]
                                     for k, v in result.items()]),
            "total_rubbish": sum([v["rubbish"]
                                  for k, v in result.items()]),
            "total_heating": sum([v["heating"]
                                  for k, v in result.items()]),
            "total_water_supply": sum([v["water_supply"]
                                       for k, v in result.items()]),
            "total_water_heating": sum([v["water_heating"]
                                        for k, v in result.items()]),
            "total_gas": sum([v["gas"]
                              for k, v in result.items()]),
            "total_electricity": sum([v["electricity"]
                                      for k, v in result.items()]),
            "total_row_summation": sum([v["row_summation"]
                                        for k, v in result.items()]),
            "total_row_summation_delta": sum([v["row_summation_delta"]
                                              for k, v in result.items()]),
        }})
        return result


class AccrualsExport(PrivilegesExportMoscow):
    """ Экспорт начислений P1, P2, P3 """

    def __init__(self, provider_id, month, sector_code, provider_name=None):
        super().__init__(provider_id, month, sector_code, provider_name)
        self.xlsx_type_a_name = "Future_name"
        self.xlsx_type_a_len = 0
        self.xlsx_type_a_cs1 = 0
        self.xlsx_type_a_cs2 = 0
        self.xlsx_type_b_name = "Future_name"
        self.xlsx_type_b_len = 0
        self.xlsx_type_b_cs1 = 0
        self.xlsx_type_b_cs2 = 0
        self.xlsx_type_v_name = "Future_name"
        self.xlsx_type_v_len = 0

    def export(self, path=None):
        files = []
        # Отчет о выпадающих доходах будет строиться для настроек
        # у которых список направлений покрывает список переданных
        # и есть договор
        export_settings = [
            s for s in self.gcjs_settings[0].package_export
            if (
                'default' == s.export_type and
                all(map(lambda x: x in s.sectors, self.sector_code))
            )
        ]
        houses_codes = self.gcjs_settings[0].houses_codes
        if not export_settings:
            raise NoSettingsFound()
        for setting in export_settings:
            privilege_and_householders = \
                self.get_raw_data(setting.houses, houses_codes, setting)

            codes = setting.contract_number, self.gcjs_settings[0].provider_code
            strings_data = self.get_strings(codes[1],
                                            privilege_and_householders)
            data = self.get_files_data(strings_data, codes)

            for d in data:
                d['filename'] = '{}/{}'.format(
                    path or settings.DEFAULT_TMP_DIR,
                    d['filename']
                )
            # xlsx сохранение
            # Строки для таблицы
            # название файла, кол-во записей, КС1, КС2
            p1_row = (self.xlsx_type_a_name,
                      self.xlsx_type_a_len,
                      self.xlsx_type_a_cs1,
                      self.xlsx_type_a_cs2)
            p2_row = (self.xlsx_type_b_name,
                      self.xlsx_type_b_len,
                      self.xlsx_type_b_cs1,
                      self.xlsx_type_b_cs2)
            p3_row = (self.xlsx_type_v_name,
                      self.xlsx_type_v_len, "-", "-")
            xlsx_accruals = self.create_exel_accruals_report(
                p1_row=p1_row, p2_row=p2_row, p3_row=p3_row,
                contract_number=setting.contract_number,
                date=self.month,
                path=path,
                provider_name=self.provider_name
            )

            self.save_to_files(data)

            files.extend([d['filename'] for d in data])
            files.extend([xlsx_accruals])

        sector_name = ''
        for sector_choice in ACCRUAL_SECTOR_TYPE_CHOICES:
            if sector_choice[0] in self.sector_code:
                if not sector_name:
                    sector_name = sector_choice[1]
                else:
                    sector_name += ', {}'.format(sector_choice[1])
        zip_name = '{}_{}_{}_{}'.format(
            self.provider,
            self.month.strftime('%m%Y'),
            datetime.datetime.now(),
            sector_name,
        ).replace(':', '-')
        log = LogDbf(
            provider=self.provider,
            file_out=None,
            file_in=None,
            created_at=datetime.datetime.now(),
        ).save()
        zip_uuid, file_id = create_zip_file_in_gs(
            zip_name, 'LogDbf', log.pk, file_paths=files, id_return=True)
        log.file_out = {'uuid': zip_uuid, 'filename': zip_name}
        log.file_in = {'uuid': zip_uuid, 'filename': zip_name}
        log.save()
        return file_id

    def get_strings(self, provider_code, data):

        return {
            'p1a': '\n'.join(self.get_p1a_strings(
                data['householders'], provider_code
            )),
            'p1b': '\n'.join(self.get_p1b_strings(
                data['householders'], provider_code
            )),
            'p1v': '\n'.join(self.get_p1v_strings(
                data['householders'], provider_code
            )),
        }

    def create_exel_accruals_report(self,
                                    p1_row,
                                    p2_row,
                                    p3_row,
                                    contract_number,
                                    date=None,
                                    provider_name='ООО "УК "ПИОНЕР-СЕРВИС"',
                                    path=None):
        """
        Сводная ведомость (отчет по начислениям)
        :param p1_row: list - данные по документу типа A
        :param p2_row: list - данные по документу типа B
        :param p3_row: list - данные по документу типа V
        :param date: datetime - дата за которую собираются данные
        :param provider_name: str - Название организации
        :param path: str - путь сохранения файла
        :return: str - путь сохранения файла
        """
        path = path or '/tmp'
        file_name = \
            '{}_Сводная ведомость (отчет по начислениям).xlsx'.format(
                contract_number)
        file_path = os.path.join(path, file_name)
        workbook = xlsxwriter.Workbook(file_path, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)

        # Конфиги стилей данных листа
        configs = {
            "title": workbook.add_format({'bold': 1,
                                          'font_size': 10,
                                          'valign': 'bottom',
                                          'align': 'center',
                                          'font_name': 'Arial'
                                          }),
            "normal_left": workbook.add_format({'font_size': 10,
                                           'valign': 'bottom',
                                           'align': 'left',
                                           'font_name': 'Arial',
                                           }),
            "normal_right": workbook.add_format({'font_size': 10,
                                           'valign': 'bottom',
                                           'align': 'right',
                                           'font_name': 'Arial',
                                           }),
            "normal_center": workbook.add_format({'font_size': 10,
                                                 'valign': 'bottom',
                                                 'align': 'center',
                                                 'font_name': 'Arial',
                                                 }),

            "table_title_ceil": workbook.add_format({'font_size': 10,
                                                     'text_wrap': True,
                                                     'valign': 'vcenter',
                                                     'align': 'center',
                                                     'font_name': 'Arial',
                                                     'border': 1
                                                     }),
            "table_title_ceil_left": workbook.add_format({'font_size': 10,
                                                     'text_wrap': True,
                                                     'valign': 'vcenter',
                                                     'align': 'left',
                                                     'font_name': 'Arial',
                                                     'border': 1
                                                     }),
            "table_bold_ceil": workbook.add_format({'bold': 1,
                                                    'font_size': 10,
                                                    'valign': 'vcenter',
                                                    'align': 'left',
                                                    'font_name': 'Arial',
                                                    'bottom': 1
                                                    }),
            "table_bold_ceil_center": workbook.add_format({'bold': 1,
                                                    'font_size': 10,
                                                    'valign': 'vcenter',
                                                    'align': 'center',
                                                    'font_name': 'Arial',
                                                    'border': 1
                                                    }),
            "table_number": workbook.add_format({'font_size': 10,
                                                     'valign': 'vcenter',
                                                     'align': 'center',
                                                     'font_name': 'Arial',
                                                     'border': 1,
                                                 'num_format': '0.00',
                                                 'bold': 1
                                                     }),

        }

        # Конфиги колонок
        # Для рядов
        # сначала для всех
        for row in range(100):
            worksheet.set_row(row, 12)
        # индивидуально
        worksheet.set_row(8, 30)  # заголовки таблицы
        worksheet.set_row(9, 30)  # заголовки таблицы
        worksheet.set_row(10, 30)  # заголовки таблицы
        worksheet.set_row(11, 30)  # заголовки таблицы

        # Для колонок
        worksheet.set_column("A:A", 0.5)
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:D", 5)
        worksheet.set_column("E:H", 7)
        worksheet.set_column("I:I", 15)
        worksheet.set_column("G:K", 7)

        # Вставка текста
        # Объединение ячеек
        # Заголовок
        worksheet.merge_range('B1:K1',
                              "Сводная ведомость передаваемой информации",
                              configs["title"])
        worksheet.merge_range('B3:K3',
                              "за: {}".format(
                                  self._date_converter(date) if date
                                  else datetime.datetime.now().strftime('%m %Y')),
                              configs["title"])
        worksheet.merge_range('B4:K4',
                              "(отчетный период)",
                              configs["normal_center"])
        worksheet.merge_range('B6:K6',
                              "Организация: {}".format(provider_name),
                              configs["title"])

        # Таблица
        worksheet.write('B9',
                        "Название файла",
                        configs["table_title_ceil"])
        worksheet.merge_range('C9:D9',
                              "Количество записей",
                              configs["table_title_ceil"])
        worksheet.merge_range('E9:F9',
                              "Контрольная сумма I (руб.)",
                              configs["table_title_ceil"])
        worksheet.merge_range('G9:H9',
                              "Контрольная сумма II (руб.)",
                              configs["table_title_ceil"])
        worksheet.merge_range('I9:K9',
                              "Содержание информации",
                              configs["table_title_ceil"])
        worksheet.merge_range('I10:K10',
                              "сведения о потребителях услуг",
                              configs["table_title_ceil_left"])
        worksheet.merge_range('I11:K11',
                              "сведения о начислениях",
                              configs["table_title_ceil_left"])
        worksheet.merge_range('I12:K12',
                              "сведения о составе семьи",
                              configs["table_title_ceil_left"])

        # Добавляем динамических данные
        row_pointer = 10
        # for privilege_number, data_field in dinamyc_data.items():
        for row_data in (p1_row, p2_row, p3_row):
            worksheet.write('B{row}'.format(row=row_pointer),
                            row_data[0],
                            configs["table_bold_ceil_center"])
            worksheet.merge_range('C{row}:D{row}'.format(row=row_pointer),
                                  row_data[1],
                                  configs["table_bold_ceil_center"])
            worksheet.merge_range('E{row}:F{row}'.format(row=row_pointer),
                                  row_data[2],
                                  configs["table_number"])
            worksheet.merge_range('G{row}:H{row}'.format(row=row_pointer),
                                  row_data[3],
                                  configs["table_number"])
            row_pointer += 1

        # Добавим поля в футер
        # Черточки
        worksheet.merge_range('B20:C20', "", configs["table_bold_ceil"])
        worksheet.merge_range('I20:K20', "", configs["table_bold_ceil"])

        # Подписи
        worksheet.write('B18', "Информацию сдал:", configs["normal_left"])
        worksheet.merge_range('I18:K18',
                              "Информацию принял:",
                              configs["normal_left"])
        worksheet.merge_range('B21:C21',
                              "(подпись, дата)",
                              configs["normal_center"])
        worksheet.merge_range('I21:K21',
                              "(подпись, дата)",
                              configs["normal_center"])
        worksheet.merge_range('I24:K24',
                              "М.П.",
                              configs["normal_center"])
        worksheet.merge_range('B24:C24',
                              "М.П.",
                              configs["normal_center"])

        # Закрываем книгу
        workbook.close()
        return file_path


class RevenuesShortfallsExport(PrivilegesExportMoscow):
    """ Отчёт о выпадающих доходах """

    def __init__(self, provider_id, month, sector_code, provider_name=None):
        super().__init__(provider_id, month, sector_code, provider_name)
        self.xlsx_consolidation_report_summary_writes = 0
        self.xlsx_consolidation_report_check_sum = 0
        self.xlsx_typy1_name = "Future_name"
        # Подразумевается передача только одного сектора
        if len(self.sector_code) != 1:
            raise NotUniqueError()

    def export(self, path=None):
        files = []
        # Отчет о выпадающих доходах будет строиться для настроек
        # у которых список направлений покрывает список переданных
        export_settings = [
            s for s in self.gcjs_settings[0].package_export
            if (
                'losses' == s.export_type and
                all(map(lambda x: x in s.sectors, self.sector_code))
            )
        ]
        houses_codes = self.gcjs_settings[0].houses_codes
        if not export_settings:
            raise NoSettingsFound()
        for setting in export_settings:
            privilege_and_householders = \
                self.get_raw_data(setting.houses, houses_codes, setting)
            # Передача в функцию данных для формирования для exel report
            data_xlsx = self.get_sorted_privilegers(
                privilege_and_householders["privilegers"])

            strings_data = self.get_strings(setting,
                                            privilege_and_householders)

            codes = setting.contract_number, self.gcjs_settings[0].provider_code
            data = self.get_files_data(strings_data, codes)

            for d in data:
                d['filename'] = '{}/{}'.format(
                    path or settings.DEFAULT_TMP_DIR,
                    d['filename']
                )
            # xlsx сохранение
            xlsx_final_report = self.create_final_exel_report(
                dinamyc_data=data_xlsx,
                contract_number=setting.contract_number,
                date=self.month,
                path=path,
                provider_name=self.provider_name
            )
            xlsx_consolidated_report = self.create_exel_consolidated_report(
                name=self.xlsx_typy1_name,
                summary_writes=self.xlsx_consolidation_report_summary_writes,
                check_sum=self.xlsx_consolidation_report_check_sum,
                contract_number=setting.contract_number,
                date=self.month,
                path=path,
                provider_name=self.provider_name
            )
            self.save_to_files(data)

            files.extend([d['filename'] for d in data])
            files.extend([xlsx_final_report, xlsx_consolidated_report])

        sector_name = ''
        for sector_choice in ACCRUAL_SECTOR_TYPE_CHOICES:
            if sector_choice[0] == self.sector_code:
                sector_name = sector_choice[1]
        zip_name = '{}_{}_{}_{}'.format(
            self.provider,
            self.month.strftime('%m%Y'),
            datetime.datetime.now(),
            sector_name,
        ).replace(':', '-')
        log = LogDbf(
            provider=self.provider,
            file_out=None,
            file_in=None,
            created_at=datetime.datetime.now(),
        ).save()
        zip_uuid, file_id = create_zip_file_in_gs(
            zip_name, 'LogDbf', log.pk, file_paths=files, id_return=True)
        log.file_out = {'uuid': zip_uuid, 'filename': zip_name}
        log.file_in = {'uuid': zip_uuid, 'filename': zip_name}
        log.save()
        return file_id

    def get_strings(self, gcjs_settings, data):
        return {
            'type1': self.get_type1_xml(
                data['privilegers'],
                gcjs_settings
            )
        }

    def create_final_exel_report(self,
                                 dinamyc_data,
                                 contract_number,
                                 date=None,
                                 provider_name='ООО "УК "ПИОНЕР-СЕРВИС"',
                                 another_data=None,
                                 path=None):
        """
        Итоговые ведомости (отчет выпадающих доходах)
        :param contract_number: str: для названия
        :param dinamyc_data: dict - данные о льготниках,
               сгруппированные по льготным группам
        :param date:  datetime - дата за которую собираются данные
        :param provider_name: str - Название организации
        :param another_data: datetime - дата выгрузки
        :param path: str - путь сохранения файла
        :return: str - путь сохранения файла
        """
        path = path or '/tmp'
        file_name = \
            '{}_Итоговые ведомости (отчет выпадающих доходах).xlsx'.format(
                contract_number)
        file_path = os.path.join(path, file_name)
        workbook = xlsxwriter.Workbook(file_path, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)

        # Конфиги стилей данных листа
        configs = {
            "title": workbook.add_format({'bold': 1,
                                          'font_size': 12,
                                          'text_wrap': True,
                                          'valign': 'bottom',
                                          'align': 'center',
                                          'font_name': 'Arial'
                                          }),
            "normal": workbook.add_format({'font_size': 10,
                                           # 'text_wrap': True,
                                           'valign': 'bottom',
                                           'align': 'left',
                                           'font_name': 'Arial',
                                           }),
            "date": workbook.add_format({'font_size': 10,
                                           # 'text_wrap': True,
                                           'valign': 'bottom',
                                           'align': 'left',
                                           'font_name': 'Arial',
                                         'num_format': 'd mmmm yyyy',
                                           }),
            "date_title": workbook.add_format({'bold': 1,
                                          'font_size': 12,
                                          'text_wrap': True,
                                          'valign': 'bottom',
                                          'align': 'center',
                                          'font_name': 'Arial',
                                               'num_format': 'd mmmm yyyy',
                                          }),
            "table_title_ceil": workbook.add_format({'font_size': 8,
                                                     'text_wrap': True,
                                                     'valign': 'vcenter',
                                                     'align': 'center',
                                                     'font_name': 'Arial',
                                                     'border': 1
                                                     }),
            "table_bold_ceil": workbook.add_format({'bold': 1,
                                                    'font_size': 10,
                                                    'valign': 'vcenter',
                                                    'align': 'left',
                                                    'font_name': 'Arial',
                                                    'bottom': 1,
                                                    'right': 1
                                                    }),
            "lines": workbook.add_format({'bold': 1,
                                                    'font_size': 10,
                                                    'valign': 'vcenter',
                                                    'align': 'left',
                                                    'font_name': 'Arial',
                                                    'bottom': 1,
                                                    }),
            "table_bold_ceil_border": workbook.add_format({'bold': 1,
                                                    'font_size': 8,
                                                    'valign': 'vcenter',
                                                    'align': 'left',
                                                    'font_name': 'Arial',
                                                    'border': 1
                                                    }),
            "table_final_text": workbook.add_format({'bold': 1,
                                                    'font_size': 8,
                                                     'valign': 'vcenter',
                                                     'align': 'left',
                                                     'font_name': 'Arial',
                                                     'top': 1,
                                                     'left': 1,
                                                    }),
            "table_count_ceil": workbook.add_format({'font_size': 8,
                                                    'valign': 'vcenter',
                                                    'align': 'right',
                                                    'font_name': 'Arial',
                                                    'bottom': 1
                                                    }),
            "table_priv_owner_text": workbook.add_format({'font_size': 8,
                                                          # 'text_wrap': True,
                                                          'valign': 'vcenter',
                                                          'align': 'left',
                                                          'font_name': 'Arial',
                                                          'bottom': 1,
                                                          'left': 1,
                                                          }),
            "table_priv_count": workbook.add_format({'font_size': 8,
                                                          'valign': 'vcenter',
                                                          'align': 'right',
                                                          'font_name': 'Arial',
                                                          'border': 1,
                                                          }),
            "table_number": workbook.add_format({'font_size': 8,
                                                     'valign': 'vcenter',
                                                     'align': 'right',
                                                     'font_name': 'Arial',
                                                     'border': 1,
                                                 'num_format': '0.00'
                                                     }),
        }

        # Статичные данные
        title_name = "Итоговые данные отчетов (корректировок отчетов) о " \
                     "выпадающих доходах от предоставления льгот по оплате " \
                     "жилищно-коммунальных услуг, предоставленных " \
                     "в электронном виде"
        control_provider = "Организация, управляющая жилым фондом:"

        # Конфиги колонок
        # Для рядов
        # сначала для всех
        for row in range(100):
            worksheet.set_row(row, 12)
        # индивидуально
        worksheet.set_row(0, 30)  # заголовок
        worksheet.set_row(1, 25)  # дата
        worksheet.set_row(7, 27)  # заголовки таблицы
        worksheet.set_row(8, 27)  # заголовки таблицы
        worksheet.set_row(9, 27)  # заголовки таблицы
        worksheet.set_row(10, 27)  # заголовки таблицы

        # Для колонок
        worksheet.set_column("A:A", 0.5)
        worksheet.set_column("T:T", 0.5)
        worksheet.set_column("C:D", 1.9)
        worksheet.set_column("E:E", 2.7)
        worksheet.set_column("F:H", 7)
        worksheet.set_column("I:J", 14)
        worksheet.set_column("K:L", 7)
        worksheet.set_column("M:N", 16)
        worksheet.set_column("O:O", 7)
        worksheet.set_column("P:P", 4)
        worksheet.set_column("Q:Q", 8.5)
        worksheet.set_column("R:R", 10)
        worksheet.set_column("S:S", 7)

        # Вставка текста
        # Объединение ячеек
        # Заголовок
        worksheet.merge_range('C1:R1', title_name, configs["title"])
        worksheet.merge_range('C2:R2',
                              "за {}".format(
                                  self._date_converter(date)
                                  if date
                                  else datetime.datetime.now().strftime('%m %Y')),
                              configs["date_title"])
        worksheet.merge_range('B4:G4', control_provider, configs["normal"])
        worksheet.merge_range('H4:K4', provider_name, configs["normal"])

        worksheet.write('B6', "Вид документа:", configs["normal"])
        worksheet.write('E6', "Отчет", configs["normal"])
        worksheet.write_datetime('R6',
                                 another_data
                                 if another_data
                                 else datetime.datetime.now(),
                                 configs["date"])

        # Таблица
        worksheet.merge_range('B8:E10', "", configs["table_title_ceil"])
        ceil_text = "Количество человек, пользующихся льготой " \
                    "(включая владельца льготы)"
        worksheet.merge_range('F8:F10',
                              ceil_text,
                              configs["table_title_ceil"])
        worksheet.merge_range('G8:G10',
                              "Фактически занимаемая площадь (кв.м)",
                              configs["table_title_ceil"])
        worksheet.merge_range('H8:H10',
                              "Площадь, на которую рассчитываются льготы (кв.м)",
                              configs["table_title_ceil"])
        ceil_text = "Выпадающие доходы от предоставления льгот " \
                    "по услугам (руб.)"
        worksheet.merge_range('I8:Q8',
                              ceil_text,
                              configs["table_title_ceil"])
        worksheet.merge_range('I9:J9',
                              "содержание и ремонт жилья",
                              configs["table_title_ceil"])
        worksheet.merge_range('K9:K10',
                              "плата за наем",
                              configs["table_title_ceil"])
        worksheet.merge_range('L9:L10',
                              "вывоз бытовых отходов",
                              configs["table_title_ceil"])
        ceil_text = "отопление на основную и дополнительную площадь, " \
                    "а так же излишки площади"
        worksheet.merge_range('M9:M10',
                              ceil_text,
                              configs["table_title_ceil"])
        ceil_text = "водоснабжение и водоотведение " \
                    "(хол. вода + хол. вода для горячего водоснабжения +" \
                    " канализация)"
        worksheet.merge_range('N9:N10',
                              ceil_text,
                              configs["table_title_ceil"])
        worksheet.merge_range('O9:O10',
                              "подогрев воды",
                              configs["table_title_ceil"])
        worksheet.merge_range('P9:P10',
                              "газ",
                              configs["table_title_ceil"])
        worksheet.merge_range('Q9:Q10',
                              "электроэнергия",
                              configs["table_title_ceil"])
        worksheet.merge_range('R8:R10',
                              "Сумма компенсации за отчетный период (руб.)",
                              configs["table_title_ceil"])
        ceil_text = "Сумма изменения за отчетный период (со знаком, руб.)"
        worksheet.merge_range('S8:S10',
                              ceil_text,
                              configs["table_title_ceil"])
        worksheet.merge_range('B11:H11',
                              "Коды услуг по справочнику банка Москвы:",
                              configs["table_title_ceil"])
        worksheet.merge_range('B12:F12',
                              "Тип жилого фонда: (код 6)",
                              configs["table_bold_ceil"])
        worksheet.merge_range('G12:S12',
                              "Дома в управлении коммерческих организаций",
                              configs["table_bold_ceil"])
        # ряд с именами услуг
        service_row = (
            ("I", "по сумме слуг 2, 43, 48"),
            ("J", "по сумме услуг 45, 47"),
            ("K", "по сумме услуг 1, 153"),
            ("L", "7"),
            ("M", "по сумме услуг 3, 16, 33, 42, 46, 73"),
            ("N", "по сумме услуг 5, 15, 32, 35, 36, 56, 67, 75, 76"),
            ("O", "по сумме услуг 4, 34, 74"),
            ("P", "6"),
            ("Q", "по сумме услуг 20, 27, 154, 155, 157, 158"),
            ("R", ""),
            ("S", "")
         )
        for col, name in service_row:
            worksheet.write("{col}11:{col}11".format(col=col),
                            name,
                            configs["table_title_ceil"])

        # Добавляем в цикле динамические данные извне
        # todo сортироовка входного словаря
        start_row = 13
        for privilege_number, data_field in dinamyc_data.items():
            if privilege_number == "totals":
                continue
            # Объеденяем ячейки Льготной категории
            worksheet.merge_range(
                'C{row}:G{row}'.format(row=start_row),
                "Льготная категория: (код {})".format(privilege_number),
                configs["table_bold_ceil"]
            )
            # Объеденяем ячейки Названия льготной категории
            worksheet.merge_range('H{row}:S{row}'.format(row=start_row),
                                  data_field["category_name"].capitalize(),
                                  configs["table_bold_ceil"])
            # Добавим поля Итого, Владельцев льгот и их количество
            worksheet.write('B{row}'.format(row=start_row + 1),
                            "ИТОГО:",
                            configs["table_final_text"])
            # скейка потому что так нужно
            worksheet.merge_range('C{row}:D{row}'.format(row=start_row + 1), "")

            worksheet.merge_range('B{row}:C{row}'.format(row=start_row + 2),
                                  "владельцев льгот:",
                                  configs["table_priv_owner_text"])
            worksheet.merge_range('D{row}:E{row}'.format(row=start_row + 2),
                                  data_field["privilegers_count"],
                                  configs["table_count_ceil"])
            # Пользующиеся льготой с обычным форматом ячейки
            worksheet.merge_range('F{}:F{}'.format(start_row + 1, start_row + 2),
                                  data_field["privilege_users"],
                                  configs["table_priv_count"])
            # По всем остальным пунктам
            service_row = (
                ("G", "square_de_facto"),
                ("H", "square_calculate"),
                ("I", "repairs_2_43_48"),
                ("J", "repairs_45_47"),
                ("K", "recruiting"),
                ("L", "rubbish"),
                ("M", "heating"),
                ("N", "water_supply"),
                ("O", "water_heating"),
                ("P", "gas"),
                ("Q", "electricity"),
                ("R", "row_summation"),
                ("S", "row_summation_delta"),
            )
            for col, field_name in service_row:
                worksheet.merge_range(
                    '{col}{row1}:{col}{row2}'.format(col=col,
                                                     row1=start_row + 1,
                                                     row2=start_row + 2),
                    data_field[field_name],
                    configs["table_number"])
            # Увеличиваем счетчик на необходимое количество строк
            start_row += 3
        # Колонки итого
        # Объеденяем ячейки итого по Льготным категориям
        worksheet.merge_range('B{row1}:H{row2}'.format(row1=start_row,
                                                       row2=start_row + 1),
                              "ИТОГО ПО ВСЕМ ЛЬГОТНЫМ КАТЕГОРИЯМ:",
                              configs["table_bold_ceil_border"])
        # Проходим по всем пунктам итого
        summation_row = (
            ("I", "total_repairs_2_43_48"),
            ("J", "total_repairs_45_47"),
            ("K", "total_recruiting"),
            ("L", "total_rubbish"),
            ("M", "total_heating"),
            ("N", "total_water_supply"),
            ("O", "total_water_heating"),
            ("P", "total_gas"),
            ("Q", "total_electricity"),
            ("R", "total_row_summation"),
            ("S", "total_row_summation_delta"),
        )
        for col, field_name in summation_row:
            worksheet.merge_range(
                '{col}{row1}:{col}{row2}'.format(col=col,
                                                 row1=start_row,
                                                 row2=start_row + 1),
                dinamyc_data["totals"][field_name],
                configs["table_number"])

        # Добавим поля в футер
        worksheet.merge_range('B{row}:E{row}'.format(row=start_row + 5),
                              "Руководитель",
                              configs["normal"])
        # Черточки
        worksheet.merge_range('G{row}:K{row}'.format(row=start_row + 5),
                              "",
                              configs["lines"])
        worksheet.merge_range('O{row}:R{row}'.format(row=start_row + 5),
                              "",
                              configs["lines"])
        worksheet.merge_range('O{row}:R{row}'.format(row=start_row + 6),
                              "",
                              configs["lines"])
        worksheet.merge_range('O{row}:R{row}'.format(row=start_row + 7),
                              "",
                              configs["lines"])
        # Подписи
        # Подпись
        worksheet.write('N{row}'.format(row=start_row + 5),
                        "Подпись",
                        configs["normal"])
        # Дата
        worksheet.write('N{row}'.format(row=start_row + 6),
                        "Дата",
                        configs["normal"])
        # Телефон
        worksheet.write('N{row}'.format(row=start_row + 7),
                        "Телефон",
                        configs["normal"])
        # МП
        worksheet.write('H{row}'.format(row=start_row + 7),
                        "М.П.",
                        configs["normal"])

        # Закрываем книгу
        workbook.close()
        return file_path

    def create_exel_consolidated_report(self,
                                        name,
                                        summary_writes,
                                        check_sum,
                                        contract_number,
                                        date=None,
                                        provider_name='ООО "УК "ПИОНЕР-СЕРВИС"',
                                        another_data=None,
                                        path=None):
        """
        Сводная ведомость (отчет о выпадающих доходах)
        :param contract_number: str: часть имени файла
        :param name: str - имя файла
        :param summary_writes: количество записей
        :param check_sum: контрольная сумма
        :param date: datetime - дата за которую собираются данные
        :param provider_name: str - Название организации
        :param another_data: datetime - дата выгрузки
        :param path: str - путь сохранения файла
        :return: str - путь сохранения файла
        """
        path = path or '/tmp'
        file_name = \
            '{}_Сводная ведомость (отчет о выпадающих доходах).xlsx'.format(
                contract_number)
        file_path = os.path.join(path, file_name)
        workbook = xlsxwriter.Workbook(file_path, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)

        # Конфиги стилей данных листа
        configs = {
            "title": workbook.add_format({'bold': 1,
                                          'font_size': 10,
                                          'valign': 'bottom',
                                          'align': 'center',
                                          'font_name': 'Arial'
                                          }),
            "date": workbook.add_format({'font_size': 10,
                                         # 'text_wrap': True,
                                         'valign': 'bottom',
                                         'align': 'right',
                                         'font_name': 'Arial',
                                         'num_format': 'd mmmm yyyy',
                                         }),
            "normal_left": workbook.add_format({'font_size': 10,
                                           'valign': 'bottom',
                                           'align': 'left',
                                           'font_name': 'Arial',
                                           }),
            "normal_right": workbook.add_format({'font_size': 10,
                                           'valign': 'bottom',
                                           'align': 'right',
                                           'font_name': 'Arial',
                                           }),
            "normal_center": workbook.add_format({'font_size': 10,
                                                 'valign': 'bottom',
                                                 'align': 'center',
                                                 'font_name': 'Arial',
                                                 }),

            "table_title_ceil": workbook.add_format({'font_size': 10,
                                                     'text_wrap': True,
                                                     'valign': 'vcenter',
                                                     'align': 'center',
                                                     'font_name': 'Arial',
                                                     'border': 1
                                                     }),
            "table_bold_ceil": workbook.add_format({'bold': 1,
                                                    'font_size': 10,
                                                    'valign': 'vcenter',
                                                    'align': 'left',
                                                    'font_name': 'Arial',
                                                    'bottom': 1
                                                    }),
            "table_number": workbook.add_format({'font_size': 10,
                                                     'valign': 'vcenter',
                                                     'align': 'center',
                                                     'font_name': 'Arial',
                                                     'border': 1,
                                                 'num_format': '0.00'
                                                     }),
        }

        # Конфиги колонок
        # Для рядов
        # сначала для всех
        for row in range(100):
            worksheet.set_row(row, 12)
        # индивидуально
        worksheet.set_row(6, 45)  # заголовки таблицы
        worksheet.set_row(7, 35)  # заголовки таблицы

        # Для колонок
        worksheet.set_column("A:A", 0.5)
        worksheet.set_column("B:B", 15)
        worksheet.set_column("C:F", 5)
        worksheet.set_column("G:G", 30)

        # Вставка текста
        # Объединение ячеек
        # Заголовок
        worksheet.merge_range('B1:G1',
                              "Сводная ведомость передаваемой информации",
                              configs["title"])
        ceil_text = "Отчет о выпадающих доходах от предоставления " \
                    "гражданам льгот на оплату ЖКУ"
        worksheet.merge_range('B2:G2',
                              ceil_text,
                              configs["title"])
        worksheet.merge_range('B3:G3',
                              "Отчет предоставлен за: {}".format(
                                  self._date_converter(date)
                                  if date
                                  else datetime.datetime.now().strftime('%m %Y')),
                              configs["title"])
        worksheet.merge_range('B4:G4',
                              "Организация: {}".format(provider_name),
                              configs["title"])
        worksheet.merge_range('B5:G5',
                              "Вид документа: отчет",
                              configs["title"])
        worksheet.write('G10',
                        another_data
                        if another_data
                        else datetime.datetime.now(),
                        configs["date"])

        # Таблица
        worksheet.write('B7',
                        "Название файла",
                        configs["table_title_ceil"])
        worksheet.merge_range('C7:D7',
                              "Суммарное количество записей всех типов",
                              configs["table_title_ceil"])
        worksheet.merge_range('E7:F7',
                              "Контрольная сумма (руб.)",
                              configs["table_title_ceil"])
        worksheet.write('G7',
                        "Содержание информации",
                        configs["table_title_ceil"])

        # Добавляем динамических данные
        worksheet.write('B8',
                        name,
                        configs["table_title_ceil"])
        worksheet.merge_range('C8:D8',
                              summary_writes,
                              configs["table_title_ceil"])
        worksheet.merge_range('E8:F8',
                              check_sum,
                              configs["table_number"])
        ceil_text = "Сведения о выпадающих доходах от " \
                    "предоставления гражданам льгот на оплату ЖКХ"
        worksheet.write('G8',
                        ceil_text,
                        configs["table_title_ceil"])

        # Добавим поля в футер
        # Черточки
        worksheet.merge_range('B16:C16', "", configs["table_bold_ceil"])
        worksheet.write('G16', "", configs["table_bold_ceil"])

        # Подписи
        worksheet.write('B14', "Информацию сдал:", configs["normal_left"])
        worksheet.write('G14', "Информацию принял:", configs["normal_left"])
        worksheet.write('B17', "(подпись, дата)", configs["normal_center"])
        worksheet.write('G17', "(подпись, дата)", configs["normal_center"])
        worksheet.write('G20', "М.П.", configs["normal_center"])
        worksheet.merge_range('B20:C20', "М.П.", configs["normal_center"])

        # Закрываем книгу
        workbook.close()
        return file_path
