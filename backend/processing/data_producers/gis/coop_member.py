from datetime import datetime

from app.house.models.house import House
from app.personnel.models.department import Department
from processing.models.billing.account import Tenant
from processing.models.billing.private_document import PrivateDocument
from processing.models.choices import PrivateDocumentsTypes, \
    PRIVATE_DOCUMENTS_TYPE_CHOICES
from .base import BaseGISDataProducer


class CoopMembersCommonFields:
    NUMBER = '№'
    ACCOUNT_LEGAL_TYPE = 'Тип лица'
    NAME = 'Имя'
    FAMILY_NAME = 'Фамилия'
    PATRONYMIC_NAME = 'Отчество'
    SNILS = 'СНИЛС'
    PRIVATE_DOCUMENT_TYPE = 'Вид документа'
    PRIVATE_DOCUMENT_NUMBER = 'Номер документа'
    PRIVATE_DOCUMENT_SERIES = 'Серия документа'
    PRIVATE_DOCUMENT_DATE = 'Дата выдачи документа'
    OGRN = 'ОГРН (заполняется только для Тип лица = юридическое лицо)'
    ADOPTION_DATE = 'Дата принятия в члены товарищества, кооператива'
    MEMBER_ROLE = 'Информация об избрании в состав правления, ревизионную комиссию'
    ELECTED_FROM_DATE = 'Избран в состав правления/ревизионной комиссии ТСЖ, кооператива на срок с'  # NOTE Не совпадает с шаблоном
    ELECTED_TILL_DATE = 'Избран в состав правления/ревизионной комиссии ТСЖ, кооператива на срок по'  # NOTE Не совпадает с шаблоном
    ELECTED_MANAGMENT_CHAIRMAN_FROM_DATE = 'Избран председателем правления на срок с'  # NOTE Не совпадает с шаблоном
    ELECTED_MANAGMENT_CHAIRMAN_TILL_DATE = 'Избран председателем правления на срок по'  # NOTE Не совпадает с шаблоном
    ELECTED_AUDIT_CHAIRMAN_FROM_DATE = 'Избран председателем ревизионной комиссии на срок с'  # NOTE Не совпадает с шаблоном
    ELECTED_AUDIT_CHAIRMAN_TILL_DATE = 'Избран председателем ревизионной комиссии на срок по'  # NOTE Не совпадает с шаблоном
    PHONE_NUMBER = 'Номер контактного телефона'
    FAX_NUMBER = 'Номер факса'
    EMAIL = 'Адрес электронной почты'


class CoopMembersOwnershipFields:
    NUMBER = '№ строки с листа "Общая информация"'
    HOUSE_FIAS_GUID = 'Глобальный уникальный идентификатор дома по ФИАС' \
                      '/Идентификационный код дома в ГИС ЖКХ'
    AREA_STR_NUMBER = 'Номер помещения (обязательно для заполнения, если дом является многоквартирным)'
    OWNERSHIP_CERTIFICATE_NUMBER = 'Номер гос. регистрации права собственности на помещение'
    OWNERSHIP_CERTIFICATE_DATE = 'Дата гос. регистрации права собственности на помещение'
    OWNERSHIP_SHARE_NUMERATOR = 'Размер доли в общем имуществе МКД (в формате X/Y). Числитель'  # NOTE Не совпадает с шаблоном
    OWNERSHIP_SHARE_DENOMINATOR = 'Размер доли в общем имуществе МКД (в формате X/Y). Знаменатель'  # NOTE Не совпадает с шаблоном


