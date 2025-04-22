from decimal import Decimal

from app.area.models.area import Area
from processing.models.billing.account import Tenant
from processing.models.billing.area_bind import AreaBind
from processing.models.choice.gis_xlsx import LIVING_AREA_GIS_TYPES_CHOICES, \
    LivingAreaGisTypes
from processing.models.house_choices import HouseEngineeringStatusTypes, \
    HOUSE_ENGINEERING_STATUS_CHOICES
from processing.models.choices import get_choice_str
from .base import BaseGISDataProducer


class HousesPropertiesFields:
    ADDRESS = 'Адрес'
    FIAS_GUID = 'Глобальный уникальный идентификатор дома по ФИАС' \
                '/Идентификационный код дома в ГИС ЖКХ'
    OKTMO = 'ОКТМО'
    STATE = 'Состояние'
    FULL_AREA = 'Общая площадь здания'
    PASSPORT_LIVING_AREA_TOTAL = \
        'Общая площадь жилых помещений по паспорту помещения'
    SERVICE_DATE_YEAR = 'Год ввода в эксплуатацию'
    FLOORS_NUMBER = 'Кол-во этажей'
    UNDERGROUND_FLOORS_NUMBER = 'Кол-во подземных этажей'
    MIN_FLOORS_NUMBER = 'Количество этажей, наименьшее'
    TIMEZONE = 'Часовая зона по Olson'
    IS_CULTURAL_HERITAGE = 'Наличие статуса объекта культурного наследия'
    CADASTRAL_NUMBER = \
        'Кадастровый номер (для связывания сведений с ГКН и ЕГРП)'


class HouseNonLivingAreasFields:
    ADDRESS = 'Адрес МКД, в котором расположено нежилое помещение'
    AREA_NUMBER = 'Номер помещения'
    IS_PUBLIC_PROPERTY = \
        'Помещение, составляющее общее имущество в многоквартирном доме'
    NON_LIVING_AREA_TOTAL = \
        'Общая площадь нежилого помещения по паспорту помещения'
    CADASTRAL_NUMBER = \
        'Кадастровый номер (для связывания сведений с ГКН и ЕГРП)'
    APPROVED = 'Информация подтверждена поставщиком'


class HousePorchesFields:
    ADDRESS = 'Адрес МКД, в котором расположен подъезд'
    PORCH_NUMBER = 'Номер подъезда'
    NUMBER_OF_FLOORS = 'Этажность'
    CONSTRUCTION_DATE = 'Год постройки'
    APPROVED = 'Информация подтверждена поставщиком'


class HouseLivingRoomsFields:
    ADDRESS = 'Адрес МКД, в котором расположено жилое помещение'
    AREA_NUMBER = 'Номер помещения'
    PORCH_NUMBER = 'Номер подъезда'
    AREA_TYPE = 'Характеристика помещения'
    AREA_TOTAL = 'Общая площадь жилого помещения по паспорту помещения'
    AREA_LIVING = 'Жилая площадь жилого помещения по паспорту помещения'
    CADASTRAL_NUMBER = \
        'Кадастровый номер (для связывания сведений с ГКН и ЕГРП)'
    APPROVED = 'Информация подтверждена поставщиком'


class HouseRoomsFields:
    ADDRESS = 'Адрес МКД, в котором расположено жилое помещение'
    AREA_NUMBER = 'Номер помещения'
    ROOM_NUMBER = 'Номер комнаты'
    ROOM_AREA_TOTAL = 'Площадь'
    CADASTRAL_NUMBER = \
        'Кадастровый номер (для связывания сведений с ГКН и ЕГРП)'
    APPROVED = 'Информация подтверждена поставщиком'


class HouseLiftsFields:
    ADDRESS = 'Адрес МКД, в котором  расположен подъезд'
    PORCH_NUMBER = 'Номер подъезда'
    SERIAL_NUMBER = 'Заводской номер'
    LIFT_TYPE = 'Тип лифта'
    SERVICE_DEADLINE = 'Предельный срок эксплуатации'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoHouseFields:  # Информация о МКД
    ADDRESS = 'Адрес МКД, для которого задается информация'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoConstructionFields:  # Конструктивные элементы
    ADDRESS = 'Адрес МКД, для которого задается информация'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoNetworksFields:  # Внутридомовые сети
    ADDRESS = 'Адрес МКД, для которого задается информация'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoNonLivingAreasFields:
    """
    Информация о нежилых помещениях
    """
    ADDRESS = 'Адрес МКД, для которого задается информация'
    AREA_NUMBER = 'Номер помещения'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoLiftsFields:  # Информация о лифтах
    ADDRESS = 'Адрес МКД, для которого задается информация'
    PORCH_NUMBER = 'Номер подъезда'
    SERIAL_NUMBER = 'Заводской номер'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoLivingAreasFields:  # Информация о жилых помещениях
    ADDRESS = 'Адрес МКД, для которого задается информация'
    AREA_NUMBER = 'Номер помещения'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HouseAdditionalInfoRoomsFields:  # Информация о комнатах
    ADDRESS = 'Адрес МКД, для которого задается информация'
    AREA_NUMBER = 'Номер помещения'
    ROOM_NUMBER = 'Номер комнаты'
    PARAM = 'Параметр'
    VALUE = 'Значение'
    # PROCESSING_STATUS = 'Статус обработки'


