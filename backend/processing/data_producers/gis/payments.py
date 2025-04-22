from bson import ObjectId
from dateutil.relativedelta import relativedelta

from processing.data_producers.balance.base import AccountBalance
from processing.models.billing.provider.main import Provider
from processing.models.billing.account import Tenant
from processing.models.billing.service_type import ServiceType, \
    ServiceTypeGisBind, ServiceTypeGisName
from processing.models.billing.settings import Settings
from processing.models.choices import ConsumptionType
from processing.models.logging.gis_log import GisImportStatus

from .base import BaseGISDataProducer
from ...models.billing.payment import Payment

NOT_FILL_FIELDS = [
    'плата за содержание жилого помещения',
    'страхование',
    'взнос на капитальный ремонт (для дпд)',
    'плата за пользование жилым помещением (плата за наем)',
    'содержание помещения'
]

CAPITAL_REPAIR = ObjectId("526234c0e0e34c4743822325")


class PD_Section_1_2:
    HCS_UID = 'Идентификатор ЖКУ'
    DOC_TYPE = 'Тип ПД'
    DOC_NUMBER = 'Номер платежного документа'
    PERIOD = 'Расчетный период (ММ.ГГГГ)'

    # Раздел 1. Сведения о плательщике. Раздел 2. Информация для внесения
    # платы получателю платежа (получателям платежей).
    AREA_SUMMARY = 'Общая площадь для ЛС'
    AREA_LIVING = 'Жилая площадь'
    AREA_HEATED = 'Отапливаемая площадь'
    RESIDENTS_NUMBER = 'Количество проживающих'
    DEBT_PREVIOUS = 'Задолженность за предыдущие периоды'
    PREPAYMENT = 'Аванс на начало расчетного периода'
    PAYMENTS = 'Учтены платежи, поступившие до указанного числа расчетного ' \
               'периода включительно'
    TO_PAY_TOTAL = (
        'Сумма к оплате за расчетный период, руб. '
        '(по всему платежному документу)'
    )
    TO_PAY_TOTAL_DEBT = 'Итого к оплате за расчетный период c учетом ' \
                        'задолженности/переплаты, руб. ' \
                        '(по всему платежному документу)'
    BANK_BIC = 'БИК банка'
    BANK_ACCOUNT = 'Расчетный счет'

    # Взнос на капитальный ремонт
    CAPITAL_REPAIR_TARIFF = 'Размер взноса на кв.м, руб.'
    CAPITAL_REPAIR_ACCRUED_TOTAL = 'Всего начислено за расчетный период, руб.'
    CAPITAL_REPAIR_RECALCULATION = 'Перерасчеты всего, руб.'
    CAPITAL_REPAIR_PLIVILEGES = 'Льготы, субсидии, руб.'
    CAPITAL_REPAIR_CALCULATION_METHOD = 'Порядок расчетов'
    CAPITAL_REPAIR_TO_PAY_TOTAL = 'Итого к оплате за расчетный период, руб.'

    #
    TO_PAY_TOTAL_SERVICES = 'Итого к оплате за расчетный период по услугам, ' \
                            'руб. (по всем услугам за расчетный период)'
    TO_PAY_TOTAL_CREDIT = 'Сумма к оплате с учетом рассрочки платежа и ' \
                          'процентов за рассрочку, руб. ' \
                          '(Итого по всему платежному документу)'
    TO_PAY_TOTAL_LAW = 'Итого к оплате по неустойкам и судебным издержкам'

    ADDITIONAL_INFO = 'Дополнительная информация'
    PAYMENT_ID_BY_GIS = 'Идентификатор платежного документа'
    TO_PAY_TOTAL_BY_GIS = '(РАССЧИТАНО ГИС ЖКХ)  ' \
                          'Итого к оплате за расчетный период'
    GIS_PROCESSING_STATUS = 'Статус обработки'
    # Новые
    PAID = 'Оплачено денежных средств, руб.'
    DATE_OF_LAST_PAY = 'Дата последней поступившей оплаты'
    SUBSIDIES = 'Субсидии, компенсации и иные меры соц. поддержки граждан, руб.'
    OGRN_PROVIDER = 'Поставщик услуги ОГРН'
    KPP_PROVIDER = 'Поставщик услуги КПП'
    REQUISITES = 'Номер платежного реквизита'
    INFO = (
        'Предельный (максимальный) индекс изменения размера платы '
        'граждан за коммунальные услуги в муниципальном образовании, %'
    )
    OGRN_EXECUTOR = 'Исполнитель услуги ОГРН'
    KPP_EXECUTOR = 'Исполнитель услуги КПП'

    ACCRUAL_PERIOD = 'Период начисления'
    TO_PAY_TOTAL_BY_REQUISITES = (
        'Сумма к оплате за расчетный период (руб) в рамках платежного реквизита'
    )
    # Новые от 19-09-2019
    # Раздел 5. Сведения о перерасчетах (доначисления +, уменьшения -)
    RECALCULATION_REASON = "Основания перерасчетов"
    RECALCULATION_SUM = "Сумма, руб."


