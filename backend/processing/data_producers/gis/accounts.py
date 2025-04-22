from copy import copy
from mongoengine import Q

from app.area.models.area import Area
from app.house.models.house import House
from processing.models.billing.account import Tenant

from .base import BaseGISDataProducer


class AccountsCommonFields:
    ENTRY_N = '№ записи'
    ACCOUNT_NUMBER = 'Номер ЛС (иной идентификатор потребителя) '
    HCS_UID = 'Идентификатор ЖКУ'
    ACCOUNT_TYPE = 'Тип лицевого счета'
    IS_RENTER = 'Являтся нанимателем?'  # TODO переименовать
    IS_SHARED = 'Лицевые счета на помещение(я) разделены?'
    NAME = 'Имя потребителя'
    FAMILY_NAME = 'Фамилия'
    PATRONYMIC_NAME = 'Отчество (при наличии)'
    SNILS = 'СНИЛС потребителя'
    ACCOUNT_PRIVATE_DOC_TYPE = 'Вид документа, удостоверяющего личность'
    ACCOUNT_PRIVATE_DOC_NUMBER = 'Номер документа, удостоверяющего личность'
    ACCOUNT_PRIVATE_DOC_SERIES = 'Серия документа, удостоверяющего личность'
    ACCOUNT_PRIVATE_DOC_DATE = 'Дата документа, удостоверяющего личность'
    OGRN = 'ОГРН/ОГРНИП потребителя (для ЮЛ/ИП)'
    NZA = 'НЗА потребителя (для ФПИЮЛ)'
    KPP = 'КПП потребителя (для ОП)'
    AREA_SUMMARY = 'Общая площадь, кв. м'
    AREA_LIVING = 'Жилая площадь, кв. м'
    AREA_HEATED = 'Отапливаемая площадь, кв. м'
    RESIDENTS_NUMBER = 'Количество проживающих, чел.'


class AccountsAreasFields:
    ENTRY_N = '№ записи лицевого счета'
    AREA_ADDRESS = 'Адрес помещения'
    HOUSE_FIAS_GUID = 'Глобальный уникальный идентификатор дома по ФИАС' \
                      '/Идентификационный код дома в ГИС ЖКХ'
    AREA_TYPE = 'Тип помещения/блок'
    AREA_NUMBER = 'Номер помещения/блока'
    ROOM_NUMBER = 'Номер комнаты'
    HOUSE_AREA_ROOM_GIS_UID = 'Идентификатор дома, помещения, комнаты, присвоенный ГИС ЖКХ'
    PAYMENT_SHARE_PCT = 'Доля внесения платы, размер доли в %'


class AccountBaseFields:
    ENTRY_N = '№ записи лицевого счета'
    BASE_TYPE = 'Тип основания'
    BASE_ID = 'Идентификатор основания'

    SOCIAL_CONTRACT_TYPE = 'Договор социального найма/Тип'
    SOCIAL_CONTRACT_NUMBER = 'Договор социального найма/Номер'
    SOCIAL_CONTRACT_DATE = 'Договор социального найма/Дата заключения'

    RESOURCE_CONTRACT_NOT_PUBLIC = 'Договор ресурсоснабжения/Договор не ' \
        'является публичным и присутствует заключенный на бумажном носителе ' \
        'или в электронной форме'
    RESOURCE_CONTRACT_NUMBER = 'Договор ресурсоснабжения/Номер'
    RESOURCE_CONTRACT_DATE = 'Договор ресурсоснабжения/Дата заключения'

    GIS_PROCESSING_STATUS = 'Статус обработки'


