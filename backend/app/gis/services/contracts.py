from datetime import datetime

from app.gis.core.web_service import WebService

from app.gis.core.custom_operation import \
    ExportOperation, HouseManagementOperation
from app.gis.core.exceptions import GisError, NoDataError

from app.gis.models.choices import GisObjectType
from app.gis.models.guid import GUID
from app.gis.models.nsi_ref import nsiRef
from app.gis.models.attachment import Attachment

from app.gis.utils.common import sb, jn, as_guid, \
    is_between, get_max_time, fmt_period, get_time
from app.gis.utils.nsi import REFERENCE_NAMES
from app.gis.utils.meters import (
    day_from_selection, selection_from_day, selection_name,
    day_from_interval, interval_from_day,
)

from app.gis.services.house_management import SystemHouseDataLoader

from processing.models.billing.service_type import ServiceTypeGisName


class DocumentState:
    """importCharterResultType.State"""
    RUNNING = 'Running'
    NOT_RUNNING = 'NotRunning'
    EXPIRED = 'Expired'


class ContractStatus:  # ~ ManagedObjectStatus
    """ContractObject.ManagedObjectStatus: StatusMKDType"""
    PROJECT = 'Project'
    REJECTED = 'Rejected'
    TERMINATED = 'Terminated'
    APPROVAL_PROCESS = 'ApprovalProcess'
    REVIEWED = 'Reviewed'
    APPROVED = 'Approved'
    LOCKED = 'Locked'
    ANNUL = 'Annul'


CONTRACT_STATUS_NAMES = {
    ContractStatus.PROJECT: 'в проекте',
    ContractStatus.APPROVED: 'утвержден',
    ContractStatus.APPROVAL_PROCESS: 'на утверждении',
    ContractStatus.REVIEWED: 'рассмотрен',
    ContractStatus.REJECTED: 'отклонен',
    ContractStatus.TERMINATED: 'расторгнут (но не удален)',
    ContractStatus.ANNUL: 'аннулирован (удален)',
    ContractStatus.LOCKED: 'заблокирован',
}


def status_name(status: str) -> str:
    """Название состояния Устава (ДУ)"""
    return sb(CONTRACT_STATUS_NAMES.get(status), f"в состоянии {sb(status)}")