class PD_Section_3_6:
    DOC_NUMBER = 'Номер платежного документа'
    SERVICE = 'Услуга'

    # Раздел 3. Расчет размера платы за содержание и ремонт жилого помещения и коммунальные услуги
    SERVICES_INDIVIDUAL_METHOD = 'Объем услуг - индивидуальное потребление - ' \
                                 'Способ определения объемов КУ'
    SERVICES_INDIVIDUAL_VOLUMES = 'Объем услуг - индивидуальное потребление' \
                                  ' - Объем, площадь, количество'
    SERVICES_COLLECTIVE_METHOD = 'Объем услуг - общедомовые нужды - Способ ' \
                                 'определения объемов КУ'
    SERVICES_COLLECTIVE_VOLUMES = 'Объем услуг - общедомовые нужды - Объем, ' \
                                  'площадь, количество'
    TARIFF = 'Тариф руб./еди-ница измерения Размер платы на кв. м, руб.'

    SERVICES_INDIVIDUAL_VALUES = 'Размер платы за коммунальные услуги, руб.' \
                                 ' - индивидуальное потребление'
    SERVICES_COLLECTIVE_VALUES = 'Размер платы за коммунальные услуги, руб.' \
                                 ' - потребление при содержании общего ' \
                                 'имущества'

    TOTAL_CALCULATED = 'Всего на-числено за расчетный период, руб.'
    INCREMENT_COEFFICIENT = 'Размер повышающего коэффициента'
    INCREMENT_VALUE = 'Размер превышения платы, рассчитанной с применением ' \
                      'повышающего коэффициента над размером платы, ' \
                      'рассчитанной без учета повышающего коэффициента'
    RECALCULATION = 'Перерасчеты всего, руб.'
    PRIVILEGES = 'Льготы, субсидии, руб.'
    CALCULATION_COMMENT = 'Порядок расчетов'

    # Раздел 4. Справочная информация
    NORM_INDIVIDUAL = 'Норматив потребления коммунальных ресурсов - в ' \
                      'жилых помеще-ниях'
    NORM_COLLECTIVE = 'Норматив потребления коммунальных ресурсов - на ' \
                      'потребление при содержании общего имущества'
    CURRENT_READINGS_INDIVIDUAL = 'Текущие показания приборов учета ' \
                                  'коммунальных ресурсов - индиви-дуальных ' \
                                  '(квартир-ных)'
    CURRENT_READINGS_COLLECTIVE = 'Текущие показания приборов учета ' \
                                  'коммунальных ресурсов - коллек-тивных ' \
                                  '(общедо-мовых)'
    TOTAL_VOLUME_INDIVIDUAL = 'Суммарный объем коммунальных ресурсов в доме' \
                              ' - в помеще-ниях дома'
    TOTAL_VOLUME_COLLECTIVE = 'Суммарный объем коммунальных ресурсов в доме' \
                              ' - в целях содержания общего имущества'

    # Раздел 5. Сведения о перерасчетах
    RECALCULATIONS_REASON = 'Основания перерасчетов'
    RECALCULATIONS_TOTAL = 'Сумма, руб.'

    # Раздел 6. Расчет суммы к оплате с учетом рассрочки платежа
    DEFERRED_PAY_CURRENT_PERIOD = 'Сумма платы с учетом рассрочки платежа - ' \
                                  'от платы за расчетный период'
    DEFERRED_PAY_CURRENT_PERIOD_PREVIOUS_PERIODS = \
        'Сумма платы с учетом рассрочки платежа - от платы за предыдущие ' \
        'расчетные периоды'
    DEFERRED_PAY_PCT_RUB = 'Проценты за рассрочку - руб.'
    DEFERRED_PAY_PCT_PCT = 'Проценты за рассрочку - %'
    TO_PAY_WITH_DEFERRED = 'Сумма к оплате с учетом рассрочки платежа и ' \
                           'процентов за рассрочку, руб.'

    # Итого к оплате за расчетный период, руб.
    TO_PAY_TOTAL = 'Итого к оплате за расчетный период, руб. - Всего'
    TO_PAY_INDIVIDUAL = 'Итого к оплате за расчетный период, руб. - в т. ч. ' \
                        'за ком. усл. - индивид. потребление'
    TO_PAY_COLLECTIVE = 'Итого к оплате за расчетный период, руб. - в т. ч. ' \
                        'за ком. усл. - потребление при содержании общего ' \
                        'имущества'

    #
    ACCRUED_BY_GIS_TOTAL = '(РАССЧИТАНО ГИС ЖКХ) Всего начислено за ' \
                           'расчетный период (без перерасчетов и льгот), руб.'
    TO_PAY_BY_GIS_TOTAL = '(РАССЧИТАНО ГИС ЖКХ) Итого к оплате за расчетный ' \
                          'период, руб. - Всего'

    PROCESSING_STATUS = 'Статус обработки'
    UNIT = 'Единциа измерения'
    OGRN_PROVIDER = 'Поставщик услуги ОГРН'
    KPP_PROVIDER = 'Поставщик услуги КПП'
    REQUISITES = 'Номер платежного реквизита'


class PaymentsDPDFields:
    DOC_NUMBER = 'Номер платежного документа'
    SERVICE = 'Услуга'
    PERIOD = 'Период, ММ.ГГГГ'
    TO_PAY_TOTAL = 'Итого к оплате за период, руб.'

    PROCESSING_STAUS = 'Статус обработки'


class PaymentsCourtFields:
    DOC_NUMBER = 'Номер платежного документа'
    TYPE = 'Вид начисления'
    BASIS = 'Основания начислений'
    VALUE = 'Сумма, руб.'

    OGRN_PROVIDER = 'Поставщик услуги ОГРН'
    KPP_PROVIDER = 'Поставщик услуги КПП'
    REQUISITES = 'Номер платежного реквизита'

    PROCESSING_STATUS = 'Статус обработки'


