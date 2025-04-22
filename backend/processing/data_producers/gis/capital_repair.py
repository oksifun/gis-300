from mongoengine import Q

from app.house.models.house import House
from processing.models.billing.settings import Settings

from .base import BaseGISDataProducer


class CapitalRepairInfoFields:
    ADDRESS = 'Адрес дома'
    HOUSE_FIAS_GUID = 'Глобальный уникальный идентификатор дома по ФИАС' \
                      '/Идентификационный код дома в ГИС ЖКХ'
    ACCOUNT_TYPE = 'Тип счета'
    REASON = 'Основание'
    DECISION_DATE = 'Дата вступления решения в силу'
    BANK_ACCOUNT_NUMBER = 'Номер счета'
    BANK_BIK = 'БИК кредитной организации, в которой открыт счет'
    BANK_OGRN = 'ОГРН кредитной организации, в которой открыт счет'
    BANK_KPP = 'КПП кредитной организации, в которой открыт счет'
    BANK_ACCOUNT_CREATE_DATE = 'Дата открытия счета'
    PROTOCOL_NUMBER = 'Номер протокола'
    PROTOCOL_DATE = 'Дата протокола'
    # DECISION_DOC_NAME = 'Полное наименование документа'
    # DECISION_DOC_TYPE = 'Вид документа'
    # DECISION_DOC_NUMBER = 'Номер документа'
    # DECISION_DOC_DATE = 'Дата документа'


class CapitalRepairInfoDataProducer(BaseGISDataProducer):
    XLSX_TEMPLATE = 'templates/gis/capital_repair_11_3_0_1.xlsx'
    XLSX_WORKSHEETS = {
        'Способ формирования фонда КР': {
            'entry_produce_method': 'get_entry_capital_repair_info',
            'title': 'Способ формирования фонда КР',
            'start_row': 3,
            'columns': {
                CapitalRepairInfoFields.ADDRESS: 'A',
                CapitalRepairInfoFields.HOUSE_FIAS_GUID: 'B',
                CapitalRepairInfoFields.ACCOUNT_TYPE: 'C',
                CapitalRepairInfoFields.REASON: 'D',
                CapitalRepairInfoFields.DECISION_DATE: 'E',
                CapitalRepairInfoFields.BANK_ACCOUNT_NUMBER: 'F',
                CapitalRepairInfoFields.BANK_BIK: 'G',
                CapitalRepairInfoFields.BANK_OGRN: 'H',
                CapitalRepairInfoFields.BANK_KPP: 'I',
                CapitalRepairInfoFields.BANK_ACCOUNT_CREATE_DATE: 'J',
                CapitalRepairInfoFields.PROTOCOL_NUMBER: 'K',
                CapitalRepairInfoFields.PROTOCOL_DATE: 'L',
                # CapitalRepairInfoFields.DECISION_DOC_NAME: 'M',
                # CapitalRepairInfoFields.DECISION_DOC_TYPE: 'N',
                # CapitalRepairInfoFields.DECISION_DOC_NUMBER: 'O',
                # CapitalRepairInfoFields.DECISION_DOC_DATE: 'P',
            }
        },
    }

    def get_entry_capital_repair_info(self, entry_source, export_task):
        multi_entry = []

        provider = entry_source['provider']
        date = entry_source['date']

        q_provider_bind = Q(service_binds__provider=provider.id)
        q_actual_bind = (
            Q(service_binds__date_start__lt=date)
            & (
                Q(service_binds__date_end=None)
                | Q(service_binds__date_end__gte=date)
            )
        )
        q_active_bind = Q(service_binds__is_active=True)

        houses = House.objects(q_provider_bind & q_actual_bind & q_active_bind)

        for house in houses:

            # Протоколы принятия решений, обратно упорядоченные по дате
            cr_protocols = list(sorted(
                [
                    protocol
                    for protocol in house.protocol_doc
                    if protocol.category == 'capital_repair_type'
                ],
                key=lambda protocol: protocol.date,
                reverse=True
            ))

            cr_protocol = cr_protocols[0] if cr_protocols else None

            # TODO choices
            # Если есть хоть один протокол собрания с категорией "Решение о выборе способа формирования ... ", то основание - решение собрания
            reason = 'Решение общего собрания собственников' if cr_protocol else 'Решение ОМС'

            # TODO choices
            # TODO не сохраняется поле, в котором хранится решение?
            account_type = 'Специальный счет' if cr_protocol else 'Счет регионального оператора'

            # TODO Перенести определение параметров счета для кап.ремонта в House
            bank_account_number = None
            bank_ogrn = None
            bank_bik = None
            bank_kpp = None
            bank_account_date_from = None

            if cr_protocol:

                # TODO 'capital_repair' перенести в choices
                capital_repair_settings = [
                    s
                    for s in Settings.objects(house=house.id).first().sectors
                    if s.sector_code == 'capital_repair'
                ]

                if capital_repair_settings:

                    capital_repair_settings = capital_repair_settings[0]

                    bank_account_number = capital_repair_settings.bank_account or ''
                    bank_accounts = [
                        bank_acc
                        for bank_acc in provider.bank_accounts
                        if bank_acc.number == bank_account_number
                    ]
                    bank_account = bank_accounts[0] if bank_accounts else None

                    if bank_account:
                        bank_ogrn = bank_account.bic.ogrn
                        if bank_account.bic.bic_body:
                            bank_bik = bank_account.bic.bic_body[0].BIC
                        else:
                            bank_bik = ''
                        bank_kpp = bank_account.bic.kpp
                        bank_account_date_from = bank_account.date_from
                protocol_number = cr_protocol.number
                protocol_date = cr_protocol.date
            else:
                protocol_number = None
                protocol_date = None
            # TODO END

            entry = {
                CapitalRepairInfoFields.ADDRESS: house.address,
                CapitalRepairInfoFields.HOUSE_FIAS_GUID: house.fias_house_guid,
                CapitalRepairInfoFields.ACCOUNT_TYPE: account_type,
                CapitalRepairInfoFields.REASON: reason,
                CapitalRepairInfoFields.DECISION_DATE: cr_protocol.date.date() if cr_protocol else '',
                CapitalRepairInfoFields.BANK_ACCOUNT_NUMBER: bank_account_number or '',
                CapitalRepairInfoFields.BANK_BIK: bank_bik or '',
                CapitalRepairInfoFields.BANK_OGRN: bank_ogrn or '',
                CapitalRepairInfoFields.BANK_KPP: bank_kpp or '',
                CapitalRepairInfoFields.BANK_ACCOUNT_CREATE_DATE: bank_account_date_from or '',
                CapitalRepairInfoFields.PROTOCOL_NUMBER: protocol_number,
                CapitalRepairInfoFields.PROTOCOL_DATE: protocol_date,
            }

            multi_entry.append(entry)

        return multi_entry