class ManagementContracts(WebService):

    SERVICE_NAME = 'HouseManagement'  # не ManagementContracts
    TARGET_NAMESPACE = 'house-management'  # не contracts

    class exportCAChData(SystemHouseDataLoader, ExportOperation):
        """Экспорт договоров управления, уставов, доп. соглашений"""

        VERSION = "10.0.1.1"  # TODO доступные версии: 13.0.0.1 и 13.1.2.1

        @property
        def description(self) -> str:

            return ("Последняя версия ДУ" if self.request.get('LastVersionOnly')
                else "Все версии ДУ")

        def _check_nsi_service(self, housing):

            element = housing.ServiceType  # полученный элемент НСИ
            description: str = f"№3.{element.Code}: {sb(element.Name)}"

            nsi_ref: nsiRef = self._nsi_refs.get(element.Code)
            if nsi_ref is None:  # элемент справочника КУ не загружен?
                self.warning("Данные элемента справочника коммунальных"
                    f" услуг {description} не загружены из ГИС ЖКХ")
            elif str(nsi_ref.guid) != element.GUID:
                # WARN идентификатор сущности на СИТ и ППАК отличается
                self.warning("Элемент справочника коммунальных"
                    f" услуг {description} имеет отличный"
                    " от полученного идентификатор ГИС ЖКХ")
            else:  # элемент справочника соответствует!
                self.log(f"Данные элемента справочника {description}"
                    f" соответствует ссылке на услугу {nsi_ref.id}")

        def __create_add_service(self, additional) -> ServiceTypeGisName:

            element = additional.ServiceType  # : nsiRef

            service_type = ServiceTypeGisName(provider=self.provider_id,
                created=additional.StartDate, closed=additional.EndDate,
                reference_name=REFERENCE_NAMES[1],  # для шаблонов
                reference_number='1', position_number=element.Code,
                gis_title=element.Name, guid=element.GUID)  # БЕЗ save

            service_type.save()  # WARN сохраняем (ссылку на) услугу ГИС ЖКХ

            return service_type

        def _check_add_service(self, additional, contract):
            """Проверить соответствие дополнительной услуги"""
            # TODO additional.BaseService - Основание?

            element = additional.ServiceType  # : nsiRef
            description: str = f"№1.{element.Code}: {sb(element.Name)}"

            service_type: ServiceTypeGisName = self._gis_names.get(element.Code)

            if not service_type:  # услуга не загружена из ГИС ЖКХ?
                self.warning("Данные элемента справочника услуг"
                    f" {description} не загружены из ГИС ЖКХ")
            elif str(service_type.guid) != element.GUID:  # СИТ?
                self.warning("Идентификатор ГИС ЖКХ элемента справочника"
                    f" {description} не совпадает с полученным")
                # service_type.guid = as_guid(element.GUID)  # или str
                # service_type.save()  # WARN сохраняем данные услуги
            elif service_type.name != element.Name:  # другое название?
                # WARN допускаются элементы с одним названием и разными ЕИ
                self.warning(f"Название элемента справочника {description}"
                    f" не соответствует услуге {sb(service_type.name)}")
            elif not is_between(  # сроки договора уже проверены
                 additional.StartDate, contract.StartDate, contract.EndDate
            ) or (contract.EndDate and not is_between(  # WARN Необязательное
                 additional.EndDate, contract.StartDate, contract.EndDate
            )):  # некорректные сроки предоставления услуги?
                self.warning("Некорректные сроки предоставления"
                    f" услуги {sb(service_type.name)} объекта управления")
            else:  # элемент справочника соответствует ДУ!
                self.log(f"Данные элемента справочника {description}"
                    f" соответствуют услуге {service_type.guid}")

        def _store_contract_object(self, exported):
            """
            Сохранить данные Объекта Управления (дома)
            """
            managed_guid: GUID = self.mapped_guid(
                GisObjectType.CONTRACT_OBJECT, self.service_bind.id
            )  # WARN сопоставляется привязка дома к организации (service_binds)
            managed_guid.premises_id = self.house_id
            managed_guid.version = exported.ContractObjectVersionGUID

            # WARN IsManagedByContract только для Charter.ContractObject

            if exported.Exclusion:  # объект исключен из устава?
                self.annulment(managed_guid,
                    exported.Exclusion.DateExclusion)
            elif not is_between(  # услуги не предоставляются или аннулирован?
                earlie=exported.StartDate, later=exported.EndDate
            ) or exported.StatusObject == ContractStatus.ANNUL:
                # Сведения об исключении объекта управления из устава
                self.annulment(managed_guid,
                    # дата окончания действия или предстоящая дата начала
                    exported.EndDate or exported.StartDate)
            elif exported.StatusObject == ContractStatus.APPROVED:
                self.success(managed_guid,
                    # идентификатор ГИС ЖКХ версии объекта управления (дома)
                    version=exported.ContractObjectVersionGUID)

                # проверяем наличие коммунальных услуг объекта управления
                for housing in exported.HouseService:  # Виды КУ
                    self._check_nsi_service(housing)
                # согласованность дополнительных услуг объекта управления
                for additional in exported.AddService:  # ДУ
                    self._check_add_service(additional, exported)
            else:  # Project, ApprovalProcess, Rejected, Locked
                self.failure(managed_guid, "Полученный объект управления "
                    + status_name(exported.StatusObject))  # в состоянии

        def _store_date_details(self, date_details):

            assert date_details, "Информация о сроках отсутствует"

            # Сроки передачи показаний ИПУ и ОДПУ?
            if date_details.PeriodMetering:
                period_metering = date_details.PeriodMetering
                self.house.gis_metering_start = \
                    day_from_selection(period_metering.StartDate)
                self.house.gis_metering_end = \
                    day_from_selection(period_metering.EndDate)

                self.log(info="Получены сроки передачи показаний приборов учета"
                    f" с {selection_name(self.house.gis_metering_start)}"
                    f" по {selection_name(self.house.gis_metering_end)}")

            # Срок выставления ПД за жилое помещение и комм. услуги?
            if date_details.PaymentDocumentInterval:
                self.house.gis_pay_doc_day = day_from_interval(
                    date_details.PaymentDocumentInterval)

                self.log(info="Получен срок выставления (начислений) ПД"
                    f" за жилое помещение и коммунальные услуги - "
                    + selection_name(self.house.gis_pay_doc_day))

            # Срок внесения платы за жилое помещение и комм. услуги?
            if date_details.PaymentInterval:
                self.house.gis_pay_day = day_from_interval(
                    date_details.PaymentInterval)

                self.log(info="Получен срок выставления платы"
                    " за жилое помещение и коммунальные услуги - "
                    + selection_name(self.house.gis_pay_day))

        def _store_charter(self, exported):
            """Сохранить данные Устава организации"""
            if exported.AttachmentCharter:  # Документы устава?
                # TODO self.management_contract.file_id
                attachments: str = '\n\t'.join(
                    f"{sb(file.Name)} ~ {file.Attachment.AttachmentGUID}"
                    for file in exported.AttachmentCharter  # Множественное
                ) or 'ОТСУТСВУЮТ'
                self.log(info=f"Идентификаторы вложенных документов устава"
                    f" {exported.CharterGUID}:\n\t{attachments}")

            if exported.NoCharterApproveProtocol:  # TODO MeetingProtocol
                self.log(warn="Содержащий решение об утверждении"
                    f" устава {exported.CharterGUID} протокол отсутствует")

            # TODO CharterPaymentsInfo - Сведения о размере платы

            if exported.IndicationsAnyDay:  # показания в любой день месяца?
                self.warning("Разрешена передача текущих показаний"
                    " индивидуальных приборов учета в любой день месяца")
            if exported.DateDetails:  # Информация о сроках?
                self._store_date_details(exported.DateDetails)

            # WARN номер (документа) Устава отсутствует в полученных данных
            self.management_contract.gis_uid = exported.CharterVersionGUID
            # Дата регистрации организации (ТСН, ТСЖ, КООП)
            self.management_contract.date = exported.Date

            self.house.save()  # WARN сохраняем (House) management_contract
            self.log(info="Сохранены данные версии устава с идентификатором"
                f" {exported.CharterVersionGUID} дома {self.house_id}")

            for contract_object in exported.ContractObject:  # Множественное
                if as_guid(contract_object.FIASHouseGuid) != self.fias_guid:
                    self.warning("Пропущены данные объекта управления (дома) с "
                        f"идентификатором ФИАС {contract_object.FIASHouseGuid}")
                    continue
                self._store_contract_object(contract_object)

        def _store_contract(self, exported):
            """Сохранить данные Договора Управления организации"""
            if exported.PlanDateComptetion < get_time():  # : datetime
                self.warning("Планируемая дата окончания действия ДУ"
                    f" №{exported.DocNum} достигнута " + fmt_period(
                        exported.PlanDateComptetion, with_day=True
                    ))

            if not exported.Owners:  # Собственник объекта жилищного фонда?
                self.warning(f"Организация не является собственником ОЖФ")
                root_entity_guid: str = (
                    exported.Cooperative.orgRootEntityGUID
                    if exported.Cooperative  # ТСЖ / Кооператив
                    else exported.MunicipalHousing.orgRootEntityGUID
                    if exported.MunicipalHousing  # Муниципальное жилье
                    else exported.BuildingOwner.orgRootEntityGUID
                    if exported.BuildingOwner  # Застройщик
                    else exported.CompetentAuthority.orgRootEntityGUID
                    if exported.CompetentAuthority  # Уполномоченный орган
                    else None
                )
                self.log(warn="Собственником ОЖФ является организация с"
                    f" идентификатором корневой сущности {root_entity_guid}")

            if exported.ContractAttachment:  # Необязательное
                # TODO management_contract.file_id
                attachments: str = '\n\t'.join(
                    f"{file.Name} ~ {file.Attachment.AttachmentGUID}"
                    for file in exported.ContractAttachment  # Множественное
                ) or 'ОТСУТСТВУЮТ'
                self.log(info=f"Идентификаторы вложенных документов договора"
                    f" управления №{exported.DocNum}:\n\t{attachments}")
                # TODO AgreementAttachment - Дополнительное соглашение

            # TODO ContractPaymentsInfo - Сведения о размере платы
            # TODO Validity (Month, Year) - Срок действия
            # TODO Protocol - Протокол открытого конкурса/собрания собственников

            if exported.IndicationsAnyDay:  # показания в любой день месяца?
                self.warning("Разрешена передача текущих показаний"
                    " индивидуальных приборов учета в любой день месяца")
            if exported.DateDetails:  # Информация о сроках?
                self._store_date_details(exported.DateDetails)

            self.management_contract.gis_uid = exported.ContractVersionGUID
            self.management_contract.number = exported.DocNum  # : str
            # SigningDate - Дата заключения (подписания)
            self.management_contract.date = \
                exported.EffectiveDate  # Дата вступления в силу

            self.house.save()  # WARN сохраняем (House) management_contract
            self.log(info="Сохранены данные договора управления"
                f" №{exported.DocNum} дома {self.house_id}")

            for contract_object in exported.ContractObject:  # Множественное
                if as_guid(contract_object.FIASHouseGuid) != self.fias_guid:
                    self.warning("Пропущены данные объекта управления (дома) с "
                        f"идентификатором ФИАС {contract_object.FIASHouseGuid}")
                    continue
                self._store_contract_object(contract_object)

        def _store(self, export_results: list):

            # коды и элементы справочников КУ и ДУ организации
            self._nsi_refs: dict = {ref.code: ref
                for ref in nsiRef.common_services(3)}  # Виды КУ организации

            self._gis_names: dict = {ref.code: ref  # : ServiceTypeGisName
                for ref in nsiRef.provider_services(self.provider_id, 1)}
            self.log("Частные (дополнительные) услуги организации:\n\t"
                + '\n\t'.join(f"1.{code}: {elem.gis_title}"
                    for code, elem in self._gis_names.items()))

            for result in export_results:  # : exportCAChResultType
                if result.Charter:  # Устав организации?
                    exported = result.Charter  # : CharterExportType
                    if exported.CharterStatus not in {ContractStatus.APPROVED}:
                        self.warning(f"Устав с корневым {exported.CharterGUID} "
                            + status_name(exported.CharterStatus)  # в состоянии
                            + " и не подлежит сохранению")
                        continue  # WARN пропускаем Устав

                    self._store_charter(exported)
                    break  # TODO сохранение более одного Устава
                elif result.Contract:  # Договор Управления?
                    exported = result.Contract  # : ContractExportType
                    if exported.ContractStatus not in {ContractStatus.APPROVED}:
                        self.warning(f"Договор управления №{exported.DocNum} "
                            + status_name(exported.ContractStatus)
                            + " и не подлежит сохранению")
                        continue  # WARN пропускаем ДУ

                    self._store_contract(exported)
                    break  # TODO сохранение более одного ДУ

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if not isinstance(request_data.get('Criteria'), list) \
                    or len(request_data['Criteria']) == 0:
                return False

            return True

        def approved(self):
            """
            Загрузка утвержденного ДУ (устава управляющей организации) дома

            Выполняется экспорт только крайней версии ДУ / устава
            """
            criteria = dict(  # SigningDate - Дата заключения ДУ
                UOGUID=self.ppaguid,  # Вариант №5
                FIASHouseGuid=self.fias_guid,  # только одного дома
                LastVersionOnly=True,  # WARN без прежних версий
            )

            self(Criteria=[criteria])  # Максимум 100

    class importCharterData(SystemHouseDataLoader, HouseManagementOperation):
        """Создание, изменение, удаление, пролонгация, расторжение Устава"""

        VERSION = "11.9.0.1"
        ELEMENT_LIMIT = 1

        def _parse(self, state_result) -> list:

            if state_result.ErrorMessage:  # : zeep.objects.ErrorMessageType
                raise GisError.from_result(state_result.ErrorMessage)

            common_results: list = []

            for import_result in state_result.ImportResult:  # : ImportResult
                if import_result.ErrorMessage:  # : ErrorMessageType
                    raise GisError.from_result(import_result.ErrorMessage)

                for common_result in import_result.CommonResult:
                    if common_result.Error:  # получена ошибка?
                        self._issue(common_result.TransportGUID,  # : str
                            common_result.Error)  # Множественное!
                    elif (common_result.importCharter  # ошибка устава?
                            and common_result.importCharter.Error):
                        self._issue(common_result.TransportGUID,  # : str
                            common_result.importCharter.Error)
                    elif (common_result.importContract  # ошибка ДУ?
                            and common_result.importContract.Error):
                        self._issue(common_result.TransportGUID,  # : str
                            common_result.importContract.Error)
                    else:  # получен результат!
                        common_results.append(common_result)

            return common_results

        def _store_contract_object(self, imported):

            managed_guid: GUID = self.mapped_guid(
                GisObjectType.CONTRACT_OBJECT, self.service_bind.id
            )  # WARN сопоставляется привязка дома к организации (service_binds)
            managed_guid.premises_id = self.house_id
            managed_guid.version = \
                imported.ContractObjectVersionGUID  # Необязательное

            if imported.IsConflicted:  # расхождение с Реестром?
                self.failure(managed_guid,
                    "Расхождение с Реестром информации об управлении МКД")
            elif imported.IsBlocked:  # заблокированный дом?
                self.failure(managed_guid,
                    "Управляемый объект (дом) заблокирован")
            elif imported.StatusObject == ContractStatus.APPROVED:
                self.success(managed_guid)  # идентификатор версии сохранен
            else:  # статус управляемого объекта?
                self.failure(managed_guid, "Полученный управляемый объект "
                    + status_name(imported.ManagedObjectStatus))  # в состоянии

        def _store_charter(self, imported):
            """importCharterResultType"""
            self.management_contract.gis_uid = imported.CharterVersionGUID
            # WARN номер и дата Устава отсутствуют в полученных данных

            # сохраняем данные ГИС ЖКХ объектов управления (домов)
            for contract_object in imported.ContractObject:  # Множественное
                if as_guid(contract_object.FIASHouseGuid) != self.fias_guid:
                    self.warning("Пропущены данные объекта управления (дома) с "
                        f"идентификатором ФИАС {contract_object.FIASHouseGuid}")
                    continue

                self._store_contract_object(contract_object)

            self.house.save()  # WARN сохраняем (House) management_contract
            self.log(info=f"Данные устава версии {imported.VersionNumber}"
                f" сохранены с идентификатором {imported.CharterVersionGUID}")

        def _store(self, common_results: list):

            for result in common_results:  # : CommonResult
                imported = result.importCharter  # : importCharterResultType

                # self._charter_guid = self._mapped_guids[result.TransportGUID]
                # self._charter_guid.version = imported.CharterVersionGUID
                # self._charter_guid.root = imported.CharterGUID  # Корневой

                if imported.State in {
                    DocumentState.NOT_RUNNING, DocumentState.EXPIRED,
                    None,  # TODO Необязательное?
                }:  # Состояние документа
                    # self.annulment(self._charter_guid,
                    #     result.UpdateDate, result.GUID)  # Необязательное
                    self.warning("Полученный документ (Устава) в состоянии"
                        f" {imported.State} не подлежит сохранению")
                elif imported.CharterStatus in {
                    ContractStatus.TERMINATED, ContractStatus.ANNUL,
                    ContractStatus.REJECTED,
                }:  # Статус ДУ
                    # self.annulment(self._charter_guid,
                    #     result.UpdateDate, result.GUID)  # Необязательное
                    self.warning(f"Устав с корневым {imported.CharterGUID} "
                        + status_name(imported.CharterStatus)
                        + " и не подлежит сохранению")  # в состоянии
                else:  # действующий / утвержденный!
                    self._store_charter(imported)

        def _contract_object(self) -> dict:
            """Объект управления"""
            managed_guid: GUID = self.mapped_guid(
                GisObjectType.CONTRACT_OBJECT, self.service_bind.id
            )  # WARN сопоставляется привязка дома к организации (service_binds)
            managed_guid.premises_id = self.house_id

            # WARN дата начала действия должна быть в интервале управления домом
            started: datetime = self.service_bind.date_start \
                or self.house.service_date  # или дата ввода в эксплуатацию дома
            # WARN окончание предоставления услуг бессрочного устава 01.01.5000
            finished: datetime = self.service_bind.date_end or get_max_time()

            if True:  # ProtocolMeetingOwners - Протокол собрания собственников?
                base_service: dict = {'CurrentCharter': True}  # Текущий ДУ

            manage_object = dict(
                FIASHouseGuid=self.fias_guid,
                BaseMService=base_service,  # WARN Необязательное в Edit
                StartDate=started, EndDate=finished or None,  # Необязательное
                # TODO IsManagedByContract  # по договору управления?
            )

            manage_object['HouseService'] = [{  # TODO все виды КУ?
                'BaseServiceCharter': base_service,
                'ServiceType': ref.as_req,  # : nsiRef
                'StartDate': started, 'EndDate': finished,
            } for ref in nsiRef.common_services(3)]  # WARN 51 содержатся в 3

            additional: dict = {f"{nsi_ref.number}: {nsi_ref.name}": nsi_ref
                for nsi_ref in nsiRef.provider_services(self.provider_id, 1)
                    if isinstance(nsi_ref, nsiRef)}
            if additional:  # дополнительные услуги организации?
                self.log("Дополнительные услуги организации"
                    f" {self.provider_id}:\n\t{jn(additional.keys())}")
                manage_object['AddService'] = [{  # Виды ДУ
                    'BaseServiceCharter': base_service,  # Основание
                    'ServiceType': nsi_ref.as_req,  # : nsiRef
                    'StartDate': started, 'EndDate': finished,  # Обязательные
                } for nsi_ref in additional.values()]
            else:  # нет дополнительных услуг!
                self.warning("Отсутствуют дополнительные услуги"
                    f" в управляемом {self.provider_name}"
                    f" доме {self.house_address}")  # TODO raise?

            if not self.version_guid:  # нет идентификатора (версии) ДУ?
                return managed_guid.as_req(**manage_object)  # PlacingCharter

            # region ВНЕСЕНИЕ ИЗМЕНЕНИЙ В ВЕРСИЮ УСТАВА (EditCharter)
            if managed_guid:  # идентификатор (версии) объекта управления?
                return managed_guid.as_req(Edit={**manage_object,
                    'ContractObjectVersionGUID': managed_guid.version})
            else:  # WARN добавляем новый объект управления!
                return managed_guid.as_req(Add=manage_object)  # TransportGUID
            # endregion ВНЕСЕНИЕ ИЗМЕНЕНИЙ В ВЕРСИЮ УСТАВА (EditCharter)

        def _date_details(self) -> dict:
            """Информация о сроках"""
            metering_period: dict = {
                'StartDate': selection_from_day(self.house.gis_metering_start),
                'EndDate': selection_from_day(self.house.gis_metering_end),
            }

            # WARN INT015045: DateDetails должен быть заполнен (все 3 значения)
            return dict(
                # Сроки передачи показаний индивидуальных и квартирных ПУ
                PeriodMetering=metering_period,
                # Срок выставления ПД для внесения платы за жилищные и/или КУ
                PaymentDocumentInterval=interval_from_day(
                    self.house.gis_pay_doc_day
                ),
                # Срок внесения платы за жилищные и/или коммунальные услуги
                # TODO в настройках начислений "Оплатить до"
                PaymentInterval=interval_from_day(self.house.gis_pay_day),
            )

        def _charter(self) -> dict:
            """Данные устава"""
            if not self.management_contract.file_id:
                raise NoDataError("Требуется файл вложения устава")

            attachment: Attachment = Attachment.fetch(
                self.management_contract.file_id, self.provider_id
            )  # WARN выбрасывает NoDataError

            charter_data: dict = {
                'Date': self.provider_guid.updated,  # TODO Дата регистрации?
                'DateDetails': self._date_details(),  # Необязательное
                'AttachmentCharter': [attachment.as_req],  # Множественное
                'ContractObject': [self._contract_object()],  # Множественное
            }

            if True:  # TODO MeetingProtocol - Протокол собрания собственников
                charter_data['NoCharterApproveProtocol'] = True  # отсутствует

            # IndicationsAnyDay - Разрешить передачу показаний ИПУ в любой день?
            # Используется значение глобальной настройки (по всем договорам)

            if True:  # Автоматически продлить срок оказания услуг на один год?
                charter_data['AutomaticRollOverOneYear'] = True  # TODO всегда?

            return charter_data

        def _compose(self) -> dict:

            if self.version_guid:  # идентификатор ГИС ЖКХ версии устава?
                charter_request = {'EditCharter': {
                    'CharterVersionGUID': self.version_guid,
                    **self._charter()
                }}
            else:
                charter_request: dict = {'PlacingCharter': self._charter()}

            return charter_request

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if not self.provider_guid.updated:
                raise NoDataError(
                    f"Дата регистрации {self.provider_name} не определена"
                )

            return True

    # TODO importContractData - Создание, редактирование, удаление ДУ
