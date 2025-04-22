from typing import Optional

from datetime import datetime, timedelta
from decimal import Decimal
from bson import ObjectId

from app.gis.core.web_service import WebService
from app.gis.core.custom_operation import ExportOperation, ImportOperation
from app.gis.core.exceptions import GisError, PublicError, \
    NoDataError, NoGUIDError, PendingSignal, NoRequestWarning

from app.gis.utils.common import sb, fmt_period, get_period
from app.gis.utils.services import (
    is_heating, is_waste_water,
    is_individual_service, is_public_service, is_municipal_service,
    get_bank_accounts, get_tariff_plan_services
)
from app.gis.utils.accounts import get_accrual_accounts, \
    get_account_type_by, get_account_type_name

from app.gis.models.choices import GisObjectType
from app.gis.models.guid import GUID
from app.gis.models.nsi_ref import nsiRef

from app.gis.services.nsi import resource_nsi_code_of
from app.gis.services.house_management import HouseManagement

from app.accruals.models.accrual_document import AccrualDoc

from processing.models.billing.payment import Payment
from processing.models.billing.accrual import Accrual
from processing.models.billing.service_type import ServiceType, \
    ServiceTypeGisName, ServiceTypeGisBind

from processing.models.choices import (
    AccrualsSectorType, ConsumptionType,
    ACCRUAL_SECTOR_TYPE_CHOICES, RECALCULATION_REASON_TYPE_CHOICES,
    ACCRUAL_DOCUMENT_STATUS_CHOICES, RecalculationReasonType
)

from processing.data_producers.balance.base import HouseAccountsBalance, \
    CONDUCTED_STATUSES


def to_rubles(kopeck_value: int, positive: bool = None) -> Decimal:
    """
    Формат денежных значений ГИС ЖКХ: decimal(11.2),
        итоговые суммы - 16.2, значения со знаком - 8.2

    :param kopeck_value: сумма в копейках!
    :param positive: None - положительное, отрицательное или 0,
        True - положительное или 0,
        False - отрицательное (по модулю) или 0
    """
    # advance = to_rubles(-date_balance) if date_balance < 0 \
    #     else to_rubles(0)  # отриц. означает наличие ПЕРЕПЛАТЫ (аванса)
    # debt = to_rubles(date_balance) if date_balance > 0 else to_rubles(0)
    if positive is False:  # только отрицательное?
        if kopeck_value > 0:  # получено положительное?
            kopeck_value = 0  # сбрасываем в ноль!
        else:  # получено отрицательное!
            kopeck_value = -kopeck_value  # инвертируем
    elif positive is True:  # только положительное?
        if kopeck_value < 0:  # получено отрицательное?
            kopeck_value = 0  # сбрасываем в ноль!

    return round(  # Decimal.quantize(Decimal('0.01'), ROUND_HALF_UP)
        Decimal(kopeck_value / 100), 2  # [+-]\d+(\.\d{2})?
    ) if kopeck_value else Decimal(0)


def round_volume(value: float) -> str:
    """Формат объемов потребления: decimal(15.7)"""
    # экспоненциальная запись вызывает ошибку
    return '{:.7f}'.format(round(value, 7))  # для xsd::decimal разрешен string


class AckStatus:
    """Статус квитирования"""
    NEW = 0  # Новый (не проходил квитирование)
    ANNUL = 1  # Аннулирован
    ACKED = 2  # Сквитирован
    PARTIAL = 3  # Частично сквитирован
    PRE = 4  # Предварительно сквитирован
    NONE = 5  # Отсутствует возможность сквитировать


ACK_STATUS_DESCRIPTION = {
    AckStatus.NEW:  "Новый (не проходил квитирование)",
    AckStatus.ANNUL: "Аннулирован",
    AckStatus.ACKED: "Сквитирован",
    AckStatus.PARTIAL: "Частично сквитирован",
    AckStatus.PRE: "Предварительно сквитирован",
    AckStatus.NONE: "Отсутствует возможность сквитировать",
}


SECTOR_NAMES = dict(ACCRUAL_SECTOR_TYPE_CHOICES)

REASON_NAMES = dict(RECALCULATION_REASON_TYPE_CHOICES)

STATUS_NAMES = dict(ACCRUAL_DOCUMENT_STATUS_CHOICES)


class ImportPaymentDocumentOperation(ImportOperation):

    @property
    def doc_provider_id(self) -> ObjectId:
        """
        Идентификатор выставившей документ начислений организации (doc.provider)

        Может отличаться от идентификатора получающей платежи (owner)
        """
        return self.agent_id or self.provider_id  # РЦ или УО

    @property
    def doc_provider_name(self) -> str:
        """Название выставившей документы начислений организации"""
        return self.get_provider_data(self.doc_provider_id, 'str_name')

    def period_accruals(self, period: datetime,
            only_conducted: bool = True, not_deleted: bool = True) -> list:
        """Идентификаторы выставленных за период начислений"""
        query: dict = {
            'account.area.house._id': self.house_id,  # индекс
            'owner': self.provider_id,  # получающая платеж за услугу
            'month': get_period(period),  # корректный (текущий) период
        }

        if only_conducted:  # проведенные начисления?
            query['doc.status'] = {'$in': CONDUCTED_STATUSES}

        if not_deleted:  # не удаленные?
            query['is_deleted'] = {'$ne': True}

        if self.agent_id:  # платежный агент (РЦ)?
            query['doc.provider'] = self.agent_id  # выставляющая на оплату

        if self.relation_id:
            query['owner'] = {'$in': [self.relation_id, self.provider_id]}
        return Accrual.objects(__raw__=query).distinct('id')

    def can_withdraw(self, pd_guid: GUID,
            has_id: bool = True, has_ack: bool = False) -> bool:
        """Платежный документ может быть отозван?"""
        assert pd_guid is not None, "Нет данных ГИС ЖКХ платежного документа"

        if pd_guid.deleted:  # отозванный?
            self.failure(pd_guid, "Платежный документ был отозван")
        elif has_id and not pd_guid.unique:  # нет уникального номера?
            self.failure(pd_guid, "Идентификатор ГИС ЖКХ не загружен")
        elif has_ack and not pd_guid.version:  # без извещения о квитировании?
            # для отмены квитирования необходим идентификатор извещения
            self.failure(pd_guid, "Данные о квитировании не загружены")
        else:
            return True  # может быть отозван

        return False  # не может быть отозван


