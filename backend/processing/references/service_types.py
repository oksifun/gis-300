import datetime

from app.meters.models.choices import MeterMeasurementUnits

SystemServiceTypesTree = [
    {
        'date_from': datetime.datetime(2000, 1, 1),
        'services': {
            # СОДЕРЖАНИЕ ОБЩЕГО ИМУЩЕСТВА
            'maintenance': {
                'title': 'Содержание общего имущества и тех.обслуживание',
                'parent_codes': [],
            },
            'fire_protection': {
                'title': 'Содержание и тех.обслуживание АППЗ',
                'parent_codes': ['maintenance'],
            },
            'gas_systems': {
                'title': 'Содержание и тех.обслуживание газовых систем',
                'parent_codes': ['maintenance'],
            },
            'elevator': {
                'title': 'Содержание и тех.обслуживание лифта',
                'parent_codes': ['maintenance'],
            },
            'chute': {
                'title': 'Содержание и тех.обслуживание мусоропровода',
                'parent_codes': ['maintenance'],
            },
            'intercom': {
                'title': 'Содержание и тех.обслуживание ПЗУ',
                'parent_codes': ['maintenance'],
            },
            'territory': {
                'title': 'Содержание придомовой территории',
                'parent_codes': ['maintenance'],
            },
            'housing': {
                'title': 'Содержание общего имущества',
                'parent_codes': ['maintenance'],
            },
            'repair': {
                'title': 'Текущий ремонт',
                'parent_codes': ['maintenance'],
            },
            'stairs_cleaning': {
                'title': 'Уборка лестничных клеток',
                'parent_codes': ['maintenance'],
            },
            'garbage_area': {
                'title': 'Содержание контейнерной площадки',
                'parent_codes': ['maintenance'],
            },
            'management': {
                'title': 'Управление многоквартирными домами',
                'parent_codes': ['maintenance'],
            },
            'house_meters': {
                'title': 'Содержание и тех.обслуживание ОДПУ',
                'parent_codes': ['maintenance'],
            },
            'house_meters_electricity': {
                'title': 'Содержание и тех.обслуживание ОДПУ электроэнергии',
                'parent_codes': ['house_meters'],
            },
            'house_meters_heat': {
                'title': 'Содержание и тех.обслуживание ОДПУ '
                         'тепла и горячей воды',
                'parent_codes': ['house_meters'],
            },
            'house_meters_water': {
                'title': 'Содержание и тех.обслуживание ОДПУ холодной воды',
                'parent_codes': ['house_meters'],
            },
            'house_meters_gas': {
                'title': 'Содержание и тех.обслуживание ОДПУ газа',
                'parent_codes': ['house_meters'],
            },

            # ГОРЯЧАЯ ВОДА
            'hot_water': {
                'title': 'Горячая вода',
                'parent_codes': [],
            },
            'hot_water_individual': {
                'title': 'Горячая вода (индивидуальное потребление)',
                'parent_codes': ['hot_water'],
                'resource': 'hot_water',
                'calculate_queue': 0,
            },
            'hot_water_individual_carrier': {
                'title': 'Горячая вода теплоноситель '
                         '(индивидуальное потребление)',
                'parent_codes': ['hot_water_individual'],
                'calculate_queue': 0,
            },
            'hot_water_public': {
                'title': 'Горячая вода (общедомовые нужды)',
                'parent_codes': ['hot_water'],
            },
            'hot_water_public_carrier': {
                'title': 'Горячая вода теплоноситель (общедомовые нужды)',
                'parent_codes': ['hot_water_public'],
            },

            'communal_services': {
                'title': 'Коммунальные услуги',
                'parent_codes': [],
            },

            # ТЕПЛОСНАБЖЕНИЕ
            'heat_supply': {
                'title': 'Теплоснабжение',
                'parent_codes': ['communal_services'],
            },
            'heat': {
                'title': 'Отопление',
                'parent_codes': ['heat_supply'],
                'calculate_queue': 2,
            },
            'heat_individual': {
                'title': 'Отопление (индивидуальное потребление)',
                'parent_codes': ['heat'],
                'resource': 'heat',
                'calculate_queue': 2,
                'okei': MeterMeasurementUnits.GIGAJOULE,
            },
            'heat_public': {
                'title': 'Отопление (общедомовые нужды)',
                'parent_codes': ['heat'],
                'okei': MeterMeasurementUnits.GIGAJOULE,
            },
            'heat_water': {
                'title': 'Подогрев воды для ГВС',
                'parent_codes': ['heat_supply'],
            },
            'heat_water_remains': {
                'title': 'Потери на ГВС (циркуляция)',
                'parent_codes': ['heat_water'],
                'okei': MeterMeasurementUnits.GIGAJOULE,
            },
            'heating_water_individual': {
                'title': 'Горячая вода тепловая энергия '
                         '(индивидуальное потребление)',
                'parent_codes': ['heat_water', 'hot_water_individual'],
                'calculate_queue': 1,
            },
            'heat_water_individual': {
                'title': 'Подогрев воды для ГВС (индивидуальное потребление)',
                'parent_codes': ['heating_water_individual'],
                'calculate_queue': 1,
                'okei': MeterMeasurementUnits.GIGAJOULE,
            },
            'heated_water_individual': {
                'title': 'Горячая вода подогретая (индивидуальное потребление)',
                'parent_codes': [
                    'heating_water_individual',
                    'hot_water_individual_carrier',
                ],
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'heating_water_public': {
                'title': 'Горячая вода тепловая энергия (общедомовые нужды)',
                'parent_codes': ['heat_water', 'hot_water_public'],
            },
            'heat_water_public': {
                'title': 'Подогрев воды для ГВС (общедомовые нужды)',
                'parent_codes': ['heating_water_public'],
                'okei': MeterMeasurementUnits.GIGAJOULE,
            },
            'heated_water_public': {
                'title': 'Горячая вода подогретая (общедомовые нужды)',
                'parent_codes': [
                    'heating_water_public',
                    'hot_water_public_carrier',
                ],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },

            # ВОДОСНАБЖЕНИЕ
            'water_cycle': {
                'title': 'Холодное водоснабжение и водоотведение',
                'parent_codes': ['communal_services'],
            },
            'waste_water': {
                'title': 'Водоотведение',
                'parent_codes': ['water_cycle'],
            },
            'waste_water_individual': {
                'title': 'Водоотведение (индивидуальное потребление)',
                'parent_codes': ['waste_water'],
                'head_codes': ['hot_water_individual', 'water_individual'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_hot_water_individual': {
                'title': 'Водоотведение горячей воды '
                         '(индивидуальное потребление)',
                'parent_codes': ['waste_water_individual'],
                'head_codes': ['hot_water_individual'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_cold_water_individual': {
                'title': 'Водоотведение холодной воды '
                         '(индивидуальное потребление)',
                'parent_codes': ['waste_water_individual'],
                'head_codes': ['water_individual'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_water_public': {
                'title': 'Водоотведение (общедомовые нужды)',
                'parent_codes': ['waste_water'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_cold_water_public': {
                'title': 'Водоотведение холодной воды (общедомовые нужды)',
                'parent_codes': ['waste_water_public'],
                'head_codes': ['water_public'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_hot_water_public': {
                'title': 'Водоотведение горячей воды (общедомовые нужды)',
                'parent_codes': ['waste_water_public'],
                'head_codes': ['hot_water_public'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'water_supply': {
                'title': 'Холодное водоснабжение',
                'parent_codes': ['water_cycle'],
            },
            'water_individual': {
                'title': 'Холодное водоснабжение (индивидуальное потребление)',
                'parent_codes': ['water_supply'],
                'resource': 'cold_water',
                'calculate_queue': 0,
            },
            'water_public': {
                'title': 'Холодное водоснабжение (общедомовые нужды)',
                'parent_codes': ['water_supply'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'water_for_hot_individual': {
                'title': 'Холодная вода для ГВС (индивидуальное потребление)',
                'parent_codes': [
                    'water_supply',
                    'hot_water_individual_carrier',
                ],
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'water_for_hot_public': {
                'title': 'Холодная вода для ГВС (общедомовые нужды)',
                'parent_codes': ['water_supply', 'hot_water_public_carrier'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },

            # ГАЗОСНАБЖЕНИЕ
            'gas_supply': {
                'title': 'Газоснабжение',
                'parent_codes': ['communal_services'],
            },
            'gas_individual': {
                'title': 'Газ (индивидуальное потребление)',
                'parent_codes': ['gas_supply'],
                'resource': 'gas',
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'gas_public': {
                'title': 'Газ (общедомовые нужды)',
                'parent_codes': ['gas_supply'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },

            # ЭЛЕКТРОСНАБЖЕНИЕ
            'electricity_supply': {
                'title': 'Электроснабжение',
                'parent_codes': ['communal_services'],
            },
            'electricity_individual': {
                'title': 'Электроэнергия (индивидуальное потребление)',
                'parent_codes': ['electricity_supply'],
            },
            'electricity_regular_individual': {
                'title': 'Электроэнергия однотар. (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_regular',
                'calculate_queue': 1,
                'head_codes': [
                    'electricity_day_individual',
                    'electricity_night_individual',
                    'electricity_peak_individual',
                    'electricity_semi_peak_individual'
                ],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_day_individual': {
                'title': 'Электроэнергия день (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_day',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_night_individual': {
                'title': 'Электроэнергия ночь (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_night',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_peak_individual': {
                'title': 'Электроэнергия пиковая (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_peak',
                'calculate_queue': 0,
            },
            'electricity_semi_peak_individual': {
                'title': 'Электроэнергия полупиковая '
                         '(индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_semi_peak',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_public': {
                'title': 'Электроэнергия (общедомовые нужды)',
                'parent_codes': ['electricity_supply'],
            },
            'electricity_regular_public': {
                'title': 'Электроэнергия однотар. (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_day_public': {
                'title': 'Электроэнергия день (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_night_public': {
                'title': 'Электроэнергия ночь (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_peak_public': {
                'title': 'Электроэнергия пиковая (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_semi_peak_public': {
                'title': 'Электроэнергия полупиковая (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },

            # ПРОЧИЕ УСЛУГИ
            'tv': {
                'title': 'Телевидение',
                'parent_codes': [],
                'okei': '661',  # канал
            },
            'radio': {
                'title': 'Радиоточка',
                'parent_codes': [],
                'okei': 'A030',  # точка присоединения
            },
            'administrative': {
                'title': 'Административно-хозяйственные расходы',
                'parent_codes': [],
            },
            'bank_fee': {
                'title': 'Комиссия банка',
                'parent_codes': [],
            },
            'penalty': {
                'title': 'Пени',
                'parent_codes': [],
            },
            'manual': {
                'title': 'Ручное начисление/Корректировки',
                'parent_codes': [],
            },
            'capital_repair': {
                'title': 'Взнос на капитальный ремонт',
                'parent_codes': [],
            },
            'pay_for_rent': {
                'title': 'Плата за пользование жилым помещением '
                         '(плата за наём)',
                'parent_codes': [],
            },
            'garbage': {
                'title': 'Вывоз мусора',
                'parent_codes': ['communal_services'],
                'okei': 'A023',  # Кубический метр на человека
            },
        }
    },
    {
        'date_from': datetime.datetime(2017, 1, 1),
        'services': {
            # СОДЕРЖАНИЕ ОБЩЕГО ИМУЩЕСТВА
            'maintenance': {
                'title': 'Содержание общего имущества и тех.обслуживание',
                'parent_codes': [],
            },
            'fire_protection': {
                'title': 'Содержание и тех.обслуживание АППЗ',
                'parent_codes': ['maintenance'],
            },
            'gas_systems': {
                'title': 'Содержание и тех.обслуживание газовых систем',
                'parent_codes': ['maintenance'],
            },
            'elevator': {
                'title': 'Содержание и тех.обслуживание лифта',
                'parent_codes': ['maintenance'],
            },
            'chute': {
                'title': 'Содержание и тех.обслуживание мусоропровода',
                'parent_codes': ['maintenance'],
            },
            'intercom': {
                'title': 'Содержание и тех.обслуживание ПЗУ',
                'parent_codes': ['maintenance'],
            },
            'territory': {
                'title': 'Содержание придомовой территории',
                'parent_codes': ['maintenance'],
            },
            'housing': {
                'title': 'Содержание общего имущества',
                'parent_codes': ['maintenance'],
            },
            'repair': {
                'title': 'Текущий ремонт',
                'parent_codes': ['maintenance'],
            },
            'stairs_cleaning': {
                'title': 'Уборка лестничных клеток',
                'parent_codes': ['maintenance'],
            },
            'garbage_area': {
                'title': 'Содержание контейнерной площадки',
                'parent_codes': ['maintenance'],
            },
            'management': {
                'title': 'Управление многоквартирными домами',
                'parent_codes': ['maintenance'],
            },
            'house_meters': {
                'title': 'Содержание и тех.обслуживание ОДПУ',
                'parent_codes': ['maintenance'],
            },
            'house_meters_electricity': {
                'title': 'Содержание и тех.обслуживание ОДПУ электроэнергии',
                'parent_codes': ['house_meters'],
            },
            'house_meters_heat': {
                'title': 'Содержание и тех.обслуживание ОДПУ '
                         'тепла и горячей воды',
                'parent_codes': ['house_meters'],
            },
            'house_meters_water': {
                'title': 'Содержание и тех.обслуживание ОДПУ холодной воды',
                'parent_codes': ['house_meters'],
            },
            'house_meters_gas': {
                'title': 'Содержание и тех.обслуживание ОДПУ газа',
                'parent_codes': ['house_meters'],
            },

            # ГОРЯЧАЯ ВОДА
            'hot_water': {
                'title': 'Горячая вода',
                'parent_codes': [],
            },
            'hot_water_individual': {
                'title': 'Горячая вода (индивидуальное потребление)',
                'parent_codes': ['hot_water'],
                'resource': 'hot_water',
                'calculate_queue': 0,
            },
            'hot_water_individual_carrier': {
                'title': 'Горячая вода теплоноситель '
                         '(индивидуальное потребление)',
                'parent_codes': ['hot_water_individual'],
                'calculate_queue': 0,
            },
            'hot_water_public': {
                'title': 'Горячая вода (общедомовые нужды)',
                'parent_codes': ['hot_water'],
            },
            'hot_water_public_carrier': {
                'title': 'Горячая вода теплоноситель (общедомовые нужды)',
                'parent_codes': ['hot_water_public'],
            },

            'communal_services': {
                'title': 'Коммунальные услуги',
                'parent_codes': [],
            },

            # ТЕПЛОСНАБЖЕНИЕ
            'heat_supply': {
                'title': 'Теплоснабжение',
                'parent_codes': ['communal_services'],
            },
            'heat': {
                'title': 'Отопление',
                'parent_codes': ['heat_supply'],
                'calculate_queue': 2,
            },
            'heat_individual': {
                'title': 'Отопление (индивидуальное потребление)',
                'parent_codes': ['heat'],
                'resource': 'heat',
                'calculate_queue': 2,
                'okei': MeterMeasurementUnits.GIGACALORIE,
            },
            'heat_public': {
                'title': 'Отопление (общедомовые нужды)',
                'parent_codes': ['heat'],
                'okei': MeterMeasurementUnits.GIGACALORIE,
            },
            'heat_water': {
                'title': 'Подогрев воды для ГВС',
                'parent_codes': ['heat_supply'],
            },
            'heating_water_individual': {
                'title': 'Горячая вода тепловая энергия '
                         '(индивидуальное потребление)',
                'parent_codes': ['heat_water', 'hot_water_individual'],
                'calculate_queue': 1,
            },
            'heat_water_individual': {
                'title': 'Подогрев воды для ГВС (индивидуальное потребление)',
                'parent_codes': ['heating_water_individual'],
                'calculate_queue': 1,
                'okei': MeterMeasurementUnits.GIGACALORIE,
            },
            'heated_water_individual': {
                'title': 'Горячая вода подогретая (индивидуальное потребление)',
                'parent_codes': ['heating_water_individual',
                                 'hot_water_individual_carrier'],
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'heating_water_public': {
                'title': 'Горячая вода тепловая энергия (общедомовые нужды)',
                'parent_codes': ['heat_water', 'hot_water_public'],
            },
            'heat_water_public': {
                'title': 'Подогрев воды для ГВС (общедомовые нужды)',
                'parent_codes': ['heating_water_public'],
                'okei': MeterMeasurementUnits.GIGACALORIE,
            },
            'heated_water_public': {
                'title': 'Горячая вода подогретая (общедомовые нужды)',
                'parent_codes': [
                    'heating_water_public',
                    'hot_water_public_carrier',
                ],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },

            # ВОДОСНАБЖЕНИЕ
            'water_cycle': {
                'title': 'Холодное водоснабжение и водоотведение',
                'parent_codes': ['communal_services'],
            },
            'waste_water': {
                'title': 'Водоотведение',
                'parent_codes': ['water_cycle'],
            },
            'waste_water_individual': {
                'title': 'Водоотведение (индивидуальное потребление)',
                'parent_codes': ['waste_water'],
                'head_codes': ['hot_water_individual', 'water_individual'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_hot_water_individual': {
                'title': 'Водоотведение горячей воды '
                         '(индивидуальное потребление)',
                'parent_codes': ['waste_water_individual'],
                'head_codes': ['hot_water_individual'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_cold_water_individual': {
                'title': 'Водоотведение холодной воды '
                         '(индивидуальное потребление)',
                'parent_codes': ['waste_water_individual'],
                'head_codes': ['water_individual'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_water_public': {
                'title': 'Водоотведение (общедомовые нужды)',
                'parent_codes': ['waste_water'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_cold_water_public': {
                'title': 'Водоотведение холодной воды (общедомовые нужды)',
                'parent_codes': ['waste_water_public'],
                'head_codes': ['water_public'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'waste_hot_water_public': {
                'title': 'Водоотведение горячей воды (общедомовые нужды)',
                'parent_codes': ['waste_water_public'],
                'head_codes': ['hot_water_public'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'water_supply': {
                'title': 'Холодное водоснабжение',
                'parent_codes': ['water_cycle'],
            },
            'water_individual': {
                'title': 'Холодное водоснабжение (индивидуальное потребление)',
                'parent_codes': ['water_supply'],
                'resource': 'cold_water',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'water_public': {
                'title': 'Холодное водоснабжение (общедомовые нужды)',
                'parent_codes': ['water_supply'],
            },
            'water_for_hot_individual': {
                'title': 'Холодная вода для ГВС (индивидуальное потребление)',
                'parent_codes': ['water_supply',
                                 'hot_water_individual_carrier'],
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'water_for_hot_public': {
                'title': 'Холодная вода для ГВС (общедомовые нужды)',
                'parent_codes': [
                    'water_supply',
                    'hot_water_public_carrier',
                ],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },

            # ГАЗОСНАБЖЕНИЕ
            'gas_supply': {
                'title': 'Газоснабжение',
                'parent_codes': ['communal_services'],
            },
            'gas_individual': {
                'title': 'Газ (индивидуальное потребление)',
                'parent_codes': ['gas_supply'],
                'resource': 'gas',
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },
            'gas_public': {
                'title': 'Газ (общедомовые нужды)',
                'parent_codes': ['gas_supply'],
                'okei': MeterMeasurementUnits.CUBIC_METER,
            },

            # ЭЛЕКТРОСНАБЖЕНИЕ
            'electricity_supply': {
                'title': 'Электроснабжение',
                'parent_codes': ['communal_services'],
            },
            'electricity_individual': {
                'title': 'Электроэнергия (индивидуальное потребление)',
                'parent_codes': ['electricity_supply'],
            },
            'electricity_regular_individual': {
                'title': 'Электроэнергия однотар. (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_regular',
                'calculate_queue': 1,
                'head_codes': [
                    'electricity_day_individual',
                    'electricity_night_individual',
                    'electricity_peak_individual',
                    'electricity_semi_peak_individual'
                ],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_day_individual': {
                'title': 'Электроэнергия день (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_day',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_night_individual': {
                'title': 'Электроэнергия ночь (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_night',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_peak_individual': {
                'title': 'Электроэнергия пиковая (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_peak',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_semi_peak_individual': {
                'title': 'Электроэнергия полупиковая '
                         '(индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_semi_peak',
                'calculate_queue': 0,
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_public': {
                'title': 'Электроэнергия (общедомовые нужды)',
                'parent_codes': ['electricity_supply'],
            },
            'electricity_regular_public': {
                'title': 'Электроэнергия однотар. (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_day_public': {
                'title': 'Электроэнергия день (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_night_public': {
                'title': 'Электроэнергия ночь (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_peak_public': {
                'title': 'Электроэнергия пиковая (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },
            'electricity_semi_peak_public': {
                'title': 'Электроэнергия полупиковая (общедомовые нужды)',
                'parent_codes': ['electricity_public'],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            },

            # ПРОЧИЕ УСЛУГИ
            'tv': {
                'title': 'Телевидение',
                'parent_codes': [],
                'okei': '661',  # канал
            },
            'radio': {
                'title': 'Радиоточка',
                'parent_codes': [],
                'okei': 'A030',  # точка присоединения
            },
            'administrative': {
                'title': 'Административно-хозяйственные расходы',
                'parent_codes': [],
            },
            'bank_fee': {
                'title': 'Комиссия банка',
                'parent_codes': [],
            },
            'penalty': {
                'title': 'Пени',
                'parent_codes': [],
            },
            'manual': {
                'title': 'Ручное начисление/Корректировки',
                'parent_codes': [],
            },
            'capital_repair': {
                'title': 'Взнос на капитальный ремонт',
                'parent_codes': [],
            },
            'pay_for_rent': {
                'title': 'Плата за пользование жилым помещением '
                         '(плата за наём)',
                'parent_codes': [],
            },
            'garbage': {
                'title': 'Вывоз мусора',
                'parent_codes': ['communal_services'],
            },
        }
    }
]