class CoopMembersDataProducer(BaseGISDataProducer):
    XLSX_TEMPLATE = 'templates/gis/coop_member_11_11_0_1.xlsx'
    XLSX_WORKSHEETS = {
        'Общая информация': {
            'entry_produce_method': 'get_entry_coop_members_common',
            'title': 'Общая информация',
            'start_row': 3,
            'columns': {
                CoopMembersCommonFields.NUMBER: 'A',
                CoopMembersCommonFields.ACCOUNT_LEGAL_TYPE: 'B',
                CoopMembersCommonFields.NAME: 'C',
                CoopMembersCommonFields.FAMILY_NAME: 'D',
                CoopMembersCommonFields.PATRONYMIC_NAME: 'E',
                CoopMembersCommonFields.SNILS: 'F',
                CoopMembersCommonFields.PRIVATE_DOCUMENT_TYPE: 'G',
                CoopMembersCommonFields.PRIVATE_DOCUMENT_NUMBER: 'H',
                CoopMembersCommonFields.PRIVATE_DOCUMENT_SERIES: 'I',
                CoopMembersCommonFields.PRIVATE_DOCUMENT_DATE: 'J',
                CoopMembersCommonFields.OGRN: 'K',
                CoopMembersCommonFields.ADOPTION_DATE: 'L',
                CoopMembersCommonFields.MEMBER_ROLE: 'M',
                CoopMembersCommonFields.ELECTED_FROM_DATE: 'N',
                CoopMembersCommonFields.ELECTED_TILL_DATE: 'O',
                CoopMembersCommonFields.ELECTED_MANAGMENT_CHAIRMAN_FROM_DATE: 'P',
                CoopMembersCommonFields.ELECTED_MANAGMENT_CHAIRMAN_TILL_DATE: 'Q',
                CoopMembersCommonFields.ELECTED_AUDIT_CHAIRMAN_FROM_DATE: 'R',
                CoopMembersCommonFields.ELECTED_AUDIT_CHAIRMAN_TILL_DATE: 'S',
                CoopMembersCommonFields.PHONE_NUMBER: 'T',
                CoopMembersCommonFields.FAX_NUMBER: 'U',
                CoopMembersCommonFields.EMAIL: 'V',
            }
        },
        'Информация о праве соб-ти': {
            'entry_produce_method': 'get_entry_coop_members_ownership_info',
            'title': 'Информация о праве соб-ти',
            'start_row': 4,
            'columns': {
                CoopMembersOwnershipFields.NUMBER: 'A',
                CoopMembersOwnershipFields.HOUSE_FIAS_GUID: 'B',
                CoopMembersOwnershipFields.AREA_STR_NUMBER: 'C',
                CoopMembersOwnershipFields.OWNERSHIP_CERTIFICATE_NUMBER: 'D',
                CoopMembersOwnershipFields.OWNERSHIP_CERTIFICATE_DATE: 'E',
                CoopMembersOwnershipFields.OWNERSHIP_SHARE_NUMERATOR: 'F',
                CoopMembersOwnershipFields.OWNERSHIP_SHARE_DENOMINATOR: 'G',
            }
        },
    }

    def get_entry_coop_members_common(self, entry_source, export_task):

        account = entry_source['account']

        is_legal_person = True if 'LegalTenant' in account._type else False

        private_doc = PrivateDocument.objects(
            is_actual=True,
            account=account.id
        ).first()

        # TODO повторяющийся код(accounts), вынести в Tenant
        private_doc_type = private_doc_number = private_doc_series = private_doc_date = None
        if private_doc:
            private_doc_known_types = [t for t in private_doc._type if hasattr(PrivateDocumentsTypes, t)]
            document_types = [doc_description for doc_type, doc_description in PRIVATE_DOCUMENTS_TYPE_CHOICES if doc_type in private_doc_known_types]

            if private_doc and private_doc_known_types and document_types:
                private_doc_type = document_types[0]
                private_doc_number = private_doc.number
                private_doc_series = private_doc.series
                private_doc_date = private_doc.issue_date
        # TODO END

        adoption_date = account.coop_member_date_from.date() if all([account.is_coop_member, account.coop_member_date_from]) else None

        # TODO Вынести в Account: Определение выборных должностей, актуальных для аккаунта(жителя)
        # TODO INDEX: [tenants]
        account_workers = list(Tenant.objects(tenants=account.id))

        managment_chairman_system_positions = [
            '526236c6e0e34c4743823634',  # Правление ТСЖ/Председатель Правления
            '526236c6e0e34c474382365a',  # Правление ЖСК/Председатель Правления
        ]

        audit_chairman_system_position = [
            '57c84bd77bbafe00bc2b9851',  # Правление ТСЖ/Председатель ревизионной комиссии
            '57c84bd77bbafe00bc2b9852',  # Правление ЖСК/Председатель ревизионной комиссии
        ]

        managment_member_system_positions = [
            '526236c6e0e34c4743823633',  # Правление ТСЖ/Член Правления
            '526236c6e0e34c4743823659',  # Правление ЖСК/Член Правления
        ]

        audit_member_system_positions = [
            '526236c6e0e34c4743823632',  # Правление ТСЖ/Член ревизионной комиссии
            '526236c6e0e34c4743823658',  # Правление ЖСК/Член ревизионной комиссии
        ]

        def check_has_system_position(workers, system_positions):
            """
                Возвращает Account работника, системная должность которого находится в system_positions,
                если есть аккаунт привязаный к данному работнику
            """

            for department in Department.objects(
                    positions__system_position__in=system_positions,
                    positions__id__in=[worker.position.id for worker in workers]
            ):

                for position in department.positions:
                    for worker in workers:
                        if str(position.system_position) in system_positions and position.id == worker.position.id:
                            return worker

            return None

        def worker_valid_election(worker):

            valid_elections = [
                history_entry for history_entry in worker.election_history if
                history_entry.date_from < datetime.now() < history_entry.date_till
            ] if worker and worker.election_history else []

            if valid_elections:
                election = valid_elections[0]  # любой
                election.date_till = election.date_till.date()
                election.date_from = election.date_from.date()

            return valid_elections[0] if valid_elections else None

        managment_chairman_worker = check_has_system_position(account_workers, managment_chairman_system_positions)
        audit_chairman_worker = check_has_system_position(account_workers, audit_chairman_system_position)
        managment_comittee_member_worker = check_has_system_position(account_workers, managment_member_system_positions)
        audit_comittee_member_worker = check_has_system_position(account_workers, audit_member_system_positions)

        if managment_chairman_worker or managment_comittee_member_worker:
            member_worker = managment_chairman_worker or managment_comittee_member_worker
            member_role = 'Избран в состав правления товарищества, кооператива'  # TODO choices
        elif audit_chairman_worker or audit_comittee_member_worker:
            member_worker = audit_chairman_worker or audit_comittee_member_worker
            if account.is_coop_member:
                member_role = 'Избран в состав ревизионной комиссии и является членом товарищества, кооператива'
            else:
                member_role = 'Избран в состав ревизионной комиссии и не является членом товарищества, кооператива'
        else:
            member_worker = None
            member_role = 'Не включен в состав правления/ревизионной комиссии товарищества, кооператива'  # TODO choices

        member_election = worker_valid_election(member_worker)

        comittee_election = member_election if managment_comittee_member_worker or audit_comittee_member_worker else None
        management_chairman_election = member_election if managment_chairman_worker else None
        audit_chairman_election = member_election if audit_chairman_worker else None
        # TODO END Вынести в Account

        entry = {
            CoopMembersCommonFields.NUMBER: account.number,
            CoopMembersCommonFields.ACCOUNT_LEGAL_TYPE: 'Юридическое лицо' if is_legal_person else 'Физическое лицо',  # TODO вынести в choice
            CoopMembersCommonFields.NAME: account.short_name if is_legal_person else account.first_name,  # NOTE Не выводим
            CoopMembersCommonFields.FAMILY_NAME: account.last_name_upper.capitalize() if account.last_name_upper else '',  # NOTE Не выводим
            CoopMembersCommonFields.PATRONYMIC_NAME: account.patronymic_name,  # NOTE Не выводим
            CoopMembersCommonFields.SNILS: account.snils,
            CoopMembersCommonFields.PRIVATE_DOCUMENT_TYPE: private_doc_type,
            CoopMembersCommonFields.PRIVATE_DOCUMENT_NUMBER: private_doc_number,
            CoopMembersCommonFields.PRIVATE_DOCUMENT_SERIES: private_doc_series,
            CoopMembersCommonFields.PRIVATE_DOCUMENT_DATE: private_doc_date,
            CoopMembersCommonFields.OGRN: account.ogrn if is_legal_person else '',
            CoopMembersCommonFields.ADOPTION_DATE: adoption_date if adoption_date else '',
            CoopMembersCommonFields.MEMBER_ROLE: member_role,
            CoopMembersCommonFields.ELECTED_FROM_DATE: comittee_election.date_from if comittee_election else '',
            CoopMembersCommonFields.ELECTED_TILL_DATE: comittee_election.date_till if comittee_election else '',
            CoopMembersCommonFields.ELECTED_MANAGMENT_CHAIRMAN_FROM_DATE: management_chairman_election.date_from if management_chairman_election else '',
            CoopMembersCommonFields.ELECTED_MANAGMENT_CHAIRMAN_TILL_DATE: management_chairman_election.date_till if management_chairman_election else '',
            CoopMembersCommonFields.ELECTED_AUDIT_CHAIRMAN_FROM_DATE: audit_chairman_election.date_from if audit_chairman_election else '',
            CoopMembersCommonFields.ELECTED_AUDIT_CHAIRMAN_TILL_DATE: audit_chairman_election.date_till if audit_chairman_election else '',
            CoopMembersCommonFields.PHONE_NUMBER: '',  # NOTE Не выводим?
            CoopMembersCommonFields.FAX_NUMBER: '',  # NOTE Не выводи?
            CoopMembersCommonFields.EMAIL: '',  # NOTE Не выводим?
        }

        return entry

    def get_entry_coop_members_ownership_info(self, entry_source, export_task):
        account = entry_source['account']

        house = House.objects(id=account.area.house.id).first()

        # Значения по умолчанию
        account_ownership_share = [0, 1]
        ownership_certificate_number = ''
        ownership_certificate_date = ''

        if account.statuses.ownership:
            account_ownership_share = account.statuses.ownership['property_share'] or account_ownership_share
            cert = account.statuses.ownership['certificate']
            if cert and cert.series and cert.number:

                ownership_certificate_number = ' '.join([
                    cert.series,
                    cert.number,
                ])

                ownership_certificate_date = cert.issued_at

        entry = {
            CoopMembersOwnershipFields.NUMBER: account.number,
            CoopMembersOwnershipFields.HOUSE_FIAS_GUID: house.gis_fias,
            CoopMembersOwnershipFields.AREA_STR_NUMBER: account.area.str_number,
            CoopMembersOwnershipFields.OWNERSHIP_CERTIFICATE_NUMBER: ownership_certificate_number,
            CoopMembersOwnershipFields.OWNERSHIP_CERTIFICATE_DATE: ownership_certificate_date,
            CoopMembersOwnershipFields.OWNERSHIP_SHARE_NUMERATOR: account_ownership_share[0],
            CoopMembersOwnershipFields.OWNERSHIP_SHARE_DENOMINATOR: account_ownership_share[1],
        }

        return entry