class AccountsDataProducer(BaseGISDataProducer):

    XLSX_TEMPLATE = 'templates/gis/accounts_11_11_0_5.xlsx'
    XLSX_WORKSHEETS = {
        'Основные сведения': {
            'entry_produce_method': 'get_entry_common',
            'title': 'Основные сведения',
            'start_row': 3,
            'columns': {
                AccountsCommonFields.ENTRY_N: 'A',
                AccountsCommonFields.ACCOUNT_NUMBER: 'B',
                AccountsCommonFields.HCS_UID: 'C',
                AccountsCommonFields.ACCOUNT_TYPE: 'D',
                AccountsCommonFields.IS_RENTER: 'E',
                AccountsCommonFields.IS_SHARED: 'F',
                AccountsCommonFields.FAMILY_NAME: 'G',
                AccountsCommonFields.NAME: 'H',
                AccountsCommonFields.PATRONYMIC_NAME: 'I',
                AccountsCommonFields.SNILS: 'J',
                AccountsCommonFields.ACCOUNT_PRIVATE_DOC_TYPE: 'K',
                AccountsCommonFields.ACCOUNT_PRIVATE_DOC_NUMBER: 'L',
                AccountsCommonFields.ACCOUNT_PRIVATE_DOC_SERIES: 'M',
                AccountsCommonFields.ACCOUNT_PRIVATE_DOC_DATE: 'N',
                AccountsCommonFields.OGRN: 'O',
                AccountsCommonFields.NZA: 'P',
                AccountsCommonFields.KPP: 'Q',
                AccountsCommonFields.AREA_SUMMARY: 'R',
                AccountsCommonFields.AREA_LIVING: 'S',
                AccountsCommonFields.AREA_HEATED: 'T',
                AccountsCommonFields.RESIDENTS_NUMBER: 'U',
            }
        },
        'Помещения': {
            'entry_produce_method': 'get_entry_areas',
            'title': 'Помещение',
            'start_row': 3,
            'columns': {
                AccountsAreasFields.ENTRY_N: 'A',
                AccountsAreasFields.AREA_ADDRESS: 'B',
                AccountsAreasFields.HOUSE_FIAS_GUID: 'C',
                AccountsAreasFields.AREA_TYPE: 'D',
                AccountsAreasFields.AREA_NUMBER: 'E',
                AccountsAreasFields.ROOM_NUMBER: 'F',
                AccountsAreasFields.HOUSE_AREA_ROOM_GIS_UID: 'G',
                AccountsAreasFields.PAYMENT_SHARE_PCT: 'H',
            }
        },
        'Основания': {
            'entry_produce_method': 'get_entry_bases',
            'title': 'Основания',
            'start_row': 3,
            'columns': {
                AccountBaseFields.ENTRY_N: 'A',
                AccountBaseFields.BASE_TYPE: 'B',
                AccountBaseFields.BASE_ID: 'C',
                AccountBaseFields.SOCIAL_CONTRACT_TYPE: 'D',
                AccountBaseFields.SOCIAL_CONTRACT_NUMBER: 'E',
                AccountBaseFields.SOCIAL_CONTRACT_DATE: 'F',
                AccountBaseFields.RESOURCE_CONTRACT_NOT_PUBLIC: 'G',
                AccountBaseFields.RESOURCE_CONTRACT_NUMBER: 'H',
                AccountBaseFields.RESOURCE_CONTRACT_DATE: 'I',
                AccountBaseFields.GIS_PROCESSING_STATUS: 'J',
            }
        }
    }

    def get_entry_common(self, entry_source, export_task):
        entry = {}
        account, area, date, account_type = entry_source['account'], entry_source['area'], entry_source['date'], entry_source['account_type']

        # № записи
        entry[AccountsCommonFields.ENTRY_N] = account.number
        # Номер ЛС (иной идентификатор потребителя)
        entry[AccountsCommonFields.ACCOUNT_NUMBER] = account.number
        # Имя
        entry[AccountsCommonFields.NAME] = account.first_name or ''
        # Имя
        entry[AccountsCommonFields.FAMILY_NAME] = account.last_name or ''
        # Отчество
        entry[AccountsCommonFields.PATRONYMIC_NAME] = account.patronymic_name or ''
        # Идентификатор ЖКУ
        entry[AccountsCommonFields.HCS_UID] = account.hcs_uid or ''
        # Тип лицевого счета
        entry[AccountsCommonFields.ACCOUNT_TYPE] = 'ЛС ' + str(account_type)
        # Является нанимателем?
        entry[AccountsCommonFields.IS_RENTER] = 'Нет'
        # Разделены ли ЛС на помещения?
        entry[AccountsCommonFields.IS_SHARED] = 'Нет'

        # TODO Добавить выгрузку ОГРН, если это ЛС ИП/ЮЛ

        # Общая площадь, кв. м
        if not getattr(area, 'is_shared', False):
            account_area_meters = area.area_total
        else:
            x, y = (0, 1)
            if account.statuses.ownership \
            and account.statuses.ownership.property_share:
                x, y = account.statuses.ownership.property_share
            account_area_meters = area.area_total * x / y if y else 0

        entry[AccountsCommonFields.AREA_SUMMARY] = account_area_meters

        # Жилая площадь, кв. м
        if area.area_living:
            entry[AccountsCommonFields.AREA_LIVING] = area.area_living

        # Количество проживающих, чел.
        if not getattr(area, 'is_shared', False):
            query = Q(area__id=area.id)
            query &= Q(statuses__registration__date_from__lte=date)
            query &= (
                    Q(statuses__registration__date_till__gte=date)
                    | Q(statuses__registration__date_till=None)
            )

            tenants_living = Tenant.objects(query).count()

        else:
            tenants_living = Tenant.objects(
                family__householder=account.id,
                id__ne=account.id,
            ).count()

        entry[AccountsCommonFields.RESIDENTS_NUMBER] = tenants_living

        return entry

    def get_entry_areas(self, entry_source, export_task):

        account = entry_source['account']

        area = Area.objects(id=account.area.id).first()
        house = House.objects(id=account.area.house.id).first()
        account_rooms = [room for room in area.rooms if room.id in account.rooms] if area.is_shared else []

        if 'LivingArea' in area._type:
            area_type = 'Жилое помещение'
        elif 'NotLivingArea' in area._type:
            area_type = 'Нежилое помещение'
        elif False:  # Сейчас такого типа в системе нет
            area_type = 'Блок в доме блокированной застройки'

        else:
            area_type = ''

        entry = {
            AccountsAreasFields.ENTRY_N: account.number,
            AccountsAreasFields.AREA_ADDRESS: house.address,
            AccountsAreasFields.PAYMENT_SHARE_PCT: '',
        }
        if not area.gis_uid:
            entry[AccountsAreasFields.HOUSE_FIAS_GUID] = (
                    house.gis_fias
                    or house.fias_house_guid
            )
            entry[AccountsAreasFields.AREA_TYPE] = area_type
            entry[AccountsAreasFields.AREA_NUMBER] = area.str_number
            entry[AccountsAreasFields.ROOM_NUMBER] = ''
        else:
            entry[AccountsAreasFields.HOUSE_FIAS_GUID] = ''
            entry[AccountsAreasFields.AREA_TYPE] = ''
            entry[AccountsAreasFields.AREA_NUMBER] = ''
            entry[AccountsAreasFields.ROOM_NUMBER] = ''
            entry[AccountsAreasFields.HOUSE_AREA_ROOM_GIS_UID] = \
                area.gis_uid

        if account_rooms:
            multi_entry = []
            for account_room in account_rooms:

                room_entry = copy(entry)
                room_entry[AccountsAreasFields.ROOM_NUMBER] = \
                    account_room.number
                multi_entry.append(room_entry)

            return multi_entry

        return entry

    def get_entry_bases(self, entry_source, export_task):
        return []