class PaymentsServicesFields:
    REFERENCE_NAME = 'Наименование справочника'
    REFERENCE_NUMBER = 'Реестровый номер справочника'
    POSITION_NAME = 'Наименование позиции справочника'
    POSITION_NUMBER = 'Реестровый номер позиции'


class PaymentsDataProducer(BaseGISDataProducer):
    XLSX_TEMPLATE = 'templates/gis/payments.xlsx'
    XLSX_WORKSHEETS = {
        'Разделы 1-2': {
            'entry_produce_method': 'get_payments_sections_1',
            'title': 'Разделы 1-2',
            'start_row': 4,
            'columns': {
                PD_Section_1_2.HCS_UID: 'A',
                PD_Section_1_2.DOC_TYPE: 'B',
                PD_Section_1_2.DOC_NUMBER: 'C',
                PD_Section_1_2.PERIOD: 'D',

                PD_Section_1_2.AREA_SUMMARY: 'E',
                PD_Section_1_2.AREA_LIVING: 'F',
                PD_Section_1_2.AREA_HEATED: 'G',
                PD_Section_1_2.RESIDENTS_NUMBER: 'H',
                PD_Section_1_2.TO_PAY_TOTAL: 'I',
                PD_Section_1_2.DEBT_PREVIOUS: 'J',
                PD_Section_1_2.PREPAYMENT: 'K',
                PD_Section_1_2.PAID: 'L',
                PD_Section_1_2.PAYMENTS: 'M',
                PD_Section_1_2.DATE_OF_LAST_PAY: 'N',
                PD_Section_1_2.SUBSIDIES: 'O',
                PD_Section_1_2.TO_PAY_TOTAL_DEBT: 'P',
                PD_Section_1_2.BANK_BIC: 'Q',
                PD_Section_1_2.BANK_ACCOUNT: 'R',
                PD_Section_1_2.CAPITAL_REPAIR_TARIFF: 'S',
                PD_Section_1_2.CAPITAL_REPAIR_ACCRUED_TOTAL: 'T',
                PD_Section_1_2.CAPITAL_REPAIR_RECALCULATION: 'U',
                PD_Section_1_2.CAPITAL_REPAIR_PLIVILEGES: 'V',
                PD_Section_1_2.CAPITAL_REPAIR_CALCULATION_METHOD: 'W',
                PD_Section_1_2.RECALCULATION_REASON: "X",
                PD_Section_1_2.RECALCULATION_SUM: "Y",
                PD_Section_1_2.CAPITAL_REPAIR_TO_PAY_TOTAL: 'Z',
                PD_Section_1_2.OGRN_PROVIDER: 'AA',
                PD_Section_1_2.KPP_PROVIDER: 'AB',
                PD_Section_1_2.REQUISITES: 'AC',
                PD_Section_1_2.TO_PAY_TOTAL_SERVICES: 'AD',
                PD_Section_1_2.TO_PAY_TOTAL_CREDIT: 'AE',
                PD_Section_1_2.TO_PAY_TOTAL_LAW: 'AF',
                PD_Section_1_2.ADDITIONAL_INFO: 'AG',
                PD_Section_1_2.INFO: 'AH',
                PD_Section_1_2.OGRN_EXECUTOR: 'AI',
                PD_Section_1_2.KPP_EXECUTOR: 'AJ',
                PD_Section_1_2.PAYMENT_ID_BY_GIS: 'AK',
                PD_Section_1_2.TO_PAY_TOTAL_BY_GIS: 'AL',
                PD_Section_1_2.GIS_PROCESSING_STATUS: 'AM',
            }
        },
        'Разделы 3-6': {
            'entry_produce_method': 'get_payments_sections_3_6',
            'title': 'Разделы 3-6',
            'start_row': 5,
            'columns': {
                PD_Section_3_6.DOC_NUMBER: 'A',
                PD_Section_3_6.SERVICE: 'B',

                # Раздел 3. Расчет размера платы за содержание и ремонт жилого
                # помещения и коммунальные услуги
                PD_Section_3_6.UNIT: 'C',

                PD_Section_3_6.SERVICES_INDIVIDUAL_METHOD: 'D',
                PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES: 'E',
                PD_Section_3_6.SERVICES_COLLECTIVE_METHOD: 'F',
                PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES: 'G',
                PD_Section_3_6.TARIFF: 'H',
                PD_Section_3_6.SERVICES_INDIVIDUAL_VALUES: 'I',
                PD_Section_3_6.SERVICES_COLLECTIVE_VALUES: 'J',

                PD_Section_3_6.TOTAL_CALCULATED: 'K',
                PD_Section_3_6.INCREMENT_COEFFICIENT: 'L',
                PD_Section_3_6.INCREMENT_VALUE: 'M',
                PD_Section_3_6.RECALCULATION: 'N',
                PD_Section_3_6.PRIVILEGES: 'O',
                PD_Section_3_6.CALCULATION_COMMENT: 'P',

                # Раздел 4. Справочная информация
                PD_Section_3_6.NORM_INDIVIDUAL: 'Q',
                PD_Section_3_6.NORM_COLLECTIVE: 'R',
                PD_Section_3_6.CURRENT_READINGS_INDIVIDUAL: 'S',
                PD_Section_3_6.CURRENT_READINGS_COLLECTIVE: 'T',
                PD_Section_3_6.TOTAL_VOLUME_INDIVIDUAL: 'U',
                PD_Section_3_6.TOTAL_VOLUME_COLLECTIVE: 'V',

                # Раздел 5. Сведения о перерасчетах
                PD_Section_3_6.RECALCULATIONS_REASON: 'W',
                PD_Section_3_6.RECALCULATIONS_TOTAL: 'X',

                # Раздел 6. Расчет суммы к оплате с учетом рассрочки платежа
                PD_Section_3_6.DEFERRED_PAY_CURRENT_PERIOD: 'Y',
                PD_Section_3_6.DEFERRED_PAY_CURRENT_PERIOD_PREVIOUS_PERIODS: 'Z',
                PD_Section_3_6.DEFERRED_PAY_PCT_RUB: 'AA',
                PD_Section_3_6.DEFERRED_PAY_PCT_PCT: 'AB',
                PD_Section_3_6.TO_PAY_WITH_DEFERRED: 'AC',

                # Итого к оплате за расчетный период, руб.
                PD_Section_3_6.TO_PAY_TOTAL: 'AD',
                PD_Section_3_6.TO_PAY_INDIVIDUAL: 'AE',
                PD_Section_3_6.TO_PAY_COLLECTIVE: 'AF',

                PD_Section_3_6.OGRN_PROVIDER: 'AG',
                PD_Section_3_6.KPP_PROVIDER: 'AH',
                PD_Section_3_6.REQUISITES: 'AI',
                PD_Section_3_6.PROCESSING_STATUS: 'AJ',

            }
        },
        'ДПД': {
            'entry_produce_method': 'get_payments_dpd',
            'title': 'ДПД',
            'start_row': 2,
            'columns': {
                PaymentsDPDFields.DOC_NUMBER: 'A',
                PaymentsDPDFields.SERVICE: 'B',
                PaymentsDPDFields.PERIOD: 'C',
                PaymentsDPDFields.TO_PAY_TOTAL: 'D',

                PaymentsCourtFields.OGRN_PROVIDER: 'E',
                PaymentsCourtFields.KPP_PROVIDER: 'F',
                PaymentsCourtFields.REQUISITES: 'G',

                PaymentsCourtFields.PROCESSING_STATUS: 'H',
            }
        },
        'Неустойки и судебные расходы': {
            'entry_produce_method': 'get_payments_court',
            'title': 'Неустойки и судебные расходы',
            'start_row': 3,
            'columns': {
                PaymentsCourtFields.DOC_NUMBER: 'A',
                PaymentsCourtFields.TYPE: 'B',
                PaymentsCourtFields.BASIS: 'C',
                PaymentsCourtFields.VALUE: 'D',

                PaymentsCourtFields.OGRN_PROVIDER: 'E',
                PaymentsCourtFields.KPP_PROVIDER: 'F',
                PaymentsCourtFields.REQUISITES: 'G',

                PaymentsCourtFields.PROCESSING_STATUS: 'H',
            }
        },
        'Услуги исполнителя': {
            'entry_produce_method': 'get_payments_section_services',
            'title': 'Услуги исполнителя',
            'start_row': 2,
            'static_page': True,
            'columns': {
                PaymentsServicesFields.REFERENCE_NAME: 'A',
                PaymentsServicesFields.REFERENCE_NUMBER: 'B',
                PaymentsServicesFields.POSITION_NAME: 'C',
                PaymentsServicesFields.POSITION_NUMBER: 'D',
            }
        },
        'Капитальный ремонт': {
            'entry_produce_method': 'get_capital_repair_data',
            'title': 'Капитальный ремонт',
            'start_row': 2,
            'static_page': True,
            'columns': {
                PD_Section_1_2.DOC_NUMBER: 'A',
                PD_Section_1_2.CAPITAL_REPAIR_TARIFF: 'B',
                PD_Section_1_2.CAPITAL_REPAIR_ACCRUED_TOTAL: 'C',
                PD_Section_1_2.CAPITAL_REPAIR_RECALCULATION: 'D',
                PD_Section_1_2.CAPITAL_REPAIR_PLIVILEGES: 'E',
                PD_Section_1_2.CAPITAL_REPAIR_CALCULATION_METHOD: 'F',
                PD_Section_1_2.CAPITAL_REPAIR_TO_PAY_TOTAL: 'G',
                PD_Section_1_2.OGRN_PROVIDER: 'H',
                PD_Section_1_2.KPP_PROVIDER: 'I',
                PD_Section_1_2.ACCRUAL_PERIOD: 'J',
                PD_Section_1_2.REQUISITES: 'K',
                PD_Section_1_2.GIS_PROCESSING_STATUS: 'L',
            }
        },
        'Платежные реквизиты': {
            'entry_produce_method': 'get_requisites_data',
            'title': 'Платежные реквизиты',
            'start_row': 2,
            'static_page': True,
            'columns': {
                PD_Section_1_2.DOC_NUMBER: 'A',
                PD_Section_1_2.REQUISITES: 'B',
                PD_Section_1_2.BANK_BIC: 'C',
                PD_Section_1_2.BANK_ACCOUNT: 'D',
                PD_Section_1_2.TO_PAY_TOTAL_BY_REQUISITES: 'E',
                PD_Section_1_2.GIS_PROCESSING_STATUS: 'F',
            }
        },
    }

    def __init__(self, entries):
        super().__init__(entries)
        self.service_types_children = None
        self.service_types_binds = None
        self.cached_provider = None

    def get_payments_sections_1(self, entry_source, export_task):
        multi_entry = []

        capital_repair_service_id: ObjectId = \
            ServiceType.objects.get(code='capital_repair').id

        owners: dict = {}
        for accrual in entry_source['accruals']:
            period = accrual.month

            account: Tenant = Tenant.objects(__raw__={
                '_id': accrual.account.id
            }).only('area', 'hcs_uid').first()
            assert account, \
                f"Не найден ЛС для документа начислений {accrual.id}"

            house = account.area.house

            if accrual.owner in owners:
                provider: Provider = owners[accrual.owner]
            else:
                provider: Provider = Provider.objects(__raw__={
                    '_id': accrual.owner
                }).only('str_name', 'bank_accounts').first()
                assert provider, \
                    f"Не найден провайдер документа начислений {accrual.id}"
                owners[accrual.owner] = provider

            provider_house_settings = Settings.objects(
                house=house.id, provider=provider.id
            ).only('sectors').first()
            assert provider_house_settings, "Не найдены параметры" \
                f" организации {provider.str_name}" \
                f" для дома {house.address}"

            accrual_sector_settings: list = [sector_settings
                for sector_settings in provider_house_settings.sectors
                if sector_settings.sector_code == accrual.sector_code]
            assert len(accrual_sector_settings) == 1, "Не определены" \
                f" параметры организации {provider.str_name} для дома" \
                f" {house.address} по направлению {accrual.sector_code}"
            accrual_settings = accrual_sector_settings[0]
            provider_bank_accounts: list = \
                [bank_account for bank_account in provider.bank_accounts
                    if bank_account.number == accrual_settings.bank_account]
            assert accrual_settings.bank_account, \
                f"Не найден банковский счет в настройках дома {house.address}"
            assert len(provider_bank_accounts) == 1, \
                f"Не найден банковский счет {accrual_settings.bank_account}" \
                f" организации {provider.str_name} по адресу {house.address} "
            provider_bank_account = provider_bank_accounts[0]

            balance = AccountBalance(account.id, provider.id)
            date_balance = round(
                balance.get_date_balance(
                    accrual.doc.date, [accrual.sector_code], use_bank_date=False
                ) / 100,
                2
            )
            # month_balance = \
            #     balance.get_date_balance(period, [accrual.sector_code]) / 100

            payment = Payment.objects(__raw__={
                'doc.date': {
                    '$gte': period,
                    '$lt': period + relativedelta(months=1),
                },
                'is_deleted': {'$ne': True},
                'account._id':  account.id
            }).as_pymongo().only('value', 'date').first()

            payment_value = payment.get('value', 0) if payment else 0
            payment_date = payment['date'].strftime("%d.%m.%Y") if payment_value else ''

            if accrual.sector_code == 'capital_repair':
                cr_services: list = [service for service in accrual.services
                    if service.service_type == capital_repair_service_id]
                if not cr_services:
                    GisImportStatus(
                        task=export_task.parent.id,
                        is_error=True, status='предупреждение',
                        description=f"Нет начислений за КР в {accrual.id}",
                    ).save()
                    continue  # пропускаем ПД, не завершаем формирование!

                cr_service = cr_services[0]  # первый (и единственный?)

                cr_tariff = cr_service.tariff
                cr_value = cr_service.value / 100
                cr_recalculations = cr_service.totals.recalculations / 100
                cr_privileges = cr_service.totals.privileges / 100
                cr_to_pay_total = cr_value - cr_recalculations - cr_privileges

                total_value = ''
                total_value_debt = ''
                total_no_penalty = ''

            else:
                cr_tariff = ''
                cr_value = ''
                cr_recalculations = ''
                cr_privileges = ''
                cr_to_pay_total = ''

                total_value = round(accrual.value / 100, 2)
                total_value_debt = round(
                    max(0, total_value + date_balance),
                    2
                )
                total_no_penalty = round(
                    total_value - accrual.totals.penalties / 100,
                    2
                )

            entry = {
                PD_Section_1_2.HCS_UID: account.hcs_uid,
                PD_Section_1_2.DOC_TYPE: 'Текущий',  # TODO choices
                PD_Section_1_2.DOC_NUMBER: str(accrual.id),
                PD_Section_1_2.PERIOD: period.strftime("%m.%Y"),

                PD_Section_1_2.AREA_SUMMARY: '@',
                PD_Section_1_2.AREA_LIVING: '@',
                PD_Section_1_2.AREA_HEATED: '@',
                PD_Section_1_2.RESIDENTS_NUMBER: '@',
                PD_Section_1_2.PAID: payment_value / 100,
                PD_Section_1_2.DATE_OF_LAST_PAY: payment_date,
                PD_Section_1_2.DEBT_PREVIOUS: (
                    date_balance if date_balance > 0 else 0
                ),
                PD_Section_1_2.PREPAYMENT: (
                    -date_balance if date_balance < 0 else 0
                ),

                PD_Section_1_2.TO_PAY_TOTAL: total_value,
                PD_Section_1_2.TO_PAY_TOTAL_DEBT: total_value_debt,

                PD_Section_1_2.BANK_BIC: provider_bank_account.bic.bic_body[0].BIC,
                PD_Section_1_2.BANK_ACCOUNT: provider_bank_account.number,

                PD_Section_1_2.CAPITAL_REPAIR_TARIFF: cr_tariff,
                PD_Section_1_2.CAPITAL_REPAIR_ACCRUED_TOTAL: cr_value,
                PD_Section_1_2.CAPITAL_REPAIR_RECALCULATION: cr_recalculations,
                PD_Section_1_2.RECALCULATION_SUM: cr_recalculations,
                PD_Section_1_2.CAPITAL_REPAIR_PLIVILEGES: cr_privileges,
                PD_Section_1_2.CAPITAL_REPAIR_CALCULATION_METHOD: '',  # TODO
                PD_Section_1_2.CAPITAL_REPAIR_TO_PAY_TOTAL: cr_to_pay_total,

                PD_Section_1_2.TO_PAY_TOTAL_SERVICES: total_no_penalty,
                PD_Section_1_2.TO_PAY_TOTAL_CREDIT: total_value,

            }
            multi_entry.append(entry)

        return multi_entry

    def get_service_types_children(self, provider_id):
        if not self.service_types_children or self.cached_provider != provider_id:
            self.service_types_children = ServiceType.get_provider_tree(
                provider_id
            )
            self.cached_provider = provider_id
        return self.service_types_children

    def _get_services_ids(self, provider_id, codes):
        all_services = self.get_service_types_children(provider_id)
        result = []
        for code in codes:
            result.extend(all_services[code])
        return result

    def get_individual_services_ids(self, provider_id):
        return self._get_services_ids(
            provider_id,
            ('heat_individual', 'heating_water_individual', 'water_individual',
             'waste_water_individual', 'gas_individual',
             'electricity_individual')
        )

    def get_public_services_ids(self, provider_id):
        return self._get_services_ids(
            provider_id,
            ('heat_public', 'heating_water_public', 'water_public',
             'waste_water_public', 'gas_public', 'electricity_public')
        )

    ReasonTypes = {
        'manual': 'ручной',
        'meter': 'возврат среднего/норматива',
        'meter_heated': 'возврат среднего/норматива',
        'bank': 'разница в комиссии банка',
        'discount': 'скидка',
    }

    def get_payments_sections_3_6(self, entry_source, export_task):
        multi_entry = []
        entry_dict = {}

        for accrual in entry_source['accruals']:
            if accrual.sector_code == 'capital_repair':
                capital_repair_title = self.get_gis_title(
                    accrual.owner,
                    CAPITAL_REPAIR,
                )
                if not capital_repair_title:
                    continue
            for accrual_service in accrual.services:
                service_type = accrual_service.service_type
                accrual_service_norma = round(accrual_service.norma, 6)
                accrual_service_tariff = round(accrual_service.tariff / 100, 2)
                accrual_service_value = round(accrual_service.value / 100, 2)
                round_recalculation = round(
                    (
                        accrual_service.totals.recalculations +
                        accrual_service.totals.shortfalls
                    ) / 100,
                    2
                )
                totals_privileges = round(
                    accrual_service.totals.privileges / 100, 2
                )
                totals_recalculations = round(
                    accrual_service.totals.recalculations / 100,
                    2
                )
                service_title = self.get_gis_title(
                    accrual.owner,
                    service_type,
                )
                val = round(
                    (
                        accrual_service.value +
                        accrual_service.totals.recalculations +
                        accrual_service.totals.shortfalls +
                        accrual_service.totals.privileges
                    ) / 100,
                    2
                )

                if not service_title:
                    continue

                consumption_method = accrual_service.method or ''

                if consumption_method == '':
                    consumption_method_str = ''
                elif self._is_waste_water(accrual.owner, service_type):
                    consumption_method_str = 'Иное'
                elif consumption_method in {
                    ConsumptionType.METER,
                    ConsumptionType.HOUSE_METER,
                }:
                    consumption_method_str = 'Прибор учета'
                elif consumption_method in {
                    ConsumptionType.NORMA,
                    ConsumptionType.NORMA_WOM,
                }:
                    consumption_method_str = 'Норматив'
                else:
                    consumption_method_str = 'Иное'

                service_category = None

                # Перечень услуг попадающих в колонку "общедомовые нужды"
                if (
                        service_type
                        in self.get_public_services_ids(accrual.owner)
                        or self._is_heat(accrual.owner, service_type)
                ):
                    service_category = 'public'
                    services_individual_method = ''
                    services_individual_volumes = ''
                    services_collective_method = consumption_method_str
                    services_collective_volumes = \
                        round(accrual_service.consumption, 7)

                # Перечень услуг попадающих в колонку "индивидуальное потребление"
                elif service_type in self.get_individual_services_ids(
                        accrual.owner
                ):
                    service_category = 'individual'
                    services_individual_method = consumption_method_str
                    services_individual_volumes = \
                        round(accrual_service.consumption, 7)
                    services_collective_method = ''
                    services_collective_volumes = ''

                #
                else:

                    services_individual_method = ''
                    services_individual_volumes = ''
                    services_collective_method = ''
                    services_collective_volumes = ''

                if service_title in entry_dict:
                    entry = entry_dict[service_title]
                    if not service_category:
                        entry[PD_Section_3_6.TARIFF] += accrual_service_tariff
                    if accrual_service_tariff:
                        entry[PD_Section_3_6.TARIFF] = accrual_service_tariff
                    entry[PD_Section_3_6.TOTAL_CALCULATED] += \
                        accrual_service_value
                    entry[PD_Section_3_6.RECALCULATION] += round_recalculation
                    entry[PD_Section_3_6.PRIVILEGES] += totals_privileges
                    if service_category == 'individual':
                        if entry[PD_Section_3_6.NORM_INDIVIDUAL] != '':
                            entry[PD_Section_3_6.NORM_INDIVIDUAL] += \
                                accrual_service_norma
                        if entry[PD_Section_3_6.TO_PAY_INDIVIDUAL] != '':
                            entry[PD_Section_3_6.TO_PAY_INDIVIDUAL] += \
                                accrual_service_value
                        if entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VALUES] != '':
                            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VALUES] += \
                                accrual_service_value
                        if entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES] == '':
                            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES] = \
                                services_individual_volumes
                        else:
                            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES] += \
                                services_individual_volumes
                        if services_individual_method:
                            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_METHOD] = \
                                services_individual_method
                    if service_category == 'public':
                        if entry[PD_Section_3_6.NORM_COLLECTIVE] != '':
                            entry[PD_Section_3_6.NORM_COLLECTIVE] += \
                                accrual_service_norma
                        if entry[PD_Section_3_6.TO_PAY_COLLECTIVE] != '':
                            entry[PD_Section_3_6.TO_PAY_COLLECTIVE] += \
                                accrual_service_value
                        if entry[PD_Section_3_6.SERVICES_COLLECTIVE_VALUES] != '':
                            entry[PD_Section_3_6.SERVICES_COLLECTIVE_VALUES] += \
                                accrual_service_value
                        if entry[PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES] == '':
                            entry[PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES] = \
                                services_collective_volumes
                        else:
                            entry[PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES] += \
                                services_collective_volumes
                        if services_collective_method:
                            entry[PD_Section_3_6.SERVICES_COLLECTIVE_METHOD] = \
                                services_collective_method
                    if accrual_service.totals.recalculations:
                        if entry[PD_Section_3_6.RECALCULATIONS_TOTAL] == '':
                            entry[PD_Section_3_6.RECALCULATIONS_TOTAL] = \
                                totals_recalculations
                        else:
                            entry[PD_Section_3_6.RECALCULATIONS_TOTAL] += \
                                totals_recalculations
                        entry[PD_Section_3_6.RECALCULATIONS_REASON] = '; '.join([
                            self.ReasonTypes.get(recalc.reason, '')
                            for recalc in accrual_service.recalculations
                        ])
                    if service_category:
                        if entry[PD_Section_3_6.TO_PAY_WITH_DEFERRED] == '':
                            entry[PD_Section_3_6.TO_PAY_WITH_DEFERRED] = val
                        else:
                            entry[PD_Section_3_6.TO_PAY_WITH_DEFERRED] += val
                    entry[PD_Section_3_6.TO_PAY_TOTAL] += val
                else:
                    entry = {
                        PD_Section_3_6.DOC_NUMBER: str(accrual.id),
                        PD_Section_3_6.SERVICE: service_title,

                        # Раздел 3. Расчет размера платы за содержание и ремонт жилого помещения
                        # и коммунальные услуги
                        PD_Section_3_6.SERVICES_INDIVIDUAL_METHOD: services_individual_method,
                        PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES: services_individual_volumes,
                        PD_Section_3_6.SERVICES_COLLECTIVE_METHOD: services_collective_method,
                        PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES: services_collective_volumes,

                        PD_Section_3_6.TARIFF: accrual_service_tariff,
                        PD_Section_3_6.TOTAL_CALCULATED: accrual_service_value,
                        PD_Section_3_6.RECALCULATION: round_recalculation,
                        PD_Section_3_6.PRIVILEGES: totals_privileges,
                        PD_Section_3_6.CALCULATION_COMMENT: '',  # TODO?

                        # Раздел 4. Справочная информация  # TODO?
                        PD_Section_3_6.NORM_INDIVIDUAL: (
                            accrual_service_norma
                            if service_category == 'individual'
                            else ''
                        ),
                        PD_Section_3_6.NORM_COLLECTIVE: (
                            accrual_service_norma
                            if service_category == 'public'
                            else ''
                        ),
                        PD_Section_3_6.CURRENT_READINGS_INDIVIDUAL: '',
                        PD_Section_3_6.CURRENT_READINGS_COLLECTIVE: '',
                        PD_Section_3_6.TOTAL_VOLUME_INDIVIDUAL: '',
                        PD_Section_3_6.TOTAL_VOLUME_COLLECTIVE: '',

                        # Раздел 5. Сведения о перерасчетах

                        PD_Section_3_6.RECALCULATIONS_TOTAL: (
                            totals_recalculations
                            if totals_recalculations
                            else ''
                        ),
                        PD_Section_3_6.RECALCULATIONS_REASON: '; '.join([
                            self.ReasonTypes.get(recalc.reason, '')
                            for recalc in accrual_service.recalculations
                        ]),

                        # NOTE Рассрочки платежа в системе сейчас нет
                        # Раздел 6. Расчет суммы к оплате с учетом рассрочки платежа
                        PD_Section_3_6.DEFERRED_PAY_CURRENT_PERIOD: '',
                        PD_Section_3_6.DEFERRED_PAY_CURRENT_PERIOD_PREVIOUS_PERIODS: '',

                        PD_Section_3_6.TO_PAY_WITH_DEFERRED: val if service_category else '',
                        PD_Section_3_6.DEFERRED_PAY_PCT_RUB: 0 if service_category else '',
                        PD_Section_3_6.DEFERRED_PAY_PCT_PCT: 0 if service_category else '',
                        # Итого к оплате за расчетный период, руб.
                        PD_Section_3_6.TO_PAY_TOTAL: val,
                        PD_Section_3_6.TO_PAY_INDIVIDUAL: (
                            accrual_service_value
                            if service_category == 'individual'
                            else ''
                        ),
                        PD_Section_3_6.TO_PAY_COLLECTIVE: (
                            accrual_service_value
                            if service_category == 'public'
                            else ''
                        ),
                        PD_Section_3_6.SERVICES_INDIVIDUAL_VALUES: (
                            accrual_service_value
                            if service_category == 'individual'
                            else ''
                        ),
                        PD_Section_3_6.SERVICES_COLLECTIVE_VALUES: (
                            accrual_service_value
                            if service_category == 'public'
                            else ''
                        ),
                    }
                    if entry.get(PD_Section_3_6.TO_PAY_WITH_DEFERRED):
                        if not entry[PD_Section_3_6.DEFERRED_PAY_PCT_RUB]:
                            entry[PD_Section_3_6.DEFERRED_PAY_PCT_RUB] = 0
                        if not entry[PD_Section_3_6.DEFERRED_PAY_PCT_PCT]:
                            entry[PD_Section_3_6.DEFERRED_PAY_PCT_PCT] = 0
                    multi_entry.append(entry)
                    entry_dict[service_title] = entry

        for entry in multi_entry:
            self.check_field_title(entry)
            self.change_services_method(entry)
            self.check_recalculation(entry)
        return multi_entry

    def _fill_cached_binds(self, provider_id):
        binds = ServiceTypeGisBind.objects(
            provider=provider_id,
            closed=None,
        )
        self.service_types_binds = {}
        for b in binds:
            self.service_types_binds[b.service_type] = b.gis_title
            if b.service_code:
                self.service_types_binds[b.service_code] = b.gis_title

    def get_gis_title(self, provider_id, service_id):
        if not self.service_types_binds or self.cached_provider != provider_id:
            self._fill_cached_binds(provider_id)
        if service_id in self.service_types_binds:
            return self.service_types_binds[service_id]
        all_services = self.get_service_types_children(provider_id)
        for code, children in all_services.items():
            if code in self.service_types_binds and service_id in children:
                return self.service_types_binds[code]
        return ''

    def _is_waste_water(self, provider_id, service_id):
        if not self.service_types_binds or self.cached_provider != provider_id:
            self._fill_cached_binds(provider_id)
        all_services = self.get_service_types_children(provider_id)
        if 'waste_water' in all_services:
            return service_id in all_services['waste_water']
        return False

    def _is_heat(self, provider_id, service_id):
        if not self.service_types_binds or self.cached_provider != provider_id:
            self._fill_cached_binds(provider_id)
        all_services = self.get_service_types_children(provider_id)
        if 'heat' in all_services:
            return service_id in all_services['heat']
        return False

    def get_payments_dpd(self, entry_source, export_task):
        pass

    def get_payments_court(self, entry_source, export_task):
        multi_entry = []
        for accrual in entry_source['accruals']:
            if accrual.totals.penalties:
                entry = {
                    PaymentsCourtFields.DOC_NUMBER: str(accrual.id),
                    PaymentsCourtFields.TYPE: 'Пени',
                    PaymentsCourtFields.BASIS: 'Пени',
                    PaymentsCourtFields.VALUE: accrual.totals.penalties / 100,
                }
                multi_entry.append(entry)

        return multi_entry

    def get_payments_section_services(self, entry_source, export_task):
        provider_id = export_task.provider.id
        binds = ServiceTypeGisName.objects(provider=provider_id, closed=None)

        multi_entry = []
        ready = []

        for bind in binds:
            if bind.gis_title not in ready:
                ready.append(bind.gis_title)
                entry = {
                    PaymentsServicesFields.REFERENCE_NAME: bind.reference_name,
                    PaymentsServicesFields.REFERENCE_NUMBER: bind.reference_number,
                    PaymentsServicesFields.POSITION_NAME: bind.gis_title,
                    PaymentsServicesFields.POSITION_NUMBER: bind.position_number,
                }
                multi_entry.append(entry)

        return multi_entry

    def get_capital_repair_data(self, entry_source, export_task):
        pass

    def get_requisites_data(self, entry_source, export_task):
        pass

    @staticmethod
    def check_recalculation(entry):
        if not entry[PD_Section_3_6.RECALCULATIONS_TOTAL]:
            entry[PD_Section_3_6.RECALCULATIONS_REASON] = ''

    @staticmethod
    def check_field_title(entry):
        if entry[PD_Section_3_6.SERVICE].lower() in NOT_FILL_FIELDS:
            entry[PD_Section_3_6.TO_PAY_WITH_DEFERRED] = ''
            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_METHOD] = ''
            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES] = ''
            entry[PD_Section_3_6.SERVICES_COLLECTIVE_METHOD] = ''
            entry[PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES] = ''

    @staticmethod
    def change_services_method(entry):
        if str(entry[PD_Section_3_6.SERVICES_INDIVIDUAL_VOLUMES]) and \
                not entry[PD_Section_3_6.SERVICES_INDIVIDUAL_METHOD]:
            entry[PD_Section_3_6.SERVICES_INDIVIDUAL_METHOD] = 'Иное'
        if str(entry[PD_Section_3_6.SERVICES_COLLECTIVE_VOLUMES]) and \
                not entry[PD_Section_3_6.SERVICES_COLLECTIVE_METHOD]:
            entry[PD_Section_3_6.SERVICES_COLLECTIVE_METHOD] = 'Иное'