class HousesDataProducer(BaseGISDataProducer):
    XLSX_TEMPLATE = 'templates/gis/houses_uo_11_11_0_12.xlsx'
    XLSX_WORKSHEETS = {
        'Характеристики МКД': {
            'entry_produce_method': 'get_entry_house_properties',
            'title': 'Характеристики МКД',
            'start_row': 3,
            'columns': {
                HousesPropertiesFields.ADDRESS: 'A',
                HousesPropertiesFields.FIAS_GUID: 'B',
                HousesPropertiesFields.OKTMO: 'C',
                HousesPropertiesFields.STATE: 'D',
                HousesPropertiesFields.FULL_AREA: 'E',
                HousesPropertiesFields.SERVICE_DATE_YEAR: 'F',
                HousesPropertiesFields.FLOORS_NUMBER: 'G',
                HousesPropertiesFields.UNDERGROUND_FLOORS_NUMBER: 'H',
                HousesPropertiesFields.MIN_FLOORS_NUMBER: 'I',
                HousesPropertiesFields.TIMEZONE: 'J',
                HousesPropertiesFields.IS_CULTURAL_HERITAGE: 'K',
                HousesPropertiesFields.CADASTRAL_NUMBER: 'L',
            }
        },
        'Нежилые помещения': {
            'entry_produce_method': 'get_entry_non_living_areas',
            'title': 'Нежилые помещения',
            'start_row': 3,
            'columns': {
                HouseNonLivingAreasFields.ADDRESS: 'A',
                HouseNonLivingAreasFields.AREA_NUMBER: 'B',
                HouseNonLivingAreasFields.IS_PUBLIC_PROPERTY: 'C',
                HouseNonLivingAreasFields.NON_LIVING_AREA_TOTAL: 'D',
                HouseNonLivingAreasFields.CADASTRAL_NUMBER: 'E',
                HouseNonLivingAreasFields.APPROVED: 'F',
            }
        },
        'Подъезды': {
            'entry_produce_method': 'get_entry_porches',
            'title': 'Подъезды',
            'start_row': 3,
            'columns': {
                HousePorchesFields.ADDRESS: 'A',
                HousePorchesFields.PORCH_NUMBER: 'B',
                HousePorchesFields.NUMBER_OF_FLOORS: 'C',
                HousePorchesFields.CONSTRUCTION_DATE: 'D',
                HousePorchesFields.APPROVED: 'E',
            }
        },
        'Жилые помещения': {
            'entry_produce_method': 'get_entry_living_areas',
            'title': 'Жилые помещения',
            'start_row': 3,
            'columns': {
                HouseLivingRoomsFields.ADDRESS: 'A',
                HouseLivingRoomsFields.AREA_NUMBER: 'B',
                HouseLivingRoomsFields.PORCH_NUMBER: 'C',
                HouseLivingRoomsFields.AREA_TYPE: 'D',
                HouseLivingRoomsFields.AREA_TOTAL: 'E',
                HouseLivingRoomsFields.AREA_LIVING: 'F',
                HouseLivingRoomsFields.CADASTRAL_NUMBER: 'G',
                HouseLivingRoomsFields.APPROVED: 'H',
            }
        },
        'Комнаты': {
            'entry_produce_method': 'get_entry_rooms',
            'title': 'Комнаты',
            'start_row': 3,
            'columns': {
                HouseRoomsFields.ADDRESS: 'A',
                HouseRoomsFields.AREA_NUMBER: 'B',
                HouseRoomsFields.ROOM_NUMBER: 'C',
                HouseRoomsFields.ROOM_AREA_TOTAL: 'D',
                HouseRoomsFields.CADASTRAL_NUMBER: 'E',
                HouseRoomsFields.APPROVED: 'F',
            }
        },
        'Лифты': {
            'entry_produce_method': 'get_entry_lifts',
            'title': 'Лифты',
            'start_row': 3,
            'columns': {
                HouseLiftsFields.ADDRESS: 'A',
                HouseLiftsFields.PORCH_NUMBER: 'B',
                HouseLiftsFields.SERIAL_NUMBER: 'C',
                HouseLiftsFields.LIFT_TYPE: 'D',
                HouseLiftsFields.SERVICE_DEADLINE: 'E',
            }
        },

        # Дополнительная информация (Параметр - Значение)

        # 'Информация о МКД': {
        #     'entry_produce_method': 'get_entry_house_additional_info_house',
        #     'start_row': 3,
        #     'columns': {
        #         HouseAdditionalInfoHouseFields.ADDRESS: 'A',
        #         HouseAdditionalInfoHouseFields.PARAM: 'B',
        #         HouseAdditionalInfoHouseFields.VALUE: 'C',
        #     }
        # },

        # 'Конструктивные элементы': {
        #     'entry_produce_method': 'get_entry_house_additional_info_construction',
        #     'start_row': 3,
        #     'columns': {
        #         HouseAdditionalInfoConstructionFields.ADDRESS: 'A',
        #         HouseAdditionalInfoConstructionFields.PARAM: 'B',
        #         HouseAdditionalInfoConstructionFields.VALUE: 'C',
        #     }
        # },

        # 'Внутридомовые сети': {
        #     'entry_produce_method': 'get_entry_house_additional_info_networks',
        #     'start_row': 3,
        #     'columns': {
        #         HouseAdditionalInfoNetworksFields.ADDRESS: 'A',
        #         HouseAdditionalInfoNetworksFields.PARAM: 'B',
        #         HouseAdditionalInfoNetworksFields.VALUE: 'C',
        #     }
        # },

        # 'Информация о нежилых помещениях': {
        #     'entry_produce_method':
        #         'get_entry_house_additional_info_non_living_areas',
        #     'start_row': 3,
        #     'columns': {
        #         HouseAdditionalInfoNonLivingAreasFields.ADDRESS: 'A',
        #         HouseAdditionalInfoNonLivingAreasFields.AREA_NUMBER: 'B',
        #         HouseAdditionalInfoNonLivingAreasFields.PARAM: 'C',
        #         HouseAdditionalInfoNonLivingAreasFields.VALUE: 'D',
        #     }
        # },

        'Информация о лифтах': {
            'entry_produce_method': 'get_entry_house_additional_info_lifts',
            'start_row': 3,
            'columns': {
                HouseAdditionalInfoLiftsFields.ADDRESS: 'A',
                HouseAdditionalInfoLiftsFields.PORCH_NUMBER: 'B',
                HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: 'C',
                HouseAdditionalInfoLiftsFields.PARAM: 'D',
                HouseAdditionalInfoLiftsFields.VALUE: 'E',
            }
        },

        # 'Информация о жилых помещениях': {
        #     'entry_produce_method':
        #         'get_entry_house_additional_info_living_areas',
        #     'start_row': 3,
        #     'columns': {
        #         HouseAdditionalInfoLivingAreasFields.ADDRESS: 'A',
        #         HouseAdditionalInfoLivingAreasFields.AREA_NUMBER: 'B',
        #         HouseAdditionalInfoLivingAreasFields.PARAM: 'C',
        #         HouseAdditionalInfoLivingAreasFields.VALUE: 'D',
        #     }
        # },

        # 'Информация о комнатах': {
        #     'entry_produce_method': 'get_entry_house_additional_info_rooms',
        #     'start_row': 3,
        #     'columns': {
        #         HouseAdditionalInfoRoomsFields.ADDRESS: 'A',
        #         HouseAdditionalInfoRoomsFields.AREA_NUMBER: 'B',
        #         HouseAdditionalInfoRoomsFields.ROOM_NUMBER: 'C',
        #         HouseAdditionalInfoRoomsFields.PARAM: 'D',
        #         HouseAdditionalInfoRoomsFields.VALUE: 'E',
        #     }
        # },
    }

    def get_entry_house_properties(self, entry_source, export_task):
        house = entry_source['house']

        entry = {
            HousesPropertiesFields.ADDRESS: house.address,
            HousesPropertiesFields.FIAS_GUID: house.gis_fias or house.fias_house_guid,
            HousesPropertiesFields.OKTMO: Decimal(house.OKTMO) if house.OKTMO and house.OKTMO.isdigit() else '',
            HousesPropertiesFields.STATE: get_choice_str(HOUSE_ENGINEERING_STATUS_CHOICES, house.engineering_status, default=HouseEngineeringStatusTypes.GOOD),
            HousesPropertiesFields.FULL_AREA: round(house.area_overall or 0, 4),
            HousesPropertiesFields.SERVICE_DATE_YEAR: house.service_date.year if house.service_date else '',
            HousesPropertiesFields.FLOORS_NUMBER: max([porch.max_floor for porch in house.porches] + [0]),
            HousesPropertiesFields.UNDERGROUND_FLOORS_NUMBER: abs(min([porch.min_floor for porch in house.porches] + [0])),
            HousesPropertiesFields.MIN_FLOORS_NUMBER: min([porch.max_floor for porch in house.porches] + [0]),
            HousesPropertiesFields.TIMEZONE: house.gis_timezone,
            HousesPropertiesFields.IS_CULTURAL_HERITAGE: 'Да' if getattr(house, 'is_cultural_heritage', False) else 'Нет',  # TODO choices
            # TODO Обязательное поле, возможно нужно убрать вариант "Нет" по умолчанию
            HousesPropertiesFields.CADASTRAL_NUMBER: house.cadastral_number if getattr(house, 'cadastral_number', False) else 'Нет',
        }

        return entry

    def _get_areas_by_type(self, house_id, provider_id, areas_type):
        house_areas = list(Area.objects(__raw__={
            'house._id': house_id,
            '_type': areas_type,
            'is_deleted': {'$ne': True},
        }))
        provider_binds = AreaBind.objects(
            area__in=[a.pk for a in house_areas],
            provider=provider_id,
            closed=None,
        ).distinct('area')
        areas = [a for a in house_areas if a.pk in provider_binds]
        areas.sort(key=lambda area: area.order)
        return areas

    def get_entry_non_living_areas(self, entry_source, export_task):
        house = entry_source['house']
        provider = entry_source['provider']

        multi_entry = []
        non_living_areas = self._get_areas_by_type(
            house.pk, provider.pk, 'NotLivingArea')

        for nl_area in non_living_areas:
            str_number = nl_area.str_number
            if str_number.endswith('Н'):
                str_number = '{}-Н'.format(str_number[0: -1])
            entry = {
                HouseNonLivingAreasFields.ADDRESS: house.address,
                HouseNonLivingAreasFields.AREA_NUMBER: str_number,
                HouseNonLivingAreasFields.IS_PUBLIC_PROPERTY: 'Нет',
                HouseNonLivingAreasFields.NON_LIVING_AREA_TOTAL: round(nl_area.area_total, 4),
                HouseNonLivingAreasFields.CADASTRAL_NUMBER: nl_area.cadastral_number if getattr(nl_area, 'cadastral_number', False) else 'Нет',
                HouseNonLivingAreasFields.APPROVED: 'Да',
            }

            multi_entry.append(entry)

        return multi_entry

    def get_entry_porches(self, entry_source, export_task):
        house = entry_source['house']

        multi_entry = []

        for porch in house.porches:
            entry = {
                HousePorchesFields.ADDRESS: house.address,
                HousePorchesFields.PORCH_NUMBER: porch.number,
                HousePorchesFields.NUMBER_OF_FLOORS: porch.max_floor,
                HousePorchesFields.CONSTRUCTION_DATE: (
                    porch.build_date.date().strftime("%Y")
                    if getattr(porch, 'build_date', False)
                    else ''
                ),
                HousePorchesFields.APPROVED: 'Да',
            }

            multi_entry.append(entry)

        return multi_entry

    def get_entry_living_areas(self, entry_source, export_task):
        house = entry_source['house']
        provider = entry_source['provider']

        multi_entry = []

        living_areas = self._get_areas_by_type(
            house.pk, provider.pk, 'LivingArea')

        porches = {porch.id: porch for porch in house.porches}

        for living_area in living_areas:
            area_type = LivingAreaGisTypes.COMMUNAL if living_area.is_shared else LivingAreaGisTypes.PRIVATE
            entry = {
                HouseLivingRoomsFields.ADDRESS: house.address,
                HouseLivingRoomsFields.AREA_NUMBER: living_area.str_number,
                HouseLivingRoomsFields.PORCH_NUMBER: porches[living_area.porch].number if living_area.porch in porches else '',
                HouseLivingRoomsFields.AREA_TYPE: get_choice_str(LIVING_AREA_GIS_TYPES_CHOICES, area_type),
                HouseLivingRoomsFields.AREA_TOTAL: round(living_area.area_total, 4),
                HouseLivingRoomsFields.AREA_LIVING: round(living_area.area_living, 4) if living_area.area_living else '',
                HouseLivingRoomsFields.CADASTRAL_NUMBER: living_area.cadastral_number if getattr(living_area, 'cadastral_number', False) else 'Нет',
                HouseLivingRoomsFields.APPROVED: 'Да',
            }

            multi_entry.append(entry)

        return multi_entry

    def get_entry_rooms(self, entry_source, export_task):
        house = entry_source['house']
        multi_entry = []

        # Только комнаты из комунальных квартир
        areas = Area.objects(
            _type__in=['LivingArea', 'NotLivingArea'],
            is_shared=True,
            is_deleted__ne=True,
            house__id=house.id
        )

        for area in areas:
            for room in area.rooms:
                entry = {
                    HouseRoomsFields.ADDRESS: house.address,
                    HouseRoomsFields.AREA_NUMBER: area.str_number,
                    HouseRoomsFields.ROOM_NUMBER: room.number,
                    HouseRoomsFields.ROOM_AREA_TOTAL: round(room.square, 4),
                    HouseRoomsFields.CADASTRAL_NUMBER: room.cadastral_number if getattr(room, 'cadastral_number', False) else 'Нет',
                    HouseRoomsFields.APPROVED: 'Да',
                }

                multi_entry.append(entry)

        return multi_entry

    def get_entry_lifts(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        for porch in house.porches:
            for lift in porch.lifts:
                entry = {
                    HouseLiftsFields.ADDRESS: house.address or '',
                    HouseLiftsFields.PORCH_NUMBER: porch.number or '',
                    HouseLiftsFields.SERIAL_NUMBER: lift.number or '',
                    HouseLiftsFields.LIFT_TYPE: 'Грузовой' if lift.capacity and lift.capacity > 600 else 'Пассажирский',  # TODO Сделать по-нормальному
                    HouseLiftsFields.SERVICE_DEADLINE: '',
                }

                multi_entry.append(entry)

        return multi_entry

    # Additional Info

    def get_entry_house_additional_info_house(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        # Год постройки (целое, множественный)
        if house.build_date and house.build_date.year:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Год постройки (целое, множественный)',
                HouseAdditionalInfoHouseFields.VALUE: house.build_date.year,
            })

        # Стадия жизненного цикла (перечислимый): [Строящийся, Эксплуатируемый, Выведен из эксплуатации, Снесенный]
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Стадия жизненного цикла (перечислимый)',
            HouseAdditionalInfoHouseFields.VALUE: 'Эксплуатируемый',
        })

        # Серия, тип проекта здания (строка)
        if house.build_date and house.build_date.year:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Серия, тип проекта здания (строка)',
                HouseAdditionalInfoHouseFields.VALUE: house.build_date.year,
            })

        # Дата проведения энергетического обследования (дата)
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Дата проведения энергетического обследования (дата)',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.energy_efficiency.examined_at,
            })

        except AttributeError:
            pass

        # Общий износ здания (вещественное), %	TechPassport.deterioration
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Общий износ здания (вещественное), %',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.deterioration,
            })

        except AttributeError:
            pass

        # - Дата, на которую установлен износ здания (дата)	InspectionReport.date

        # - Класс энергетической эффективности (перечислимый):	EnergyEfficiency (Другие классы!)

        # Разновидность территорий (перечислимый):
        #     Сельские территории
        #     Иные территории  # Что такое "Иные территории" ?
        #     Городские населенные пункты
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Разновидность территорий (перечислимый)',
            HouseAdditionalInfoHouseFields.VALUE: 'Сельские территории' if house.is_rural() else 'Городские населенные пункты',
        })

        # Общежитие(логическое) HostelArea
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Общежитие(логическое)',
            HouseAdditionalInfoHouseFields.VALUE: 'нет',  # TODO
        })

        # - Количество технических этажей (целое), шт

        # Количество подъездов в многоквартирном доме (целое), шт	HousePassport.TechPassport.
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество подъездов в многоквартирном доме (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.count_porch,
                # HouseAdditionalInfoHouseFields.VALUE: len(house.porches),  # как вариант
            })
        except AttributeError:
            pass

        # Количество лифтов (целое), шт
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Количество лифтов (целое), шт',
            HouseAdditionalInfoHouseFields.VALUE: house.lift_count,
        })

        # Общая площадь жилых помещений (вещественное),кв.м.
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM:
                'Общая площадь жилых помещений (вещественное),кв.м.',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(
                house__id=house.id,
                _type='LivingArea'
            ).sum('area_total'),
        })

        # Общая площадь нежилых помещений,
        # за исключением помещений общего пользования (вещественное),кв.м
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM:
                'Общая площадь нежилых помещений, за исключением '
                'помещений общего пользования (вещественное),кв.м',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(
                house__id=house.id,
                _type='NotLivingArea'
            ).sum('area_total'),
        })

        # TODO INDEX Area._type

        # Общая площадь жилых помещений (вещественное), кв.м.	sum(Area)
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Общая площадь жилых помещений (вещественное), кв.м.',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(house__id=house.id, _type='LivingArea').sum('area_total'),
        })

        # Количество жилых помещений (квартир) (целое), кварт
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Количество жилых помещений (квартир) (целое), кварт',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(house__id=house.id, _type='LivingArea').count(),
        })

        # - Жилая площадь (вещественное), кв.м	? Площадь комнат в жилых квартирах?

        # Общая площадь нежилых помещений, за исключением помещений общего пользования (вещественное), кв.м	sum(NonLivingArea.area)
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Общая площадь нежилых помещений, за исключением помещений общего пользования (вещественное), кв.м',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(house__id=house.id, _type='NotLivingArea', common_property__ne=True).sum('area_total'),
        })

        # Количество нежилых помещений (целое), шт	count(NonLivingArea.area)
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Количество нежилых помещений (целое), шт',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(house__id=house.id, _type='NotLivingArea').count(),
        })

        # Площадь всех помещений общего имущества (вещественное), кв.м
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Площадь всех помещений общего имущества (вещественное), кв.м',
            HouseAdditionalInfoHouseFields.VALUE: Area.objects(house__id=house.id, _type='NotLivingArea', common_property=True).sum('area_total'),
        })

        # Площадь лестничных маршей и площадок (вещественное), кв.м	area_mop_stair
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Площадь лестничных маршей и площадок (вещественное), кв.м',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.area_mop_stair,
            })
        except AttributeError:
            pass

        # Площадь коридоров мест общего пользования (вещественное), кв.м	area_mop_lobby
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Площадь коридоров мест общего пользования (вещественное), кв.м',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.area_mop_lobby,
            })
        except AttributeError:
            pass

        # Площадь технических этажей (вещественное), кв.м	area_tech_floor
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Площадь технических этажей (вещественное), кв.м',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.area_tech_floor,
            })
        except AttributeError:
            pass

        # Площадь убежищ (вещественное), кв.м	area_shelter
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Площадь убежищ (вещественное), кв.м',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.area_shelter,
            })
        except AttributeError:
            pass

        # Средняя высота помещений (вещественное), м	House.default_rooms_height
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Средняя высота помещений (вещественное), м',
            HouseAdditionalInfoHouseFields.VALUE: house.default_rooms_height,
        })

        # Площадь чердачных помещений (вещественное), кв.м	House.area_garret
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Площадь чердачных помещений (вещественное), кв.м',
            HouseAdditionalInfoHouseFields.VALUE: house.area_garret,
        })

        # Площадь подвала (строка), кв.м	House.area_basements
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Площадь подвала (строка), кв.м',
            HouseAdditionalInfoHouseFields.VALUE: house.area_basements,
        })

        # Кадастровый номер земельного участка (строка, множественный)	cadastral
        multi_entry.append({
            HouseAdditionalInfoHouseFields.ADDRESS: house.address,
            HouseAdditionalInfoHouseFields.PARAM: 'Кадастровый номер земельного участка (строка, множественный)',
            HouseAdditionalInfoHouseFields.VALUE: house.cadastral_number,
        })

        # Количество этажей, наименьшее (целое), шт	count_floor_min
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество этажей, наименьшее (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.tech_info.count_floor_min,
            })
        except AttributeError:
            pass

        return multi_entry

    def get_entry_house_additional_info_construction(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        # Количество металлических дверей убежищ (целое), шт
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество металлических дверей убежищ (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: house.passport.count_door_shelter,
            })
        except AttributeError:
            pass

        # - Количество лестничных площадок (целое)

        return multi_entry

    def get_entry_house_additional_info_networks(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        # Количество вводов внутридомовой инженерной системы электроснабжения в многоквартирный дом (количество точек поставки) (целое), шт  #  ResourceInput
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество вводов внутридомовой инженерной системы электроснабжения в многоквартирный дом (количество точек поставки) (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: len([resource for resource in house.passport.resources if resource.type == 'SЭЛ']),
            })
        except AttributeError:
            pass

        # Общее количество светильников общего имущества (целое), шт	sum(PowerEquipmentInfo.lamps_)
        try:
            lamps_num = sum((
                house.passport.equipment.power.lamps_daylight,
                house.passport.equipment.power.lamps_incandescent,
                house.passport.equipment.power.lamps_mercury,
                house.passport.equipment.power.lamps_outdoor,
            ))

            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Общее количество светильников общего имущества (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: lamps_num,
            })
        except AttributeError:
            pass

        # Тип внутридомовой системы отопления (перечислимый):	 HeatEquipmentInfo
        #     Центральная
        #     Печная
        #     Электрическая
        #     Домовая котельная
        #     Квартирное отопление (котел)
        try:
            gis_heat_types = {
                'central': 'Центральная',
                'auto': 'Домовая котельная',
                'aprt': 'Квартирное отопление (котел)',
                'oven': 'Печная',
            }

            if house.passport.equipment.heat.type in gis_heat_types:
                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoHouseFields.PARAM: 'Тип внутридомовой системы отопления (перечислимый)',
                    HouseAdditionalInfoHouseFields.VALUE: gis_heat_types[house.passport.equipment.heat.type],
                })

        except AttributeError:
            pass

        # Количество вводов системы отопления в многоквартирный дом (количество точек поставки) (целое), шт	 ResourceInput
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество вводов системы отопления в многоквартирный дом (количество точек поставки) (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: len([resource for resource in house.passport.resources if resource.type == 'SОТ']),
            })
        except AttributeError:
            pass

        # Количество тепловых узлов (целое), шт	 heat_nodes_number ?
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество тепловых узлов (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: sum([resource.heat_nodes_number for resource in house.passport.resources if resource.type == 'SОТ']),
            })
        except AttributeError:
            pass

        # Тип отопительных приборов (перечислимый, множественный):
        #     Радиатор	 bool( radiators_stairwell_number + radiators_apartment_number )
        #     Конвектор	 convectors_number
        try:
            if bool(house.passport.equipment.heat.radiators_stairwell_number + house.passport.equipment.heat.radiators_apartment_number):
                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoHouseFields.PARAM: 'Тип отопительных приборов (перечислимый, множественный)',
                    HouseAdditionalInfoHouseFields.VALUE: 'Радиатор',
                })

            if bool(house.passport.equipment.heat.convectors_number):
                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoHouseFields.PARAM: 'Тип отопительных приборов (перечислимый, множественный)',
                    HouseAdditionalInfoHouseFields.VALUE: 'Конвектор',
                })
        except AttributeError:
            pass

        # Количество отопительных приборов (целое), шт	sum(prev)
        try:
            heat_equip_sum = sum((
                house.passport.equipment.heat.radiators_stairwell_number,
                house.passport.equipment.heat.radiators_apartment_number,
                house.passport.equipment.heat.convectors_number
            ))

            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество отопительных приборов (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: heat_equip_sum,
            })
        except AttributeError:
            pass

        # - Наличие системы ГВС (логическое)	по услугам в доме?

        # Количество стояков (вещественное), шт	risers_number
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество стояков (вещественное), шт',
                HouseAdditionalInfoHouseFields.VALUE: sum([resource.risers_number for resource in house.passport.resources if resource.type == 'ХВС']),
            })
        except AttributeError:
            pass

        # - Наличие системы ХВС (логическое)

        # Количество водомерных узлов (целое), шт	measuring_number
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Количество водомерных узлов (целое), шт',
                HouseAdditionalInfoHouseFields.VALUE: sum([resource.measuring_number for resource in house.passport.resources if resource.type == 'SХВ']),
            })
        except AttributeError:
            pass

        # - Наличие системы газоснабжения (логическое)	по привязке?

        # Общая протяженность системы газоснабжения (вещественное), м	NaturalGasEquipmentInfo.total_length
        try:
            multi_entry.append({
                HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                HouseAdditionalInfoHouseFields.PARAM: 'Общая протяженность системы газоснабжения (вещественное), м',
                HouseAdditionalInfoHouseFields.VALUE: sum([resource.total_length for resource in house.passport.resources if resource.type == 'SГЗ']),
            })
        except AttributeError:
            pass

        # Тип системы вентиляции (перечислимый):	VentilationEquipmentInfo
        #     Приточная
        #     Вытяжная
        #     Приточно-вытяжная
        try:
            gis_vent_types = {
                'forced': 'Приточная',
                'exhaust': 'Вытяжная',
                'purge': 'Приточно-вытяжная',
            }

            if house.passport.equipment.ventilation.type in gis_vent_types:
                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoHouseFields.PARAM: 'Тип системы вентиляции (перечислимый)',
                    HouseAdditionalInfoHouseFields.VALUE: gis_vent_types[house.passport.equipment.ventilation.type],
                })

        except AttributeError:
            pass

        return multi_entry

    def get_entry_house_additional_info_non_living_areas(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        return multi_entry

    def get_entry_house_additional_info_lifts(self, entry_source, export_task):

        multi_entry = []
        house = entry_source['house']

        for porch in house.porches:
            for lift in porch.lifts:
                """
                # Инвентарный номер (строка)	number
                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Инвентарный номер (строка)',
                    HouseAdditionalInfoHouseFields.VALUE: lift.number,  # Бесполезная строка ?
                })
                """

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Наименование завода изготовителя (строка)',
                    HouseAdditionalInfoHouseFields.VALUE: lift.manufacturer,
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Год модернизации (дата, множественный)',
                    HouseAdditionalInfoHouseFields.VALUE: lift.modernization_date,
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Тип шахты лифта (перечислимый)',
                    HouseAdditionalInfoHouseFields.VALUE: 'Приставная' if lift.well_type == 'ext' else 'Встроенная',  # TODO choices
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Скорость подъема (вещественное), м/с',
                    HouseAdditionalInfoHouseFields.VALUE: lift.climb_rate,
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Количество остановок (целое), шт',
                    HouseAdditionalInfoHouseFields.VALUE: lift.stop_number,
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Наличие частотного регулирования дверей/привода (логическое)',
                    HouseAdditionalInfoHouseFields.VALUE: 'да' if lift.has_freq_reg else 'нет',
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Год ввода в эксплуатацию (дата)',
                    HouseAdditionalInfoHouseFields.VALUE: lift.started_at,
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Грузоподъемность (вещественное), кг',
                    HouseAdditionalInfoHouseFields.VALUE: lift.capacity,
                })

                multi_entry.append({
                    HouseAdditionalInfoHouseFields.ADDRESS: house.address,
                    HouseAdditionalInfoLiftsFields.PORCH_NUMBER: porch.number,
                    HouseAdditionalInfoLiftsFields.SERIAL_NUMBER: lift.number,
                    HouseAdditionalInfoHouseFields.PARAM: 'Нормативный срок службы (целое), лет',
                    HouseAdditionalInfoHouseFields.VALUE: lift.deadline_years,
                })

        return multi_entry

    def get_entry_house_additional_info_living_areas(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        for living_area in Area.objects(is_deleted__ne=True, _type='LivingArea', house__id=house.id):

            # Количество комнат (перечислимый), шт:
            #     1-комнатные
            #     2-комнатные
            #     3-комнатные
            #     4-комнатные
            #     5-комнатные
            #     6-комнатные
            #     7 и более комнат

            if len(living_area.rooms) >= 1:
                if len(living_area.rooms) == 1: area_room_type = '1-комнатные'
                elif len(living_area.rooms) == 2: area_room_type = '2-комнатные'
                elif len(living_area.rooms) == 3: area_room_type = '3-комнатные'
                elif len(living_area.rooms) == 4: area_room_type = '4-комнатные'
                elif len(living_area.rooms) == 5: area_room_type = '5-комнатные'
                elif len(living_area.rooms) == 6: area_room_type = '6-комнатные'
                elif len(living_area.rooms) >= 7: area_room_type = '7 и более комнат'

                multi_entry.append({
                    HouseAdditionalInfoLivingAreasFields.ADDRESS: house.address,
                    HouseAdditionalInfoLivingAreasFields.AREA_NUMBER: living_area.str_number,
                    HouseAdditionalInfoLivingAreasFields.PARAM: 'Количество комнат (перечислимый), шт',
                    HouseAdditionalInfoLivingAreasFields.VALUE: area_room_type,
                })

            # Количество граждан, проживающих в квартире (целое)
            tenants_count = Tenant.objects(
                is_deleted__ne=True,
                _type='Tenant',
                area__id=living_area.id,
            ).count()
            multi_entry.append({
                HouseAdditionalInfoLivingAreasFields.ADDRESS: house.address,
                HouseAdditionalInfoLivingAreasFields.AREA_NUMBER: living_area.str_number,
                HouseAdditionalInfoLivingAreasFields.PARAM: 'Количество граждан, проживающих в квартире (целое)',
                HouseAdditionalInfoLivingAreasFields.VALUE: tenants_count,
            })

            # - Вид формы собственности (перечислимый):
            #     Частный жилищный фонд
            #     Государственный жилищный фонд
            #     Муниципальный жилищный фонд

        return multi_entry

    def get_entry_house_additional_info_rooms(self, entry_source, export_task):

        house = entry_source['house']
        multi_entry = []

        for shared_area in Area.objects(is_shared=True, is_deleted__ne=True, house__id=house.id):
            for room in shared_area.rooms:

                # Количество граждан, проживающих в комнате в коммунальной квартире (целое)	count(Account.area.room == room.id) если account.area.is_shared
                tenants_count = Tenant.objects(
                    is_deleted__ne=True,
                    _type='Tenant',
                    rooms=room.id,
                    area__id=shared_area.id,
                ).count()
                multi_entry.append({
                    HouseAdditionalInfoRoomsFields.ADDRESS: house.address,
                    HouseAdditionalInfoRoomsFields.AREA_NUMBER: shared_area.str_number,
                    HouseAdditionalInfoRoomsFields.ROOM_NUMBER: room.number,
                    HouseAdditionalInfoRoomsFields.PARAM: 'Количество граждан, проживающих в комнате в коммунальной квартире (целое)',
                    HouseAdditionalInfoRoomsFields.VALUE: tenants_count,
                })

                '''
                Тип жилого помещения (перечислимый):
                    -В городских населенных пунктах, не оборудованные 
                    стационарными электроплитами, электроотопительными и 
                    электронагревательными установками
                    -В городских населенных пунктах, оборудованные стационарными 
                    электроплитами и не оборудованные электроотопительными и 
                    электронагревательными установками
                    -В городских населенных пунктах, оборудованные 
                    электроотопительными и (или) электронагревательными 
                    установками
                    -В сельских населенных пунктах, не оборудованные 
                    стационарными электроплитами, электроотопительными и 
                    электронагревательными установками
                    -В сельских населенных пунктах, оборудованные стационарными 
                    электроплитами и не оборудованные электроотопительными и 
                    электронагревательными установками
                    -В сельских населенных пунктах, оборудованные 
                    электроотопительными и (или) электронагревательными 
                    установками
                '''
                is_rural = house.is_rural()
                if (
                        not is_rural
                        and shared_area.stove_type != 'electric'
                        and shared_area.has_boiler is not True
                ):
                    area_type = \
                        'В городских населенных пунктах, не оборудованные ' \
                        'стационарными электроплитами, электроотопительными ' \
                        'и электронагревательными установками'
                elif (
                        not is_rural
                        and shared_area.stove_type == 'electric'
                        and shared_area.has_boiler is not True
                ):
                    area_type = \
                        'В городских населенных пунктах, оборудованные ' \
                        'стационарными электроплитами и не оборудованные ' \
                        'электроотопительными и электронагревательными ' \
                        'установками'
                elif (
                        not is_rural
                        and shared_area.stove_type == 'electric'
                        and shared_area.has_boiler
                ):
                    area_type = \
                        'В городских населенных пунктах, оборудованные ' \
                        'электроотопительными и (или) электронагревательными ' \
                        'установками'
                elif (
                        is_rural
                        and shared_area.stove_type != 'electric'
                        and shared_area.has_boiler is not True
                ):
                    area_type = \
                        'В сельских населенных пунктах, не оборудованные ' \
                        'стационарными электроплитами, электроотопительными ' \
                        'и электронагревательными установками'
                elif (
                        is_rural
                        and shared_area.stove_type == 'electric'
                        and shared_area.has_boiler is not True
                ):
                    area_type = \
                        'В сельских населенных пунктах, оборудованные ' \
                        'стационарными электроплитами и не оборудованные ' \
                        'электроотопительными и электронагревательными ' \
                        'установками'
                elif (
                        is_rural
                        and shared_area.stove_type == 'electric'
                        and shared_area.has_boiler
                ):
                    area_type = \
                        'В сельских населенных пунктах, оборудованные ' \
                        'электроотопительными и (или) электронагревательными ' \
                        'установками'

                else:
                    raise ValueError(
                        'Невозможно определить тип жилого помещения',
                    )

                multi_entry.append({
                    HouseAdditionalInfoRoomsFields.ADDRESS: house.address,
                    HouseAdditionalInfoRoomsFields.AREA_NUMBER: shared_area.str_number,
                    HouseAdditionalInfoRoomsFields.ROOM_NUMBER: room.number,
                    HouseAdditionalInfoRoomsFields.PARAM: 'Тип жилого помещения (перечислимый)',
                    HouseAdditionalInfoRoomsFields.VALUE: area_type,
                })

                # Наличие электрооборудования (перечислимый, множественный):
                #     оборудован в установленном порядке стационарными электроплитами для приготовления пищи
                #     не оборудован стационарными электроплитами для приготовления пищи
                #     оборудован в установленном порядке электроотопительными, электронагревательными установками для целей горячего водоснабжения
                #     не оборудован электроотопительными, электронагревательными установками для целей горячего водоснабжения
                if shared_area.stove_type == 'electric':
                    has_electric_stove = 'оборудован в установленном порядке стационарными электроплитами для приготовления пищи'
                else:
                    has_electric_stove = 'не оборудован стационарными электроплитами для приготовления пищи'

                multi_entry.append({
                    HouseAdditionalInfoRoomsFields.ADDRESS: house.address,
                    HouseAdditionalInfoRoomsFields.AREA_NUMBER: shared_area.str_number,
                    HouseAdditionalInfoRoomsFields.ROOM_NUMBER: room.number,
                    HouseAdditionalInfoRoomsFields.PARAM: 'Наличие электрооборудования (перечислимый, множественный)',
                    HouseAdditionalInfoRoomsFields.VALUE: has_electric_stove,
                })

                if shared_area.has_boiler:
                    has_boiler = 'оборудован в установленном порядке электроотопительными, электронагревательными установками для целей горячего водоснабжения'
                else:
                    has_boiler = 'не оборудован электроотопительными, электронагревательными установками для целей горячего водоснабжения'

                multi_entry.append({
                    HouseAdditionalInfoRoomsFields.ADDRESS: house.address,
                    HouseAdditionalInfoRoomsFields.AREA_NUMBER: shared_area.str_number,
                    HouseAdditionalInfoRoomsFields.ROOM_NUMBER: room.number,
                    HouseAdditionalInfoRoomsFields.PARAM: 'Наличие электрооборудования (перечислимый, множественный)',
                    HouseAdditionalInfoRoomsFields.VALUE: has_boiler,
                })

        return multi_entry