class Bills(WebService):
    """Асинхронный сервис обмена сведениями о начислениях, взаиморасчетах"""

    @classmethod
    def load_pd_guids(cls, self: ImportOperation, *accrual_id_s: ObjectId):
        """Загрузить идентификаторы ПД"""
        assert accrual_id_s, "Отсутствуют идентификаторы загружаемых ПД"

        pd_guids: dict = \
            self.required_guids(GisObjectType.ACCRUAL, *accrual_id_s)

        if self.is_required(GisObjectType.ACCRUAL):  # требуется загрузка?
            _export = \
                Bills.exportPaymentDocumentData(self.provider_id, self.house_id)
            self.follow(_export)  # сохраняем запись о текущей операции

            _export.prepare(*accrual_id_s)  # добавляется период начислений

            # WARN запись об операции сохраняется при выходе из контекста
            raise PendingSignal("Операция отложена до завершения"
                " загрузки идентификаторов ГИС ЖКХ платежных документов")

        return pd_guids  # AccrualId: GUID

    class exportPaymentDocumentData(ExportOperation):
        """Экспорт сведений о платежных документах"""

        VERSION = "13.1.0.1"  # прежние версии: 11.2.0.10, 12.2.0.1
        ELEMENT_LIMIT = 300  # максимум 1000, файл ответа (xml) не более 10 Мб

        period_accruals = ImportPaymentDocumentOperation.period_accruals

        @property
        def description(self) -> str:

            return f"{len(self.object_ids)} ПД за {fmt_period(self.period)}"

        def store_pd(self, exported):
            """PaymentDocument"""
            assert exported.PaymentDocumentNumber, \
                "Получены данные ПД без (идентификационного) номера"
            accrual_id = ObjectId(exported.PaymentDocumentNumber)  # : str

            pd_guid: GUID = self._mapped_guids[accrual_id]

            pd_guid.unique = exported.PaymentDocumentID  # идентификатор ГИС ЖКХ
            pd_guid.desc = f"№{accrual_id}"  # : str

            # TODO сохранять идентификаторы ПД в отдельную коллекцию?
            if exported.Expose:  # Выставлен на оплату?
                self.success(pd_guid)  # AccountGuid - идентификатор ЛС
            elif exported.Withdraw:  # Отозванный?
                self.annulment(pd_guid)  # TODO дата отзыва?
            else:  # Проект?!
                self.deletion(pd_guid)  # сохраняем в состоянии "Удален"

        def _store(self, parsed: dict):
            """Извлеченные из exportPaymentDocumentResultType данные"""
            # получаем сопоставленные идентификаторы ГИС ЖКХ полученных ПД
            self.mapped_guids(GisObjectType.ACCRUAL, *parsed)  # : AccrualId

            for exported in parsed.values():
                self.store_pd(exported)  # сохраняем данные ГИС ЖКХ ПД

        def _parse(self, state_result) -> dict:

            parsed: dict = {}  # AccrualId: PaymentDocument

            results: list = state_result.exportPaymentDocResult
            for result in results:
                if result.ErrorMessage:  # ошибка контролей или бизнес-процесса?
                    self.warning(GisError.message_of(result.ErrorMessage))
                else:  # получены данные ГИС ЖКХ платежного документа!
                    exported = result.PaymentDocument  # : PaymentDocument
                    accrual_id = ObjectId(exported.PaymentDocumentNumber)

                    if exported.Expose:  # Выставлен на оплату?
                        parsed[accrual_id] = exported
                    elif exported.Withdraw:  # Отозванный?
                        if accrual_id not in parsed:  # единственный?
                            parsed[accrual_id] = exported
                        elif parsed[accrual_id].Withdraw:  # повторно?
                            parsed[accrual_id] = exported

            self.log(f"Извлечены данные ГИС ЖКХ {len(parsed)}"
                f" платежных документов из {len(results)} полученных")

            return parsed

        def _compose(self) -> dict:
            """exportPaymentDocumentRequest"""
            payment_documents: list = \
                [str(accrual_id) for accrual_id in self.object_ids]
            assert payment_documents, "Перечень подлежащих загрузке ПД пуст"

            return dict(  # совместно с FIASHouseGuid требуется (1000):
                PaymentDocumentNumber=payment_documents,
                # или AccountNumber - № ЛС или иной идентификатор плательщика
            )

        def _request(self) -> dict:

            request_data: dict = super()._request()  # копия данных запроса

            if 'FIASHouseGuid' not in request_data:
                request_data['FIASHouseGuid'] = self.fias_guid

            request_data.update({
                'Month': self.period.month, 'Year': self.period.year,
            })  # добавляем в запрос месяц и год (периода) начислений

            return request_data

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if 'Month' in request_data or 'Year' in request_data:  # в запросе?
                return False
            elif 'period' not in request_data:  # период не определен?
                return False

            return True

        def prepare(self, *accrual_id_s: ObjectId, **request_data):
            """Подготовка к загрузке данных ПД по периодам"""
            if 'period' in request_data:  # период начислений определен?
                prepared: dict = {request_data['period']: accrual_id_s}
            else:  # необходимо определить период(ы) начислений!
                prepared: dict = {}  # month: [ AccrualId,... ]

                for accrual in Accrual.objects(__raw__={
                    '_id': {'$in': accrual_id_s},
                }).only('month').as_pymongo():
                    prepared.setdefault(
                        accrual['month'], []
                    ).append(accrual['_id'])

            for period, accrual_ids in prepared.items():
                request_data['period'] = period
                super().prepare(*accrual_ids, **request_data)

        def periodic(self, period: datetime = None):
            """Загрузить из ГИС ЖКХ идентификаторы ПД за период"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                accrual_ids: list = self.period_accruals(period, False, False)
                if not accrual_ids:
                    raise NoDataError("Отсутствуют документы начислений для"
                        f" загрузки данных ГИС ЖКХ за {fmt_period(period)}")

            self.log(info=f"Загружаются данные ГИС ЖКХ {len(accrual_ids)}"
                f" ПД за {fmt_period(period)} дома {self.house_address}")

            self(  # PaymentDocumentID - Идентификатор ГИС ЖКХ ПД или:
                *accrual_ids,  # ~ PaymentDocumentNumber
                period=period,  # ~ Year и Month
                # или UnifiedAccountNumber - Номер ЕЛС
                # или ServiceID - Идентификатор ЖКУ
                # или AccountGUID - Идентификатор ЛС в ГИС ЖКХ
            )

    class importPaymentDocumentData(ImportPaymentDocumentOperation):
        """
        Передать сведения о платежных документах

        Выгруженные с "PaymentDocumentID" ПД сначала отзываются

        Ошибки при повторной выгрузке:
            "Платежный документ с таким номером уже существует."
            "Отзыв ПД невозможен, ПД уже отозван."
        """
        VERSION = "11.2.0.16"
        ELEMENT_LIMIT = 500

        REQUIREMENTS = {
            # TODO GisObjectType.SERVICE_TYPE: 100
            GisObjectType.UO_ACCOUNT: 70,  # загружаются данные ЛС всех типов
        }

        DEBUG_SERVICES = False  # вести подробный журнал загрузки услуг?

        @property
        def description(self) -> str:

            return f"{len(self.object_ids)} ПД за {fmt_period(self.period)}"

        def _store(self, import_results: list):

            for result in import_results:  # WARN только сопоставленные (parse)
                pd_guid: GUID = self._mapped_guids[result.TransportGUID]
                if self['update_existing']:  # принудительное обновление?
                    self.success(pd_guid, result.GUID,  # version - квитирование
                        unique=result.UniqueNumber)  # уникальный номер ГИС ЖКХ
                else:  # стандартная выгрузка!
                    self.deletion(pd_guid)  # TODO не подлежит сохранению?

        def _import_accounts(self, *account_id_s: ObjectId):

            _import = HouseManagement.importAccountData(  # выгружаем в ГИС ЖКХ
                self.provider_id, self.house_id,  # лицевые счета (жильцов) дома
                update_existing=True  # WARN принудительно обновляем
            )
            self.lead(_import)  # будет выполнена после завершения текущей

            assert not _import.is_saved, \
                "Запись о последующей операции не должна быть сохранена"
            _import.prepare(*account_id_s)  # WARN сохраняем последующую

            self.save()  # WARN сохраняем предшествующую запись об операции

        def _load_request_data(self):

            # region СПРАВОЧНИКИ УСЛУГ (ОРГАНИЗАЦИИ)
            self._provider_nsi_references = {(ref.reg_num, ref.code):
                ref.as_req for ref in nsiRef.provider_services(
                self.provider_id  # WARN в ГИС ЖКХ нет данных РЦ
            ) if isinstance(ref, ServiceTypeGisName)}  # 1, 51 и 337

            if not self._provider_nsi_references:
                raise NoGUIDError("Не загружены идентификаторы"
                    " ГИС ЖКХ элементов частных справочников (услуг)")

            self.log(f"Элементы частных справочников {self.provider_name}:\n\t"
                + '\n\t'.join(f"{ref[0]}.{ref[1]}" + (
                    f" {req['Name'] or req['Code']} ~ {req['GUID']}"
                    if req else " ~ БЕЗ идентификатора"
                ) for ref, req in self._provider_nsi_references.items()),
                is_spam=not self.DEBUG_SERVICES)

            self._provider_nsi_references.update({(ref.reg_num, ref.code):
                ref.as_req for ref in nsiRef.common_services(2, 3, 50)
            if isinstance(ref, nsiRef)})  # КР, КУ и ЖУ
            # endregion СПРАВОЧНИКИ УСЛУГ (ОРГАНИЗАЦИИ)

            # region СОПОСТАВЛЕНИЯ УСЛУГ (ОРГАНИЗАЦИИ)
            titled_refs: dict = {}

            for nsi in ServiceTypeGisName.objects(__raw__={
                # WARN ServiceTypeGisName.provider = owner, а не doc.provider
                'provider': self.provider_id, 'closed': None,  # актуальные
                'reference_number': {'$in': [
                    # WARN кроме элементов справочника №2 ~ "КР на ОДН"
                    *ServiceTypeGisName.service_nsi(),  # справочники услуг
                    '50'  # общий справочник жилищных услуг
                ]},
            }).as_pymongo().order_by('reference_number'):
                title: str = nsi['gis_title']
                ref: tuple = (int(nsi['reference_number']),
                    nsi['position_number'])
                if title in titled_refs:  # одноименные элементы справочников?
                    dup: tuple = titled_refs[title]
                    raise PublicError("Элементы частных справочников (услуг)"
                        f" ГИС ЖКХ {ref[0]}.{ref[1]} и {dup[0]}.{dup[1]}"
                        f" имеют совпадающее наименование {sb(title)}")

                titled_refs[title] = ref

            self._provider_service_binds: dict = {}  # ObjectId:(reg_num,'code')

            for title, binds in ServiceTypeGisBind.mappings_of(
                self.provider_id  # WARN услуги УО сопоставляет РЦ
            ).items():  # 'title': (ServiceTypeId, 'code')
                if title in titled_refs:  # элемент (частного) справочника?
                    ref: tuple = titled_refs[title]
                elif title == 'Плата за содержание жилого помещения':
                    ref: tuple = (50, '1')  # WARN hardcode
                    self.log(warn="Предопределен элемент справочника жилищных"
                        f" услуг {ref[0]}.{ref[1]} ~ {sb(title)}")
                elif title == 'Взнос на капитальный ремонт':
                    ref: tuple = (50, '2')  # WARN hardcode
                    self.log(warn="Предопределен элемент справочника жилищных"
                        f" услуг {ref[0]}.{ref[1]} ~ {sb(title)}")
                else:  # элемент справочника не найден!
                    self.warning(f"Отсутствует сопоставленный с {len(binds)}"
                        f" услугами элемент справочника услуг {sb(title)}")
                    continue  # TODO пропускаем услуги без сопоставления?

                self.log(f"Элементу справочника {ref[0]}.{ref[1]}"
                    " сопоставлены услуги: " + ', '.join(
                        bind[1] or str(bind[0]) for bind in binds
                    ), is_spam=not self.DEBUG_SERVICES)
                for bind in binds:
                    self._provider_service_binds[bind[0]] = ref
            # endregion СОПОСТАВЛЕНИЯ УСЛУГ (ОРГАНИЗАЦИИ)

            # region УСЛУГИ ТАРИФНЫХ ПЛАНОВ
            tariff_plans: list = Accrual.objects(__raw__={
                '_id': {'$in': self.object_ids},
                'tariff_plan': {'$ne': None},  # WARN встречается null
            }).distinct('tariff_plan')  # аналог get_tariff_plan_ids

            self._tariff_service_types: dict = {}  # ServiceTypeId: ServiceType
            for tariff_plan_id in tariff_plans:
                tariff_services: list = get_tariff_plan_services(tariff_plan_id)
                if tariff_services:  # получены услуги тарифного плана?
                    self._tariff_service_types.update({
                        service['_id']: service for service in tariff_services
                    })  # добавляем услуги тарифного плана
                else:  # нет (услуг) тарифного плана?
                    self.warning("Имеются начисления по отсутствующему"
                        " или пустому (без услуг) тарифному плану")

            # тарифный план документа пуст при начислении по нескольким планам
            self.log("Услуги тарифных планов "
                + ', '.join(str(_id) for _id in tariff_plans) + ":\n\t"
                + '\n\t'.join(f"{sb(srv['title'])} ~ {srv.get('code') or _id}"
                    for _id, srv in self._tariff_service_types.items()),
             is_spam=not self.DEBUG_SERVICES)
            # endregion УСЛУГИ ТАРИФНЫХ ПЛАНОВ

        def _load_accounts_data(self):

            self._typed_tenant_guids: dict = {}  # 'AccountType': TenantId: GUID
            self._accounts_balance: dict = {}  # 'sector_code': TenantId: value

            for sector_code, accounts in get_accrual_accounts(
                *self.object_ids  # WARN идентификаторы начислений распределены
            ).items():
                account_type: str = get_account_type_by(sector_code)
                if account_type is None:  # неиспользуемое направление платежа?
                    raise PublicError("Начисления по направлению платежа"
                        f" {sb(sector_code)} не подлежат выгрузке в ГИС ЖКХ")
                else:
                    account_type_name: str = get_account_type_name(account_type)

                assert not self.object_type or \
                    account_type == self.object_type, \
                    "Тип ЛС не совпадает с установленным для операции"

                if account_type not in self._typed_tenant_guids:
                    account_guids: dict = \
                        self.owned_guids(account_type, *accounts)
                    if not account_guids:  # данные ГИС ЖКХ не загружены?
                        raise NoGUIDError("Отсутствуют идентификаторы"
                            f" ГИС ЖКХ {account_type_name}")
                    self._typed_tenant_guids[account_type] = account_guids

                # создаем экземпляр вспомогательного класса для получения сальдо
                utility = HouseAccountsBalance(self.house_id, accounts)
                # дата формирования документа (doc.date) > периода (month)
                # используется для нахождения сальдо по направлению платежа
                # сальдо одно для всех документов с датой и направлением платежа
                for doc_date in Accrual.objects(__raw__={
                    '_id': {'$in': self.object_ids},
                }).distinct('doc.date'):  # более одного документа за период?
                    # получаем сальдо ЛС по направлениям платежей на дату
                    date_balance: dict = utility.get_date_balance(
                        date_on=doc_date,  # Accrual.doc.date
                        sectors=[sector_code],  # $in
                        use_bank_date=False  # True-Payment.doc_date, False-date
                    )  # TODO turnovers - обороты (все операции)
                    if not date_balance:  # пустой словарь?
                        self.warning(f"Отсутствует сальдо {account_type_name}"
                            f" на {fmt_period(doc_date, with_day=True)}")
                        continue  # пропускаем направление платежа без сальдо
                    # ссылка на изменяемый словарь в общедоступном словаре
                    sector_balance: dict = \
                        self._accounts_balance.setdefault(sector_code, {})
                    for account_id, balance in date_balance.items():
                        # balance = { area_id, area_number, area_order, val }
                        balance_value: int = balance['val']  # сумма сальдо ЛС
                        if balance_value:  # может быть отрицательным!
                            sector_balance[account_id] = balance_value

                    joined_balance: str = ', '.join(f"{_id} = {to_rubles(val)}"
                        for _id, val in sector_balance.items()) or 'ОТСУТСТВУЮТ'
                    self.log(f"Загружено сальдо по {account_type_name}:\n\t"
                        + joined_balance)

        def _load_payments_data(self):

            # region БАНКОВСКИЕ РЕКВИЗИТЫ (ОРГАНИЗАЦИИ)
            self._bank_accounts: dict = {self.provider_id: get_bank_accounts(
                self.provider_id, house_id=self.house_id  # WARN единственный
            )}  # ProviderId: {'sector_code': ('БИК', 'Р/С')}
            if self.agent_id:  # получателем платежа может быть РЦ?
                self._bank_accounts[self.agent_id] = get_bank_accounts(
                    self.agent_id, house_id=self.house_id  # WARN единственный
                )  # добавляем банковские реквизиты РЦ
            if self.relation_id:  # получатель привязанная организация?
                self._bank_accounts[self.relation_id] = get_bank_accounts(
                    self.relation_id, house_id=self.house_id  # WARN единственный
                )  # добавляем банковские реквизиты привязанной организации
            if not self._bank_accounts[self.provider_id] and \
                    not self._bank_accounts.get(self.agent_id) and \
                    not self._bank_accounts.get(self.relation_id):
                raise NoDataError("Отсутствуют банковские реквизиты"
                    " оплаты оказываемых услуг организации")
            for provider_id, accounts in self._bank_accounts.items():
                self.log("Банковские реквизиты оплаты оказываемых"
                    f" организацией {provider_id} услуг:\n\t" + ('\n\t'.join(
                        f"{code} - БИК: {bic}, Р/С: {acc}"
                        for code, (bic, acc) in accounts.items()
                    ) or 'ОТСУТСТВУЮТ'))
            # endregion БАНКОВСКИЕ РЕКВИЗИТЫ (ОРГАНИЗАЦИИ)

            # region ПЛАТЕЖИ ЗА ПЕРИОД
            self._payments: dict = {}  # 'sector_code': AccountId: {value, date}
            provider_ids = [self.provider_id]
            if self.relation_id:
                provider_ids.append(self.relation_id)
            # Смотрим, когда был предыдущий документ начислений по дому
            previous_accrual_doc = AccrualDoc.objects(
                __raw__={
                    'house._id': self.house_id,
                    'date_from': {'$lt': self.period},
                    'is_deleted': {'$ne': True},
                    'status': 'ready',
                    'provider': {'$in': provider_ids},
                }
            ).order_by('-date_from').as_pymongo().first()
            # Смотрим на текущий документ начислений по дому
            current_accrual_doc = AccrualDoc.objects(
                __raw__={
                    'house._id': self.house_id,
                    # первое число месяца и года из запроса
                    'date_from': self.period,
                    'is_deleted': {'$ne': True},
                    'status': 'ready',
                    'provider': {'$in': provider_ids},
                }
            ).order_by('-date_from').as_pymongo().first()
            if not current_accrual_doc:
                raise NoDataError(f"Подлежащий выгрузке документ начислений"
                                  f" за период {self.period.strftime('%m.%Y')}"
                                  f" был открыт или не найден")
            # Ищем оплаты с даты предыдущего докнача по текущий
            for pay in Payment.objects(__raw__={
                'account.area.house._id': self.house_id,  # индекс
                'date': {
                    '$gte':
                        previous_accrual_doc.get('date')
                        if previous_accrual_doc
                        else datetime.today() - timedelta(days=30),
                    '$lt':
                        current_accrual_doc.get(
                            'date', datetime.today()
                        )
                },
                'is_deleted': {'$ne': True},
            }).only(
                'account.id', 'sector_code',
                'value', 'doc.date'  # date - дата оплаты
            ).as_pymongo():
                payment: dict = self._payments.setdefault(
                    pay['sector_code'],
                    {}
                ).setdefault(
                    pay['account']['_id'],
                    {'value': 0, 'date': None}  # по умолчанию
                )
                payment['value'] += pay['value']  # в копейках

                if payment.get('date') is None or \
                        pay['doc']['date'] > payment['date']:
                    payment['date'] = pay['doc']['date']  # дата поступления(?)

            joined_payments: str = '\n\t'.join(sb(SECTOR_NAMES.get(code))
                + f" оплачено {len(pays)} жильцами на сумму "
                + str(to_rubles(sum(pay['value'] for pay in pays.values())))
                    for code, pays in self._payments.items()) or 'ОТСУТСТВУЮТ'
            self.log(f"Загружены оплаты за {fmt_period(self.period)}"
                " по направлениям платежа:\n\t" + joined_payments)
            # endregion ПЛАТЕЖИ ЗА ПЕРИОД

        def _get_service_type(self, service_id: ObjectId) -> dict:

            if service_id not in self._tariff_service_types:
                service_type: dict = \
                    ServiceType.objects(id=service_id).as_pymongo().first()
                assert service_type is not None, \
                    f"Услуга с идентификатором {service_id} не найдена"
                service_type['caption'] = sb(service_type['title']) or \
                    (f"с кодом {service_type['code']}"
                        if service_type.get('code') else f"с ид. {service_id}")
                # WARN добавляем загруженную к услугам тарифного плана
                self._tariff_service_types[service_id] = service_type

                self.warning(f"Услуга {service_type['caption']}"
                    " отсутствует в тарифном плане организации")

            return self._tariff_service_types[service_id]

        def _payment_document(self, accrual: dict) -> Optional[dict]:

            def __code_or_title(_id) -> str:

                _service: dict = self._get_service_type(_id)

                return _service.get('code') or sb(_service['title']) \
                    if _service else str(_id)  # отсутствует в ТП

            def _payment_recalculation(reason_totals: dict) -> dict:
                """
                Сведения о перерасчетах

                :param reason_totals: "Причина": К оплате, руб.
                """
                assert reason_totals, "Причины и суммы перерасчетов отсутствуют"

                return {'recalculationReason':
                    '; '.join(REASON_NAMES.get(reason, reason)
                        for reason in reason_totals),  # ~ keys
                    'sum': to_rubles(sum(reason_totals.values())),
                }  # Основания перерасчетов и Сумма

            def _payment_info_details() -> dict:

                return dict(
                    # Сумма к оплате на расчетный счет
                    TotalPayableByPaymentInformation=to_rubles(accrual_value),
                    # НЕОБЯЗАТЕЛЬНЫЕ: Номер ЛС (иной ид. плательщика)
                    # TODO AccountNumber=None,
                    # Задолженность и переплата на начало расчетного периода,
                    # учтены поступившие до PaymentsTaken (включительно) платежи
                    # TODO DebtPreviousPeriodsOrAdvanceBillingPeriod=None,
                    # Итого к оплате c задолженностью/переплатой на Р/С
                    # TODO TotalPayableWithDebtAndAdvance=None,
                )

            def _penalties_wo_court_costs() -> list:

                penalties: dict = {}
                for penalty in accrual['penalties']:
                    period: str = fmt_period(penalty['period'])
                    # value - сумма пени за просрочку
                    # value_include - включенная в квитанцию пени
                    value = penalty['value_include'] + penalty['value_return']
                    if period not in penalties:
                        penalties[period] = value
                    else:
                        penalties[period] += value

                return [dict(
                    # WARN Выявлено дублирование услуги
                    #  e05e538b-83d2-4d69-86d6-902829cc90e3 (Пени).
                    #  Услуги указанные в платежном документе
                    #  с типом «Текущий» не должны повторяться;
                    #  в платежном документе с типом «Долговой»
                    #  комбинация «услуга» + «период задолженности»
                    #  должна быть уникальной.
                    ServiceType=nsiRef.common(329, 1),  # НСИ 329:
                    # 1-Пени, 2-Штрафы, 3-Гос. пошлины, 4-Судебные издержки
                    Cause=f"Пени за {', '.join(penalties)}"[:1000],  # max = 1K
                    TotalPayable=to_rubles(sum(penalties.values())),
                    # TODO orgPPAGUID  # Поставщик услуги (isRCAccount)
                    PaymentInformationKey=None,  # единые реквизиты
                )]  # TODO судебные издержки?

            def _determining(*service_method_s: str) -> str:
                """
                Способ определения объемов КУ

                :returns: (N)orm-Норматив, (M)etering device-ПУ, (O)ther-Иное
                """
                meter_methods = {
                    ConsumptionType.METER,  # ИПУ
                    # ConsumptionType.METER_WO,  # без счетчика
                    ConsumptionType.HOUSE_METER,  # ОДПУ
                    ConsumptionType.AVERAGE,  # среднее
                }
                norm_methods = {
                    ConsumptionType.NORMA,
                    ConsumptionType.NORMA_WOM,  # норматив без счетчика
                }
                # ConsumptionType.NOTHING  # отсутствует
                determining_methods: set = {'M' if method in meter_methods
                    else 'N' if method in norm_methods else 'O'  # 'nothing'
                for method in service_method_s}  # все методы группы услуг

                # для различных способов определения возвращаем 'O' - "Иное"
                return determining_methods.pop() \
                    if len(determining_methods) == 1 else 'O'

            def _consumption(collected: dict, is_public: bool = True) -> dict:
                """
                Объем затраченного коммунально ресурса (на ОДН)
                Количественное выражение предоставленных коммунальных услуг
                """
                return {  # атрибуты элемента запроса:
                    'type': 'O' if is_public else 'I',  # ОДН или индивидуальное
                    'determiningMethod': _determining(*collected['methods']),
                    # значение элемента запроса (text):
                    '_value_1': round_volume(collected['consumption']),
                }  # WARN без Volume

            def _totals(embedded_services: list) -> dict:

                from collections import defaultdict

                totals: dict = {
                    'tariff': 0, 'value': 0, 'result': 0,
                    'privileges': 0, 'recalculations': 0, 'shortfalls': 0,
                    'recalc': defaultdict(int),  # причина : сумма перерасчетов
                    'individual': {'consumption': 0.0, 'value': 0, 'result': 0,
                        'methods': set()},
                    'public': {'consumption': 0.0, 'value': 0, 'result': 0,
                        'methods': set()},
                    'included': defaultdict(list),  # в том числе (на ОДН)
                }  # инициализация итоговых значений

                for _embedded in embedded_services:  # ~ ServiceEmbedded
                    _total = _embedded['totals'] or {
                        # в totals ВСЕГДА есть все (4) значения (default = 0)
                        'recalculations': 0, 'privileges': 0, 'shortfalls': 0
                        # TODO privileges_info : int
                    }  # Суммарные данные по услуге
                    # Добавляем значения по тарифу и начислениям
                    totals['tariff'] += _embedded['tariff']  # Тариф
                    totals['value'] += _embedded['value']  # Начислено

                    # WARN ServiceEmbedded.result - НЕТ В СТАРЫХ ПД!
                    # Рассчитываем итоговый результат
                    service_result: int = (_embedded['result']
                        if _embedded.get('result') is not None
                        else _embedded['value'] + _total['recalculations']
                        + _total['privileges'] + _total['shortfalls'])
                    totals['result'] += service_result  # Итого к оплате, копеек

                    # Добавляем перерасчеты, корректировки и льготы
                    totals['recalculations'] += _total['recalculations']  # Перерасчеты
                    totals['shortfalls'] += _total['shortfalls']  # Корректировки
                    totals['privileges'] += _total['privileges']  # Льготы WARN ОТРИЦАТЕЛЬНЫЕ

                    # Проверяем наличие ручных перерасчетов
                    manual_found = any(
                        calc['reason'] == RecalculationReasonType.MANUAL
                        for calc in _embedded['recalculations']
                    )
                    # Обновляем причину перерасчетов, если найден ручной и есть комментарий
                    if manual_found and _embedded.get('comment'):
                        for calc in _embedded['recalculations']:
                            calc['reason'] = _embedded['comment']

                    # Обновляем значения перерасчетов, аккумулируем по каждой услуге
                    for calc in _embedded['recalculations']:
                        totals['recalc'][calc['reason']] += calc['value']

                    # После цикла проверяем, что сумма перерасчетов совпадает
                    assert totals['recalculations'] == sum(
                        totals['recalc'].values()), \
                        "Сумма перерасчетов по услугам не совпадает по причинам"

                    _service_id = _embedded['service_type']  # : ObjectId
                    # WARN отсутствующие в ТП услуги добавляются
                    _service: dict = self._get_service_type(_service_id)
                    _service_code = _service.get('code')  # может отсутствовать!

                    if not _service_code:  # услуга без кода?
                        continue  # дополнительная услуга?
                    elif not is_municipal_service(_service_code):  # НЕ КУ?
                        continue  # жилищная или дополнительная услуга!
                    elif is_individual_service(_service_code):
                        _split = totals['individual']  # инд. потребление
                        _split['consumption'] += _embedded['consumption']
                    elif is_public_service(_service_code):
                        _split = totals['public']  # потребление при СОИ
                        if is_heating(_service_code):  # WARN только Отопление
                            _split['consumption'] += _embedded['consumption']
                        # группируем по коду (НЕ главного) комм. ресурса (НСИ 2)
                        _nsi_code: int = resource_nsi_code_of(_service_code)
                        _included: dict = totals['included']
                        _included[_nsi_code].append(_embedded)
                    else:  # целевое потребление не определено!
                        self.warning("Целевое потребление коммунальной услуги"
                            f" {sb(_service['title'])} не определено")
                        continue  # пропускаем услугу

                    # вложенный словарь передается по ссылке и дополняется
                    _split['value'] += _embedded['value']  # Начислено
                    _split['result'] += service_result  # Итого к оплате

                    _method: str = _embedded.get('method')  # Метод расчета
                    if (is_waste_water(_service_code) and  # Водоотведение
                            _method != ConsumptionType.METER_WO):  # без ПУ?
                        self.log(warn="Метод определения затраченного объема"
                            ' "Водоотведения" переопределен как "Без счетчика"')
                        _split['methods'].add(ConsumptionType.METER_WO)  # не ПУ
                    else:  # не водоотведение или корректный метод определения!
                        _split['methods'].add(_method)

                return totals

            def _cr_charge(total) -> dict:

                capital_repair_charge = dict(
                    # Размер взноса на кв.м, руб.
                    Contribution=to_rubles(total['tariff']),  # 17.2
                    # Всего начислено за расчетный период, руб.
                    AccountingPeriodTotal=to_rubles(total['value']),
                    # Перерасчеты, корректировки (руб)
                    MoneyRecalculation=to_rubles(  # с корректировками!
                        total['recalculations'] + total['shortfalls']),
                    # Льготы, субсидии, скидки (руб)
                    MoneyDiscount=to_rubles(abs(total['privileges'])),
                    # Итого к оплате за расчетный период, руб.
                    TotalPayable=to_rubles(total['result']),
                    # CalcExplanation  # Порядок расчетов?
                    PaymentInformationKey=None,  # единые реквизиты
                )
                # TODO orgPPAGUID  # Поставщик услуги

                if total['recalculations']:  # Перерасчеты (БЕЗ корректировок)?
                    capital_repair_charge['PaymentRecalculation'] = \
                        _payment_recalculation(total['recalc'])

                return capital_repair_charge

            def _service_pd(total) -> dict:
                """Базовая (общая) часть ПД"""
                service_pd = dict(  # общая часть всех видов услуг
                    # ЖУ (НСИ 50), КУ (НСИ 3), Гл. КУ (НСИ 51), ДУ (НСИ 1):
                    ServiceType=self._service_nsi_ref,  # nsiRef.as_req
                    Rate=to_rubles(total['tariff']),
                    # Всего начислено за расчетный период, руб. ~ п. 19:
                    AccountingPeriodTotal=to_rubles(total['value']),
                    # Итого к оплате за расчетный период, руб. ~ п. 22:
                    TotalPayable=to_rubles(total['result']),
                    # CalcExplanation  # Порядок расчетов?
                    PaymentInformationKey=None,  # WARN None - единые реквизиты
                    # TODO orgPPAGUID - Поставщик услуги
                )

                if total['recalculations'] or total['shortfalls'] \
                        or total['privileges']:  # имеются перерасчеты, льготы?
                    service_pd['ServiceCharge'] = dict(
                        MoneyRecalculation=to_rubles(
                            total['recalculations'] + total['shortfalls']
                        ),  # Перерасчеты, корректировки (руб) ~ п. 20
                        MoneyDiscount=to_rubles(
                            abs(total['privileges'])
                        ),  # Льготы, субсидии, скидки (руб) ~ п. 21
                    )
                if total['recalculations']:  # имеются перерасчеты?
                    service_pd['PaymentRecalculation'] = _payment_recalculation(
                        total['recalc']
                    )  # Сведения о перерасчетах (доначислении +, уменьшении -)

                return service_pd

            def _municipal_service(total) -> dict:
                """Главная коммунальная услуга с объемом потребления"""
                _ind = total['individual']
                _pub = total['public']

                _iv = to_rubles(_ind['value']) if _ind['value'] else None
                _ir = to_rubles(_ind['result']) if _ind['result'] else None
                _pv = to_rubles(_pub['value']) if _pub['value'] else None
                _pr = to_rubles(_pub['result']) if _pub['result'] else None

                municipal_service = dict(
                    **_service_pd(total),
                    AmountOfPaymentMunicipalServiceIndividualConsumption=_iv,
                    MunicipalServiceIndividualConsumptionPayable=_ir,
                    AmountOfPaymentMunicipalServiceCommunalConsumption=_pv,
                    MunicipalServiceCommunalConsumptionPayable=_pr,
                    # TODO ServiceInformation - Справочная информация
                    # TODO MultiplyingFactor - Повышающий коэффициент (кроме ВО)
                    # TODO PiecemealPayment - Рассрочка
                )

                _volume: list = []  # Объем потребления
                if _ind['consumption']:
                    _volume.append(_consumption(_ind, is_public=False))
                if _pub['consumption']:
                    _volume.append(_consumption(_pub, is_public=True))
                if _volume:  # Максимум 2: ['I', 'O']
                    municipal_service['Consumption'] = {'Volume': _volume}

                return municipal_service

            def _additional_service(total) -> dict:
                """
                Вид дополнительной услуги
                """
                additional_service: dict = _service_pd(total)

                # TODO additional_service['Consumption'] - Объем услуг?

                return additional_service

            def _service_charge(total) -> dict:
                """
                Перерасчеты, льготы, субсидии
                """
                assert total['recalculations'] or \
                    total['privileges'] or total['shortfalls'], \
                    "Отсутствуют перерасчеты, льготы, субсидии"

                return dict(
                    # Перерасчеты, корректировки, руб.
                    MoneyRecalculation=to_rubles(
                        total['recalculations'] + total['shortfalls']
                    ),
                    # Льготы, субсидии, скидки, руб.
                    MoneyDiscount=to_rubles(abs(total['privileges'])),
                )

            def _general_resource(res_code: str, resources: list) -> dict:
                """
                Коммунальный ресурс (главный), потребляемый на ОДН в МКД
                """
                _total = _totals(resources)
                _public = _total['public']

                _pub_val = to_rubles(_public['value'])  # Плата за КР на ОДН
                _value = to_rubles(_total['value'])  # Начислено

                _resource_ref: dict = \
                    nsiRef.private(337, res_code, self.provider_id)  # ~ as_req
                if _resource_ref is None:
                    raise NoGUIDError(f"Элемент с кодом {res_code}"
                        " частного справочника №337 (ОДН) не загружен")

                general_resource = dict(
                    ServiceType=_resource_ref,  # Главный комм. ресурс (НСИ 337)
                    Rate=to_rubles(_total['tariff']),
                    # Начислено (без перерасчетов и льгот), руб.:
                    AccountingPeriodTotal=_value,
                    # К оплате за КР потребленный на ОДН, руб.:
                    MunicipalServiceCommunalConsumptionPayable=_value,
                    # Размер платы за КР на ОДН: WARN НЕ ОБРАБАТЫВАЕТСЯ ГИС ЖКХ!
                    AmountOfPaymentMunicipalServiceCommunalConsumption=_pub_val,
                    # Итого к оплате за расчетный период, руб.:
                    TotalPayable=to_rubles(_total['result']),
                    # WARN determiningMethod гл. КР обязателен при ЕИ КР не 'м2'
                    Consumption={'Volume': _consumption(_public)},
                )
                # TODO orgPPAGUID - Поставщик ресурса
                if _total['privileges'] or _total['recalculations'] or \
                        _total['shortfalls']:  # Перерасчеты, льготы, субсидии?
                    general_resource['ServiceCharge'] = _service_charge(_total)
                if _total['recalculations']:  # Перерасчеты?
                    general_resource['PaymentRecalculation'] = \
                        _payment_recalculation(_total['recalc'])

                return general_resource

            def _municipal_resource(res_code: int, services: list) -> dict:
                """
                Комм. ресурсы, потребляемые при использовании и СОИ в МКД
                """
                _total = _totals(services)
                _public = _total['public']

                _pub_val = to_rubles(_public['value'])  # Плата за КР на ОДН
                _value = to_rubles(_total['value'])  # Начислено за услугу

                municipal_resource = dict(
                    ServiceType=nsiRef.common(2, res_code),  # Вид КР (НСИ 2)
                    # Всего начислено за расчетный период, руб.:
                    AccountingPeriodTotal=_value,
                    # К оплате за КР на ОДН, руб.:
                    MunicipalServiceCommunalConsumptionPayable=_value,
                    # Размер платы за КР на ОДН: WARN НЕ ОБРАБАТЫВАЕТСЯ ГИС ЖКХ!
                    AmountOfPaymentMunicipalServiceCommunalConsumption=_pub_val,
                    # Итого к оплате за расчетный период, руб.:
                    TotalPayable=to_rubles(_total['result']),  # Рез. начисления
                    Unit='D',  # из справочника TODO 'S'-кв.м, None-по умолчанию
                )
                # TODO orgPPAGUID - Поставщик услуги
                municipal_resource['GeneralMunicipalResource'] = [
                    _general_resource(code, resources) for code, resources in
                    general_resources.items() if int(code[:1]) == res_code  #3.1
                ] or None  # допускается наличие "пустых" вложенных элементов
                # WARN Rate не обязателен если заполнен GeneralMunicipalResource
                if not municipal_resource['GeneralMunicipalResource']:
                    # Тариф ~ Размер платы или взноса на кв.м, руб.
                    municipal_resource['Rate'] = to_rubles(_total['tariff'])
                if _public['consumption']:  # КР на ОДН?
                    municipal_resource['Consumption'] = \
                        {'Volume': _consumption(_public)}
                if _total['privileges'] or _total['recalculations'] or \
                        _total['shortfalls']:  # Перерасчеты, льготы, субсидии?
                    municipal_resource['ServiceCharge'] = \
                        _service_charge(_total)
                if _total['recalculations']:  # Сведения о перерасчетах?
                    municipal_resource['PaymentRecalculation'] = \
                        _payment_recalculation(_total['recalc'])

                return municipal_resource

            def _housing_service(total) -> dict:
                """
                Жилищная услуга

                Если домом управляет УК, ТСЖ, Ж(С или иной)К,
                то коммунальные ресурсы на ОДН относятся к ЖУ!
                """
                municipal_resources = [_municipal_resource(code, services)
                    for code, services in total['included'].items()] or None

                return dict(**_service_pd(total),
                    MunicipalResource=municipal_resources)

            def _group_service(total) -> Optional[dict]:
                """
                TODO Вид комм. услуги (НСИ 3), содержащей главные комм. услуги

                В блоке предоставляется возможность указать группирующие виды
                коммунальных услуг, с разбивкой на главные коммунальные услуги.
                """
                return None

            def _result(accrual_service: dict) -> float:

                if accrual_service.get('result'):
                    return accrual_service['result']

                service_totals: dict = accrual_service['totals']
                return accrual_service['value'] \
                    + service_totals['recalculations'] \
                    + service_totals['privileges'] \
                    + service_totals['shortfalls']

            accrual_id: ObjectId = accrual['_id']  # ~ PaymentDocumentNumber
            pd_guid: GUID = self._mapped_guids[accrual_id]  # AccrualId: GUID

            if self._is_skippable(pd_guid):  # не обновлять?
                self.log(warn="Не подлежат (повторной) выгрузке в ГИС ЖКХ"
                    f" данные ПД №{accrual_id} с уникальным №{pd_guid.unique}")
                return  # пропускаем выгруженный (с уникальным номером) ПД

            # account_area: dict = accrual['account']['area']  # помещение ЛС
            # area_number: str = account_area['str_number']  # номер помещения
            pd_guid.desc = f"№{accrual_id}"  # номер в качестве описания

            if accrual['doc']['status'] not in CONDUCTED_STATUSES:  # в работе?
                self.failure(pd_guid, "Начисление документа не проведено")
                return  # пропускаем незакрытое начисление

            owner_id: ObjectId = accrual['owner']  # получатель платежа
            # TODO orgPPAGUID=self.guid_of('Provider', owner_id)

            sector_code: str = accrual['sector_code']  # Направление начислений
            sector_name: str = SECTOR_NAMES.get(sector_code)  # "Квартплата"
            account_type: str = get_account_type_by(sector_code)  # тип ЛС
            if account_type is None:  # неиспользуемое направление платежа?
                self.failure(pd_guid, "Направление платежа"
                    f" {sb(sector_name)} не подлежит выгрузке")
                return  # пропускаем ПД для ЛС с невыясненным типом

            is_capital_repair: bool = \
                sector_code == AccrualsSectorType.CAPITAL_REPAIR  # Капремонт?

            # region БАНКОВСКИЕ РЕКВИЗИТЫ (НАПРАВЛЕНИЯ ПЛАТЕЖА)
            if owner_id not in self._bank_accounts:
                self.failure(pd_guid,
                    "Банковские реквизиты получателя платежа не найдены")
                return  # пропускаем ПД без реквизитов получателя платежа
            elif sector_code not in self._bank_accounts[owner_id]:
                self.failure(pd_guid,
                    "Банковские реквизиты направления платежа не найдены")
                return  # пропускаем ПД без реквизитов направления платежа
            else:  # банковские реквизиты организации для направления платежа!
                bic, acc = self._bank_accounts[owner_id][sector_code]

            if (bic, acc) in self._payment_information:  # уже встречался?
                payment_info_key = self._payment_information[(bic, acc)]
            else:  # еще не встречавшийся банковский счет!
                payment_info_key = self.generated_guid  # ~ TransportGUID
                self._payment_information[(bic, acc)] = payment_info_key
            # endregion БАНКОВСКИЕ РЕКВИЗИТЫ (НАПРАВЛЕНИЯ ПЛАТЕЖА)

            # region ПЛАТЕЖНЫЙ ДОКУМЕНТ (ОБЩАЯ ЧАСТЬ)
            account_id: ObjectId = accrual['account']['_id']

            # находим ЛС определенного типа среди идентификаторов ГИС ЖКХ
            account_guid: GUID = \
                self._typed_tenant_guids[account_type].get(account_id)  # None?
            if not account_guid:  # идентификатор ГИС ЖКХ не загружен?
                self.failure(pd_guid, "Отсутствует идентификатор ГИС ЖКХ ЛС")
                return  # пропускаем ПД без идентификатора ЛС

            accrual_value: int = accrual['value']  # Сумма начисленного

            # сальдо (недо-/переплата) по лицевому счету - может отсутствовать
            account_balance: int = \
                self._accounts_balance.get(sector_code, {}).get(account_id, 0)

            # PaymentDocumentID (присвоенный ГИС ЖКХ ид. ПД): 90НО452262-01-1011
            # в случае повторной выгрузки без ID вернется ошибка о существовании
            payment_document = dict(  # WARN НЕ as_req
                TransportGUID=pd_guid.transport,  # : UUID
                AccountGuid=account_guid.gis,  # Идентификатор ЛС
                PaymentDocumentNumber=str(accrual_id),  # Номер ПД
                AdvanceBllingPeriod=to_rubles(account_balance, False),  # Аванс
                DebtPreviousPeriods=to_rubles(account_balance, True),  # Долг
                TotalPayableByPD=to_rubles(accrual_value),  # Начислено
                TotalPayableByPDWithDebtAndAdvance=to_rubles(
                    accrual_value + account_balance, True  # положительное или 0
                ),  # Итого по всему ПД с учетом задолженности и переплаты
                PaymentsTaken=accrual['doc']['date'].day,  # Учтены платежи до
                # TODO AdditionalInformation,  # Доп. информация
                # TODO totalPiecemealPaymentSum  # С учетом рассрочки и %%
                # TODO ComponentsOfCost  # Составляющие стоимости ЭЭ
                # TODO LimitIndex  # Макс. индекс изм. платы за КУ в МО
                # TODO SubsidiesCompensationSocialSupport  # Соц. поддержка
            )
            if (not pd_guid.deleted  # WARN Отзыв ПД невозможен, ПД уже отозван.
                    and not pd_guid.error):  # была ошибка в данных?
                payment_document['PaymentDocumentID'] = pd_guid.unique  # : str
            # Платежные реквизиты можно указать только в целом на весь платежный
            # документ или только на каждую услугу в отдельности. Не допускается
            # частичное заполнение платёжных реквизитов для отдельных услуг.
            # payment_document['DetailsPaymentInformation'] = [{
            #     'PaymentInformationKey': payment_info_key,
            #     **_payment_info_details(),  # начисления по нескольким Р/С
            # }]
            payment_document['PaymentInformationKey'] = payment_info_key

            sector_payments: dict = self._payments.get(sector_code)
            payment: dict = sector_payments.get(account_id) \
                if sector_payments else None
            if payment is None:  # платежей не было?
                self.log(warn=f"Отсутствуют оплаты за {fmt_period(self.period)}"
                f" ЛС {account_id} по направлению {sb(sector_name)}")
            else:
                payment_document['PaidCash'] = to_rubles(payment['value'])  # ₽
                payment_document['DateOfLastReceivedPayment'] = payment['date']

            # TODO PaymentInformationDetails - Детализация начислений по Р/С
            # endregion ПЛАТЕЖНЫЙ ДОКУМЕНТ (ОБЩАЯ ЧАСТЬ)

            # TODO Долговой ПД: только ChargeDebt или CapitalRepairDebt

            # region ГРУППИРОВКА УСЛУГ ПД
            grouped: dict = {}  # (int, str) : [ ServiceEmbedded ]
            general_resources: dict = {}  # (в том числе) КР на ОДН
            recalculations: dict = {}  # Сведения о перерасчетах (Капремонт)

            for embedded in accrual['services']:  # ~ ServiceEmbedded
                service_id: ObjectId = embedded['service_type']

                # проверяем наличие услуги в тарифном плане ПД
                service: dict = self._get_service_type(service_id)
                service_code: str = service.get('code')  # код услуги

                # получаем номер (int) справочника услуг и код (str) элемента
                ref: tuple = self._provider_service_binds.get(service_id)
                if not ref:  # элемент справочника не загружен из ГИС ЖКХ?
                    self.failure(pd_guid, "Получены начисления по услуге"
                        f" {service['caption']} без сопоставления")
                    return  # пропускаем ПД с услугой без сопоставления
                elif ref not in self._provider_nsi_references:
                    # данные ГИС ЖКХ элемента справочника (услуги) не загружены?
                    self.failure(pd_guid, "Не загружены данные ГИС ЖКХ"
                        f" элемента справочника {ref[0]}.{ref[1]}")
                    return  # пропускаем ПД без идентификатора услуги
                elif ref[0] == 2:  # услуга сопоставлена с ресурсом?
                    self.failure(pd_guid, f"Услуга {service['caption']} не"
                        " сопоставлена с «Коммунальной» или «Ресурсом на ОДН»")
                    return  # пропускаем ПД с сопоставленной с ресурсом услугой
                elif is_capital_repair:  # начислено за капитальный ремонт?
                    if ref != (50, '2'):  # услуга сопоставлена не с КР?
                        recalculations[service['title']] = _result(embedded)
                        continue  # WARN услуги в перерасчетах не группируются
                elif ref == (50, '2'):  # капремонт?
                    if _result(embedded) == 0:  # без начислений?
                        self.warning("Услуга «Капитальный ремонт» без"
                            " начислений удалена из «Коммунальных услуг»")
                        continue  # WARN пропускаем КР без начислений
                    # self.failure(pd_guid, "Услуга «Капитальный ремонт» должна"
                    #     " выгружаться в отдельном ПД или как «Дополнительная»")
                    # return  # пропускаем ПД с неверно сопоставленным КР
                elif ref == (50, '1'):  # Содержание жилого помещения?
                    if service_code and is_public_service(service_code):  # ОДН?
                        if is_heating(service_code):  # Отопление?
                            self.failure(pd_guid, f"Услуга {service['caption']}"
                                " не сопоставлена с «Отоплением»")
                            return  # пропускаем ПД с услугой на ОДН в ЖУ
                        # else WARN не "Отопление" может быть в "Жилищных"
                        self.warning(f"Услуга {service['caption']} не"
                            " сопоставлена с «Коммунальным ресурсом на ОДН»")
                elif ref[0] == 337:  # TODO только для УК, ТСЖ, ЖСК
                    general_resources.setdefault(ref[1], []).append(embedded)
                    self.log(warn="Сопоставленная с ресурсом на ОДН"
                        f" 337.{ref[1]} услуга {service['caption']}"
                        " добавлена к «Жилищным»")
                    ref = (50, '1')  # Плата за содержание жилого помещения

                # группируем начисления за услуги по элементам справочников
                grouped.setdefault(ref, []).append(embedded)

            self.log(f"Сгруппированные услуги ПД №{accrual_id}:\n\t"
                + '\n\t'.join(f"{ref[0]}.{ref[1]}: " + ', '.join(
                    __code_or_title(emb['service_type']) for emb in group
                ) for ref, group in grouped.items()),
                is_spam=not self.DEBUG_SERVICES)
            if general_resources:  # имеются начисления за ресурсы на ОДН?
                self.log(f"Сгруппированные затраченные ресурсы на ОДН:\n\t"
                    + '\n\t'.join(f"337.{code}: " + ', '.join(
                        __code_or_title(res['service_type']) for res in grp
                    ) for code, grp in general_resources.items()),
                    is_spam=not self.DEBUG_SERVICES)
            if recalculations:  # имеются сведения о перерасчетах КР?
                self.log(f"Сведения о перерасчетах по капремонту:\n\t"
                    + '\n\t'.join(f"{title} = {to_rubles(result)} руб."
                        for title, result in recalculations.items()),
                    is_spam=not self.DEBUG_SERVICES)
            # endregion ГРУППИРОВКА УСЛУГ ПД

            # TODO обработка услуг с другими ACCRUAL_SECTOR_TYPE_CHOICES?

            # region КАПИТАЛЬНЫЙ РЕМОНТ (CapitalRepairCharge)
            # отделяем услугу "капитальный ремонт"
            cr_services: list = grouped.pop((50, '2'), None)

            # отдельное направление на капитальный ремонт?
            if is_capital_repair:
                # WARN в ПД за КР могут быть другие услуги (Банковский сбор)
                if not cr_services:  # ни одна услуга не сопоставлена с КР?
                    self.failure(pd_guid, "Нет сопоставленной со"
                        " «Взносом на капитальный ремонт» услуги")
                    return  # пропускаем с услугой без сопоставления
                cr_total: dict = _totals(cr_services)  # сумма начислений по КР
                self.log(f"В ПД №{accrual_id} по направлению платежа"
                    f" «Капремонт» начислено {to_rubles(cr_total['value'])}"
                    f" (к оплате: {to_rubles(cr_total['result'])}) руб.",
                    is_spam=not self.DEBUG_SERVICES)

                payment_document['CapitalRepairCharge'] = _cr_charge(cr_total)

            # капитальный ремонт внутри основной квитанции?
            elif cr_services:
                cr_total: dict = _totals(cr_services)  # сумма начислений по КР
                self.log(f"В ПД №{accrual_id} по направлению платежа"
                         f" «Капремонт» начислено {to_rubles(cr_total['value'])}"
                         f" (к оплате: {to_rubles(cr_total['result'])}) руб.",
                         is_spam=not self.DEBUG_SERVICES)
                payment_document['CapitalRepairCharge'] = _cr_charge(cr_total)
                # TODO CapitalRepairYearCharge  # Начислено за 12 месяцев
            # endregion КАПИТАЛЬНЫЙ РЕМОНТ (CapitalRepairCharge)

            # region ПЕНИ (PenaltiesAndCourtCosts)
            if not accrual['totals'].get('penalties'):  # нет начисленной пени?
                pass
            elif accrual['penalties']:  # имеется конкретизация пени?
                # Поле «Итого к оплате по неустойкам и судебным издержкам»
                # может быть заполнено только, если в ПД передана информация
                # о неустойках и судебных расходах.
                payment_document['TotalByPenaltiesAndCourtCosts'] = \
                    to_rubles(accrual['totals']['penalties'])  # : Decimal
                payment_document['PenaltiesAndCourtCosts'] = \
                    _penalties_wo_court_costs()  # Множественное
                self.log(f"Платежный документ {accrual_id} включает"
                    f" {len(accrual['penalties'])} начислений пени в размере "
                    f"{payment_document['TotalByPenaltiesAndCourtCosts']} руб.",
                    is_spam=not self.DEBUG_SERVICES)
            else:  # конкретизации начисленных пени нет!
                self.warning("Не подлежат выгрузке неконкретизированные"
                    f" пени платежного документа №{accrual_id}")
            # endregion ПЕНИ (PenaltiesAndCourtCosts)

            # TODO Insurance - Страховые продукты

            # region НАЧИСЛЕНИЯ ПО УСЛУГАМ (ChargeInfo)
            charges = []  # начисления по услугам (множественное)
            charge_total: int = 0

            for ref, grouped_services in grouped.items():
                reference_number: int = ref[0]  # номер справочника

                self._service_nsi_ref: dict = \
                    self._provider_nsi_references.get(ref)  # nsiRef.as_req
                if self._service_nsi_ref is None:  # элемент отсутствует?
                    raise NoGUIDError("Идентификатор элемента справочника"
                        f" №{ref[0]}.{ref[1]} не загружен из ГИС ЖКХ")

                gr_total: dict = _totals(grouped_services)  # ~ ServiceTotals
                charge_total += gr_total['value']

                self.log(f"За {sb(self._service_nsi_ref.get('Name'))}"
                    f" по тарифу {to_rubles(gr_total['tariff'])} руб."
                    " с расходом " + str(gr_total['individual']['consumption']
                        or gr_total['public']['consumption'])
                    + f" начислено {to_rubles(gr_total['value'])} руб."
                    + f", итого {to_rubles(gr_total['result'])} руб.",
                    is_spam=not self.DEBUG_SERVICES)

                charge_info = dict(
                    # Главная комм. услуга с объемом потребления (НСИ 51)
                    MunicipalService=_municipal_service(gr_total)
                    if reference_number in {51} else None,
                    # Дополнительная услуга (НСИ 1)
                    AdditionalService=_additional_service(gr_total)
                    if reference_number in {1} else None,
                    # Жилищная услуга (НСИ 50)
                    HousingService=_housing_service(gr_total)
                    # в том числе КР (НСИ 2 и 337) на ОДН в МКД
                    if reference_number in {50, 2, 337} else None,
                    # Комм. услуга (НСИ 3), содержащая гл. комм. услуги
                    GroupMunicipalService=_group_service(gr_total)
                    if reference_number in {3} else None
                )
                charges.append(charge_info)

            # Итого к оплате за расчетный период (TotalPayableByChargeInfo)
            # может передаваться только в составе текущего платежного документа,
            # в котором указаны начисления хотя бы по одной услуге:
            # ChargeInfo, CapitalRepairCharge/CapitalRepairYearCharge, Insurance
            if not charges and not is_capital_repair:
                self.failure(pd_guid,
                    "Начисления по услугам отсутствуют ~ Долговой ПД?")
                return

            payment_document['ChargeInfo'] = charges  # Обязательное
            payment_document['TotalPayableByChargeInfo'] = \
                to_rubles(charge_total)
            # endregion НАЧИСЛЕНИЯ ПО УСЛУГАМ (ChargeInfo)

            return payment_document

        def _compose(self) -> dict:
            """importPaymentDocumentRequest"""
            accruals: list = Accrual.objects(__raw__={
                '_id': {'$in': self.object_ids},
            }).only(
                'owner', 'account', 'doc', 'sector_code', 'month',
                'value', 'totals', 'services', 'penalties',
            ).as_pymongo()  # загружаем данные платежных документов

            # WARN сопоставляем идентификаторы начислений операции
            self.mapped_guids(GisObjectType.ACCRUAL, *self.object_ids)

            self._payment_information: dict = {}  # заполняются в _produce

            payment_documents: list = \
                self._produce(self._payment_document, accruals)

            # TODO PaymentProviderInformation - только для isRCAccount
            payment_information: list = [{
                'TransportGUID': uuid,  # : UUID
                'BankBIK': bic_acc[0], 'operatingAccountNumber': bic_acc[1],
            } for bic_acc, uuid in self._payment_information.items()]

            return dict(PaymentDocument=payment_documents,  # Множественное
                PaymentInformation=payment_information)  # Множественное

        def _request(self) -> dict:

            self._load_request_data()  # загружаем необходимые данные

            self._load_accounts_data()  # загружаем данные лицевых счетов

            self._load_payments_data()  # загружаем данные платежей

            request_data: dict = super()._request()  # копия данных запроса

            request_data.update({
                'Month': self.period.month, 'Year': self.period.year,
            })  # добавляем в запрос месяц и год (периода) начислений

            if 'ConfirmAmountsCorrect' not in request_data:  # INT008165:
                # Выявлено расхождение...с автоматически рассчитанными в ГИС ЖКХ
                request_data['ConfirmAmountsCorrect'] = True  # Фиксированное

            return request_data

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if 'Month' in request_data or 'Year' in request_data:  # в запросе?
                return False
            elif 'period' not in request_data:  # не определен для операции?
                return False

            return True

        def _preload(self):

            # TODO Nsi.load_provider_refs - другой формат данных

            accrual_account_ids: list = Accrual.objects(__raw__={
                '_id': {'$in': self.object_ids},  # WARN не распределены
            }).distinct('account._id')

            # загружаются идентификаторы ЛС всех типов (КУ, КР,...)
            HouseManagement.load_account_guids(self, *accrual_account_ids)

        def prepare(self, *accrual_id_s: ObjectId, **request_data):
            """
            Подготовка к выгрузке начислений по направлению платежа
            """
            prepared: dict = {}  # 'AccountType': [ AccrualId,... ]

            for accrual in Accrual.objects(__raw__={
                '_id': {'$in': accrual_id_s},
            }).only('sector_code').as_pymongo():
                # WARN одному типу соответствуют несколько направлений платежа
                account_type: str = get_account_type_by(accrual['sector_code'])
                if account_type:  # типа ЛС для направления платежа?
                    prepared.setdefault(account_type, []).append(accrual['_id'])
                else:  # тип ЛС не определен?
                    self.warning("Пропущены начисления по направлению платежа "
                        + sb(SECTOR_NAMES.get(accrual['sector_code']),
                            f"с кодом {accrual['sector_code']}"))

            for account_type, accrual_ids in prepared.items():
                request_data['object_type'] = account_type  # WARN извлекается
                super().prepare(*accrual_ids, **request_data)  # period

        def periodic(self, period: datetime = None):
            """Выгрузить в ГИС ЖКХ документы начислений за период"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                # accrual_doc_id: list = AccrualDoc.objects(__raw__={
                #     'sector_binds.provider': self.provider_id,
                #     'status': AccrualDocumentStatus.READY,
                #     'date_from': period,
                # }).scalar('id').as_pymongo()  # TODO документы разных видов

                accrual_ids: list = self.period_accruals(period)
                if not accrual_ids:  # нет проведенных начислений за период?
                    raise NoDataError("Отсутствуют подлежащие выгрузке"
                        f" в ГИС ЖКХ начисления за {fmt_period(period)}")

            self.log(info=f"Выгружаются {len(accrual_ids)} выставленных"
                f" {self.doc_provider_name} начислений за {fmt_period(period)}")

            self(*accrual_ids, period=period)  # WARN извлекается

        def document(self, accrual_doc_id: ObjectId):
            """Выгрузить в ГИС ЖКХ начисления документа"""
            with self.load_context as context:  # WARN сохраняем в случае ошибки
                doc: dict = AccrualDoc.objects(__raw__={
                    '_id': accrual_doc_id,  # индивидуальная проверка начислений
                }).only(
                    'provider', 'status', 'date_from', 'date', 'description'
                ).as_pymongo().first()  # или None
                if doc is None:
                    raise NoDataError("Подлежащий выгрузке документ начислений"
                        f" с идентификатором {accrual_doc_id} не найден")

                period: datetime = doc['date_from']  # первое число месяца
                description: str = sb(doc.get('description'),
                    f"Начисления за {fmt_period(period)}")

                if doc['provider'] not in {self.doc_provider_id, self.relation_id}:  # не provider_id
                    raise PublicError(f"Подлежащий выгрузке в ГИС ЖКХ документ"
                        f" {description} выставлен не {self.doc_provider_name}")
                elif doc['status'] not in CONDUCTED_STATUSES:  # не проведен?
                    status: str = STATUS_NAMES.get(doc['status'], doc['status'])
                    raise PublicError("Подлежащий выгрузке в ГИС ЖКХ документ"
                        f" {description} в данный момент {sb(status)}")

                accrual_ids: list = Accrual.objects(__raw__={
                    'doc._id': doc['_id'], 'is_deleted': {'$ne': True},
                    # WARN 'doc.status' проверяется при формировании запроса
                }).distinct('id')
                if not accrual_ids:
                    raise NoDataError("Отсутствуют подлежащие выгрузке"
                        f" в ГИС ЖКХ начисления документа {description}")

            if context.exception:  # ошибка плановой операции?
                return  # завершаем выполнение

            self.log(info=f"Выгружаются {len(accrual_ids)} начислений"
                f" проведенного документа за {fmt_period(period)}")

            self(*accrual_ids, period=period)  # WARN извлекается

    class withdrawPaymentDocumentData(ImportPaymentDocumentOperation):
        """Отозвать платежные документы"""
        WSDL_NAME = 'importPaymentDocumentData'  # WARN класс переименован

        VERSION = "11.2.0.16"
        ELEMENT_LIMIT = 1000

        REQUIREMENTS = {
            GisObjectType.ACCRUAL: 100,  # идентификаторы платежных документов
            GisObjectType.NOTIFICATION: 100,  # извещения о квитировании
        }

        @property
        def description(self) -> str:

            return f"{len(self.object_ids)} ПД"

        def _store(self, import_results: list):

            # SRV008071: Отзыв платежного документа невозможен...
            # квитирован с извещениями о принятии к исполнению распоряжений.

            for imported in import_results:  # : CommonResultType
                pd_guid: GUID = self._mapped_guids[imported.TransportGUID]

                assert imported.UniqueNumber == pd_guid.unique, \
                    f"Полученный номер {imported.UniqueNumber}" \
                    f" не совпадает с переданным {pd_guid.unique}"

                self.annulment(pd_guid, imported.UpdateDate, imported.GUID)

        def _compose(self) -> dict:
            """importPaymentDocumentRequest"""
            assert self._pd_guids, "Требуются идентификаторы ГИС ЖКХ ПД"

            withdraw_pd: list = []

            for accrual_id in self.object_ids:
                pd_guid: GUID = self._map(self._pd_guids.get(accrual_id,
                    self.object_guid(GisObjectType.ACCRUAL, accrual_id)))

                if self.can_withdraw(pd_guid):  # подлежит отзыву?
                    payment_document: dict = pd_guid.as_req(
                        # TransportGUID сформирован при сопоставлении
                        PaymentDocumentID=pd_guid.unique,  # : str
                    )
                    withdraw_pd.append(payment_document)

            if not withdraw_pd:
                raise NoRequestWarning(
                    "Нет подлежащих отзыву платежных документов"
                )

            return dict(WithdrawPaymentDocument=withdraw_pd)  # Множественное

        def _preload(self):

            assert self.object_ids, \
                "Требуются идентификаторы отзываемых документов начислений"

            self._pd_guids = Bills.load_pd_guids(self, *self.object_ids)

            if (not self['update_existing'] or  # TODO дополнительное условие?
                    GisObjectType.NOTIFICATION in self.acquired):  # повторно?
                return  # WARN без отмены квитирования

            # получаем имеющие идентификатор извещения о квитировании (version)
            self._pd_guids = self.required_guids(GisObjectType.NOTIFICATION,
                *self.object_ids)  # TODO или self._pd_guids?

            if self.is_required(GisObjectType.NOTIFICATION):
                _import = \
                    Bills.importAcknowledgment(self.provider_id, self.house_id)
                self.follow(_import)  # сохраняем запись о текущей операции

                no_ack_ids: list = [accrual_id for accrual_id in self.object_ids
                    if accrual_id not in self._pd_guids]  # без идентификатора

                _import.prepare(*no_ack_ids)

                # WARN запись об операции сохраняется при выходе из контекста
                raise PendingSignal("Операция отложена до завершения"
                    " отмены квитирования платежных документов")

        def periodic(self, period: datetime = None):
            """Аннулировать выгруженные в ГИС ЖКХ начисления (ПД) за период"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                accrual_ids: list = self.period_accruals(period, False, False)
                if not accrual_ids:
                    raise NoDataError("Отсутствуют подлежащие отзыву"
                        f" документы начислений за {fmt_period(period)}")

            self(*accrual_ids)

    class exportNotificationsOfOrderExecution(ExportOperation):
        """
        Экспорт (извещений о принятии к исполнению распоряжений)
        результатов квитирования (ПД)
        """
        VERSION = "13.1.8.1"  # 10.0.1.1
        ELEMENT_LIMIT = 1  # TODO извещение о квитировании единственного ПД?

        can_withdraw = ImportPaymentDocumentOperation.can_withdraw

        @property
        def description(self) -> str:

            return f"№{self.object_ids[0]}"

        def _restore_mapping(self):

            self._mapped_guids = {guid.unique: guid
                for guid in GUID.objects(__raw__={
                    'record_id': self.record_id,  # сопоставленные операции
                    'unique': {'$ne': None},  # с уникальным номером
                })}

            self.log(f"Загружены {len(self._mapped_guids)}"
                " сопоставленных (с уникальным номером)"
                f" идентификаторов операции {self.record_id}")

        def store_order_execution(self, notification):
            """NotificationOfOrderExecutionWithStatus"""
            # WARN notification.orgPPAGUID - идентификатор (как правило) банка

            notification_execution_guid: str = \
                notification.NotificationsOfOrderExecutionGUID
            info = notification.OrderInfo
            order_id: str = info.OrderID  # для нужд квитирования
            # account_number: str = info.get('AccountNumber')
            # pay_doc_id: str = info.get('PaymentDocumentID')
            if notification.AckStatus in {
                AckStatus.NEW, AckStatus.ANNUL, AckStatus.NONE,
            }:
                status_description: str = sb(ACK_STATUS_DESCRIPTION.get(
                    notification.AckStatus, notification.AckStatus  # TODO или №
                ))
                self.log(warn="Платежный документ с идентификатором"
                    f" извещения {notification_execution_guid}"
                    f" получен в состоянии {status_description}")
                return  # ПД не сквитирован

            executions: dict = {}

            requests = notification.AcknowledgmentRequestsList
            for request in requests.AcknowledgmentRequest:  # : list
                # order_id: str = request['OrderID']
                execution_guid: str = \
                    request.NotificationsOfOrderExecutionGUID
                assert execution_guid == notification_execution_guid, \
                    "Идентификатор извещения отличается от указанного в запросе"

                if request.AckImpossible:  # не None?
                    impossible_reason: str = \
                        f"по причине {request.AckImpossible.Reason}" \
                        if request.AckImpossible.Reason else "без причины"
                    self.log(warn="Квитирование с идентификатором извещения"
                        f" {execution_guid} не выполнено {impossible_reason}")
                    return  # квитирование невозможно

                ack = request.PaymentDocumentAck  # или None
                payment_document_id: str = ack.PaymentDocumentID

                if executions.get(payment_document_id) == execution_guid:
                    continue  # пропускаем прежнее извещение о квитировании

                pd_guid: GUID = self._mapped_guids.get(payment_document_id)
                if pd_guid is not None:  # сопоставлен?
                    self.success(pd_guid,  # gis и root зарезервированы
                        version=execution_guid, number=order_id)

                executions[payment_document_id] = execution_guid

        def _store(self, export_results: list):
            """exportNotificationsOfOrderExecutionResult"""
            for exported in export_results:
                for notification in \
                        exported.NotificationOfOrderExecutionWithStatus:
                    self.store_order_execution(notification)

            # TODO вывод незагруженных идентификаторов?

        def _compose(self) -> dict:
            """exportNotificationsOfOrderExecutionRequest"""
            assert len(self.object_ids) == 1, \
                "Допускается загрузка данных о квитировании единственного ПД"

            pd_guid: GUID = \
                self.mapped_guid(GisObjectType.ACCRUAL, self.object_ids[0])

            supplier_ids: dict = {}  # PaymentDocumentID или другие реквизиты

            if self.can_withdraw(pd_guid):  # подлежит отзыву?
                supplier_ids['PaymentDocumentID'] = pd_guid.unique  # : str

            if not supplier_ids:
                raise NoRequestWarning("Нет подлежащих отмене квитирования ПД")

            return dict(SupplierIDs=supplier_ids)  # По реквизитам начислений

    class importAcknowledgment(ImportPaymentDocumentOperation):
        """Отмена квитирования"""

        VERSION = "11.0.0.2"
        ELEMENT_LIMIT = 100

        REQUIREMENTS = {GisObjectType.NOTIFICATION: 100}

        @property
        def description(self) -> str:

            return f"{len(self.object_ids)} ПД"

        def _store(self, import_results: list):

            for result in import_results:
                pd_guid: GUID = self._mapped_guids[result.TransportGUID]

                self.success(pd_guid, result.GUID,  # реальный идентификатор ПД
                    # WARN result.UniqueNumber не совпадает с PaymentDocumentId
                    updated=result.UpdateDate)  # WARN FixedOffset +03:00

        def _compose(self):
            """importAcknowledgmentRequest"""
            ack_cancellations: list = []

            for accrual_id in self.object_ids:
                pd_guid: GUID = self._map(self._pd_guids.get(accrual_id,
                    self.object_guid(GisObjectType.ACCRUAL, accrual_id)))

                if self.can_withdraw(pd_guid, has_ack=True):  # подлежит отзыву?
                    payment_document: dict = pd_guid.as_req(
                        # TransportGUID сформирован при сопоставлении
                        PaymentDocumentID=pd_guid.unique,
                        NotificationsOfOrderExecutionGUID=pd_guid.version,
                    )
                    ack_cancellations.append(payment_document)

            if not ack_cancellations:
                raise NoRequestWarning("Нет подлежащих отмене квитирования ПД")

            return dict(AckCancellation=ack_cancellations)  # Множественное

        def _preload(self):

            assert self.object_ids, "Отсутствуют идентификаторы отзываемых ПД"

            self._pd_guids = self.required_guids(GisObjectType.NOTIFICATION,
                *self.object_ids)  # извещения о квитировании (version)

            if self.is_required(GisObjectType.NOTIFICATION):  # не загружены?
                _export = Bills.exportNotificationsOfOrderExecution(
                    self.provider_id, self.house_id
                )
                self.follow(_export)  # сохраняем запись о текущей операции

                _export.prepare(*self.object_ids)  # : AccrualId

                # WARN запись об операции сохраняется при выходе из контекста
                raise PendingSignal("Операция отложена до завершения"
                    " загрузки идентификаторов извещений о квитировании")
