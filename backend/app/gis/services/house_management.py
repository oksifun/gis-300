from dateutil.relativedelta import relativedelta
from django.utils.functional import cached_property

from typing import Optional

from uuid import UUID
from bson import ObjectId
from datetime import datetime
from collections import defaultdict

from re import match as re_match, IGNORECASE

from app.gis.core.web_service import WebService
from app.gis.core.async_operation import AsyncOperation
from app.gis.core.custom_operation import \
    ExportOperation, HouseManagementOperation
from app.gis.core.exceptions import PendingSignal, \
    NoGUIDError, NoDataError, NoRequestWarning, ObjectError

from app.gis.models.choices import GisObjectType
from app.gis.models.guid import GUID
from app.gis.models.nsi_ref import nsiRef

from app.gis.utils.common import as_guid, sb, concat, \
    is_between, get_period, fmt_period, get_time, sp
from app.gis.utils.providers import is_ogrn, ogrn_or_not, kpp_or_not
from app.gis.utils.accounts import get_account_type_name, \
    get_typed_accounts, get_last_accrual_doc_ids, get_responsible_tenants, \
    get_accrual_doc_ids
from app.gis.utils.houses import get_fixed_number, add_hyphen_before_last_N
from app.gis.utils.meters import (
    is_correct_sn, get_serial_number, get_description, get_premisses_id,
    get_resource_code, get_resource_type,
    get_resource_meters, get_typed_meters, get_house_meters,
    METER_OKEI_UNITS
)

from app.meters.models.meter import AreaMeter, HouseMeter, \
    VOLUME_METER, ELECTRIC_METER, DEFAULT_OKEI_UNITS, \
    METER_CHECK_INTERVAL_BY_TYPE
from app.meters.models.choices import MeterMeasurementUnits as MeasurementUnits

from app.area.models.area import Area
from app.house.models.house import House, Porch, Lift, \
    EmbeddedManagerContract, HouseEmbededServiceBind

from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual

from processing.models.choices import GenderType, AreaType, TenantType

from processing.data_producers.balance.base import CONDUCTED_STATUSES


class SystemHouseDataLoader:
    """
    Загрузчик Системных (не ГИС ЖКХ) данных дома

    TODO Загружаются данные всех полей модели House

    WARN Должен идти в списке наследования ДО класса операции (AsyncOperation)
    """
    @cached_property
    def house(self) -> House:
        """Системные данные дома"""
        assert isinstance(self, AsyncOperation)

        # TODO 'service_binds.provider': self.provider_id,
        house: House = House.objects.with_id(self.house_id)

        self.log("Загружены Системные данные управляемого"
            f" {self.provider_id} дома {self.house_id}")

        return house

    @property
    def fias_guid(self) -> Optional[UUID]:
        """Идентификатор ФИАС (или временный ГИС ЖКХ) дома"""
        return as_guid(self.house.gis_fias  # идентификатор ГИС ЖКХ
            or self.house.fias_house_guid)  # идентификатор ФИАС или None

    @property
    def cadastral_number(self) -> str:
        """Кадастровый номер дома"""
        return (self.house.cadastral_number or '').strip()

    @property
    def house_address(self) -> str:
        """Адрес дома"""
        return self.house.address  # есть всегда?

    @cached_property
    def management_contract(self) -> EmbeddedManagerContract:
        """Договор управления домом"""
        if not self.house.management_contract:
            self.house.management_contract = EmbeddedManagerContract()

        assert self.house.management_contract.id, \
            "Отсутствует идентификатор (документа) договора управления"

        return self.house.management_contract

    @property
    def version_guid(self) -> Optional[str]:
        """Идентификатор версии устава в ГИС ЖКХ"""
        return self.management_contract.gis_uid  # или None

    @cached_property
    def service_bind(self) -> HouseEmbededServiceBind:  # WARN опечатка
        """Привязка управляющей организации к дому"""
        # действующие привязки начавших и продолжающих управление организаций
        provider_binds: dict = self.house.provider_binds(True, True, True)

        assert isinstance(self, AsyncOperation)
        service_bind = provider_binds.get(self.provider_id)  # или None

        assert isinstance(service_bind, HouseEmbededServiceBind), \
            "Не установлена связь текущей организации с домом"

        self.log("Получены данные действующей привязки управляемого"
            f" {self.provider_id} дома {self.house_id}")

        return service_bind


class MeteringDevice:

    NA = 'нет данных'  # замена отсутствующих данных

    def __init__(self, meter: dict):

        self._meter = meter

    # region СВОЙСТВА
    @property
    def is_living_area(self) -> bool:
        """Жилое помещение (квартира)?"""
        return AreaType.LIVING_AREA in self._meter['area']['_type']

    @property
    def is_not_living_area(self) -> bool:
        """Нежилое помещение?"""
        return AreaType.NOT_LIVING_AREA in self._meter['area']['_type']

    @property
    def is_parking(self) -> bool:
        """Машиноместо (паркинг)?"""
        return AreaType.PARKING_AREA in self._meter['area']['_type']

    @cached_property
    def serial_number(self) -> str:
        """Серийный (заводской) номер"""
        return get_serial_number(self._meter, '')  # WARN не None

    @cached_property
    def resource_type(self) -> str:
        """Тип ресурса"""
        return get_resource_type(*self._meter['_type'])

    @cached_property
    def municipal_resource(self) -> dict:  # ~ nsiRef
        """Ссылка на элемент справочника ресурсов"""
        return nsiRef.common(2, get_resource_code(self.resource_type))

    @cached_property
    def okei_unit(self) -> str:
        """Единица измерения ресурса"""
        okei_unit: str = self._meter.get('unit_of_measurement_okei')

        if not okei_unit:
            okei_unit = DEFAULT_OKEI_UNITS.get(self.resource_type)

        return okei_unit

    @property
    def is_consumed_volume(self) -> bool:
        """Наличие технической возможности автоматического
        расчета потребляемого объема коммунального ресурса?"""
        return self.resource_type in VOLUME_METER

    @property
    def is_energy(self) -> bool:
        """Учет электрической энергии?"""
        return self.resource_type in ELECTRIC_METER

    @property
    def is_remote_metering(self) -> bool:
        """
        Наличие возможности дистанционного снятия показаний?

        При RemoteMeteringMode=true нет возможности вводить показания через ЛК
        """
        return self._meter.get('is_automatic') or False

    @property
    def is_area_meter(self) -> bool:
        """Индивидуальный ПУ?"""
        return 'AreaMeter' in self._meter['_type']  # self._meter.get('area')

    @property
    def is_house_meter(self) -> bool:
        """ОбщеДомовой ПУ?"""
        return 'HouseMeter' in self._meter['_type']  # self._meter.get('house')

    @property
    def area_id(self) -> ObjectId:
        """Идентификатор помещения установки"""
        assert self.is_area_meter, "Данные помещения только индивидуального ПУ"
        return self._meter['area']['_id']

    @property
    def house_id(self) -> ObjectId:
        """Идентификатор дома установки"""
        assert self.is_house_meter, "Идентификатор дома только общедомового ПУ"
        return self._meter['house']['_id']

    @property
    def is_deleted(self) -> bool:
        """Удален?"""
        return self._meter.get('is_deleted') or False

    @property
    def installed(self) -> Optional[datetime]:
        """Дата установки"""
        return self._meter.get('installation_date')  # не обязательное

    @property
    def commissioned(self) -> datetime:
        """Дата начала работы"""
        return self._meter.get('working_start_date')  # будет обязательным

    @property
    def disassembled(self) -> Optional[datetime]:
        """Когда снят?"""
        return self._meter.get('working_finish_date')

    @property
    def replaced(self) -> Optional[datetime]:
        """
        Когда заменен?

        Если есть change_meter_date, то есть и working_finish_date
        """
        return self._meter.get('change_meter_date')

    @cached_property
    def replacing_id(self) -> Optional[ObjectId]:
        """Идентификатор замещающего ПУ"""
        return AreaMeter.objects(__raw__={
            'area._id': self.area_id,  # в том же помещении
            'communication': self._meter['communication'],  # на том же стояке
            **AreaMeter.working_meter_query(),  # действующий ИПУ
        }).scalar('id').first() if self._meter.get('communication') else None

    @cached_property
    def initial_values(self) -> list:
        """Начальные показания"""
        if self._meter.get('initial_values'):
            return self._meter['initial_values']

        if self._meter.get('readings'):  # есть всегда?
            return self._meter['readings'][0]['values']  # первые показания

        return []

    @property
    def one_rate_value(self) -> dict:
        """Показания по одному тарифу"""
        assert not self.is_energy, ""
        return {
            'MunicipalResource': self.municipal_resource,  # ~ nsiRef
            'MeteringValue': self.initial_values[0],  # 15 до запятой, 7 после
        }

    @cached_property
    def multi_rate_values(self) -> dict:
        """Показания по нескольким тарифам"""
        # WARN MunicipalResource требуется только для NotEnergy
        return {  # 15 до запятой, 7 после
            'MeteringValueT1': self.initial_values[0],  # Показание по T1
            'MeteringValueT2': self.initial_values[1],  # Показание по T2
            'MeteringValueT3': self.initial_values[2],  # Показание по T3
        } if self.tariff_count == 3 else {
            'MeteringValueT1': self.initial_values[0],
            'MeteringValueT2': self.initial_values[1],
        } if self.tariff_count == 2 else {
            'MeteringValueT1': self.initial_values[0],  # Обязательное
        } if self.tariff_count == 1 else {}

    @property
    def tariff_count(self) -> int:
        """Количество тарифов"""
        return len(self.initial_values)  # или readings

    @property
    def transformation_ratio(self) -> int:
        """
        Коэффициент трансформации

        TODO decimal ~ 9999999999.9999
        """
        assert self.is_energy, \
            "Коэффициент трансформации заполняется только для электроэнергии"
        return self._meter['ratio']  # обязательное, по умолчанию = 1

    @property
    def check_interval(self) -> int:
        """
        Межповерочный интервал (НСИ 16)

        Значения от 1 до 20 - интервал в годах; 21 - 30 лет
        """
        check_interval: int = self._meter.get('expiration_date_check') \
            or METER_CHECK_INTERVAL_BY_TYPE.get(self.resource_type)

        if not check_interval:
            check_interval = 6  # лет, по умолчанию
        elif check_interval > 20:  # GasRateAreaMeter: 25
            check_interval = 21  # ~ 30 лет

        return check_interval

    @property
    def first_check_date(self) -> datetime:
        """Дата первичной поверки"""
        return self._meter.get('first_check_date', get_time(ms=0))

    @property
    def last_check_date(self) -> Optional[datetime]:
        """Дата следующей поверки"""
        return self._meter.get('last_check_date')

    @property
    def next_check_date(self) -> datetime:
        """Дата следующей поверки"""
        check_date: datetime = self._meter.get('next_check_date')  # кроме ОДПУ?

        if not check_date:
            check_date = (
                self.last_check_date or self.first_check_date
            ).replace(
                year=check_date.year + self.check_interval
            )

        return check_date

    @property
    def _has_previous_readings(self) -> bool:
        """Имеются показания за предыдущий период?"""
        current_period: datetime = get_period()

        for reading in self._meter['readings']:  # по умолчанию = []
            if current_period >= reading['period']:
                return True

        return False
    # endregion СВОЙСТВА

    def basic_characteristics(self) -> dict:
        """MeteringDeviceBasicProtoType"""
        characteristics: dict = {
            'MeteringDeviceNumber': self.serial_number,
            'MeteringDeviceStamp': self._meter.get('brand_name') or self.NA,
            'MeteringDeviceModel': self._meter.get('model_name') or self.NA,

            'InstallationDate': self.installed,  # Необязательное
            'CommissioningDate': self.commissioned,  # Обязательное (кроме ОДПУ)

            'RemoteMeteringMode': self.is_remote_metering,  # автоматизированный
            'RemoteMeteringInfo': self.NA,  # обязательно при RemoteMeteringMode

            'FirstVerificationDate': self.last_check_date,  # Обязательное ОДПУ
            'FactorySealDate': self.first_check_date,  # Обязательное

            'TemperatureSensor': False,  # Обязательное
            'PressureSensor': False,  # Обязательное
        }

        if self.is_consumed_volume:  # Предоставляет объем потребленного КР?
            characteristics['ConsumedVolume'] = True  # Необязательное

        return characteristics

    def linked(self, *meter_guids) -> Optional[dict]:
        """
        Связать ПУ с другими заведенными в ГИС ЖКХ ПУ.

        Операция возможна только, если для текущего ПУ установлен признак
        "Объем ресурса определяется с помощью нескольких приборов учета".

        :param meter_guids: перечень (идентификаторов версии) связанных ПУ
        """
        return {
            'LinkedMeteringDeviceVersionGUID': meter_guids,
            # 'in' - на входе, 'out' - на выходе
            'InstallationPlace': 'out' if self._meter.get('reverse') else 'in',
        } if meter_guids else None

    def archive(self) -> dict:
        """Архивация ПУ без замены на другой ПУ"""
        # Архивация ПУ (НСИ 21):
        #  1 - Замена в связи с поломкой,
        #  2 - Замена по иной причине,
        #  3 - Замена после проведения поверки,
        #  4 - Ошибка,
        #  5 - Истек срок действия основания управления ОЖФ,
        #  6 - Срок проведения плановой поверки истек,
        #  7 - Снос дома,
        #  8 - Неисправность прибора учета,
        #  9 - Заключение прямого договора с РСО,
        # 10 - Прекращение деятельности создавшей ПУ организации
        return {'ArchivingReason': nsiRef.common(21,
            3 if self.replaced else 4 if self.is_deleted else 8)}

    def replace(self, replacing_guid: GUID) -> dict:
        """Архивация ПУ с заменой на другой ПУ"""
        assert self.replaced and replacing_guid

        replacer: dict = {
            'VerificationDate': self.replaced,  # Дата поверки
            # WARN идентификатор версии заменяющего ПУ в ГИС ЖКХ
            'ReplacingMeteringDeviceVersionGUID': replacing_guid.gis,
        }

        # TODO ReasonVerification - Причина внеплановой поверки (НСИ 224):
        #  1 - Неотображение результатов измерений,
        #  2 - Нарушение контрольных пломб / знаков проверки,
        #  3 - Механическое повреждение,
        #  4 - Превышение допустимой погрешности показаний,
        #  5 - Истечение межпроверочного интервала
        if True:  # Плановая поверка?
            replacer['PlannedVerification'] = True

        if self.is_consumed_volume:
            replacer['VolumeDeviceValues'] = [{
                'MunicipalResource': self.municipal_resource,
                **self.multi_rate_values  # без MunicipalResource
            }]  # Максимум 3
        elif self.is_energy:
            replacer['DeviceValueMunicipalResourceElectric'] = \
                self.multi_rate_values  # единственный элемент
        else:  # not is_energy
            replacer['DeviceValueMunicipalResourceNotElectric'] = [
                self.one_rate_value
            ]  # Максимум 3

        return replacer  # : ReplaceDevice


class HouseManagement(WebService):
    """Асинхронный сервис управления объектами РАО"""

    # region ЗАГРУЗКА ТРЕБУЕМЫХ ДАННЫХ
    @classmethod
    def load_house_guid(cls, self: AsyncOperation):
        """
        Загрузить идентификатор ГИС ЖКХ дома
        """
        assert not self.IS_HOMELESS and not self.house_guid, \
            "Загрузка идентификатора ГИС ЖКХ дома не требуется"

        if (not self['load_requirements']  # WARN не has_requirements
                or GisObjectType.HOUSE in self.acquired):  # не первый раз?
            raise NoGUIDError("Не загружен идентификатор"
                " ГИС ЖКХ (не ФИАС) дома")

        self.acquired[GisObjectType.HOUSE] = 0  # признак загрузки

        _export = cls.exportHouseData(self.provider_id, self.house_id)
        self.follow(_export)  # WARN сохраняем запись о текущей операции

        _export.prepare()  # без аргументов - идентификаторов помещений

        # WARN запись об операции сохраняется при выходе из контекста
        raise PendingSignal("Операция была отложена до завершения"
            " загрузки идентификатора ГИС ЖКХ дома")

    @classmethod
    def load_area_guids(cls, self: AsyncOperation, *area_id_s: ObjectId):
        """
        Загрузить идентификаторы ГИС ЖКХ помещений дома
        """
        assert area_id_s, "Список идентификаторов требуемых помещений пуст"

        area_guids: dict = \
            self.required_guids(GisObjectType.AREA, *area_id_s)

        if self.is_required(GisObjectType.AREA):  # требуется загрузка?
            _export = cls.exportHouseData(self.provider_id, self.house_id)

            self.follow(_export)  # WARN сохраняем запись о текущей операции

            _export.prepare(*area_id_s)  # подготавливаем упреждающую операцию

            # WARN запись об операции сохраняется при выходе из контекста
            raise PendingSignal("Операция была отложена до завершения"
                " загрузки идентификаторов ГИС ЖКХ помещений ЛС")

        return area_guids

    @classmethod
    def load_account_guids(cls, self: AsyncOperation, *tenant_id_s: ObjectId):
        """
        Загрузить идентификаторы ГИС ЖКХ лицевых счетов (жителей) дома
        """
        assert tenant_id_s, "Список идентификаторов требуемых ЛС пуст"

        account_type: str = GisObjectType.UO_ACCOUNT
        account_guids: dict = self.required_guids(account_type, *tenant_id_s)

        if self.is_required(account_type):  # требуется загрузка?
            _export = cls.exportAccountData(self.provider_id, self.house_id)
            self.follow(_export)  # WARN сохраняем запись о текущей операции

            _export.prepare(*tenant_id_s)  # подготавливаем упреждающую операцию

            # WARN запись об операции сохраняется при выходе из контекста
            raise PendingSignal("Операция была отложена до завершения"
                " загрузки идентификаторов ГИС ЖКХ лицевых счетов")

        return account_guids

    @classmethod
    def _require_account_guids(cls, self: AsyncOperation,
            account_type: str, *tenant_id_s: ObjectId):
        """
        Выгрузить идентификаторы ГИС ЖКХ лицевых счетов (жителей) дома

        Выгрузка выполняется непосредственно перед завершением текущей операции
        """
        assert tenant_id_s, "Список идентификаторов требуемых ЛС пуст"

        account_guids: dict = self.required_guids(account_type, *tenant_id_s)

        if self.is_required(account_type):  # требуется загрузка ид-ов?
            _import = cls.importAccountData(self.provider_id, self.house_id,
                update_existing=False)  # WARN не обновляем имеющиеся в ГИС ЖКХ
            self.follow(_import)  # WARN сохраняем в последовательном режиме

            _import(*tenant_id_s,
                account_type=GisObjectType.UO_ACCOUNT)  # WARN ЛС для оплаты КУ

            # WARN запись об операции сохраняется при выходе из контекста
            raise PendingSignal("Операция была отложена до завершения"
                " загрузки идентификаторов ГИС ЖКХ лицевых счетов")

        return account_guids

    @classmethod
    def load_meter_guids(cls, self: AsyncOperation,
            meter_type: str, *meter_id_s: ObjectId):
        """
        Загрузить идентификаторы ГИС ЖКХ (индивидуальных) приборов учета
        """
        assert meter_id_s, "Список идентификаторов требуемых ПУ пуст"

        # WARN owned_guids переопределен в exportMeteringDeviceHistory
        device_guids: dict = self.required_guids(meter_type, *meter_id_s)

        if self.is_required(meter_type):  # требуется загрузка?
            _export = cls.exportMeteringDeviceData(
                self.provider_id, self.house_id
            )
            self.follow(_export)  # сохраняем запись о текущей операции

            _export.prepare(*meter_id_s)  # подготавливаем упреждающую операцию

            # WARN запись об операции сохраняется при выходе из контекста
            raise PendingSignal("Операция была отложена до завершения"
                " загрузки идентификаторов ГИС ЖКХ приборов учета")

        return device_guids
    # endregion ЗАГРУЗКА ТРЕБУЕМЫХ ДАННЫХ

    # WARN exportBriefBasicHouseRequest - разрешена только для РЦ
    # TODO exportBriefApartmentHouse / exportBriefLivingHouse - только для РЦ?

    class exportHouseData(SystemHouseDataLoader, ExportOperation):
        """Экспорт данных дома"""

        IS_HOMELESS = True  # операция без (загрузки данных ГИС ЖКХ) дома

        VERSION = "12.2.0.1"

        GET_STATE_DELAY = [10, 30, 60, 120, 300, 600]  # около 5 минут

        NON_RESIDENTIAL_AREA_TYPES = [
            AreaType.NOT_LIVING_AREA, AreaType.PARKING_AREA
        ]  # нежилые

        @property
        def description(self) -> str:

            return f"ФИАС: {self.request.get('FIASHouseGuid') or 'ОТСУТСТВУЕТ'}"

        def _store_entrances(self, apartment_house):

            entrances = {entrance.EntranceNum: entrance  # : str - Обязательное
                for entrance in apartment_house.Entrance  # полученные подъезды
            if not entrance.TerminationDate}  # ТОЛЬКО НЕАНУЛИРОВАННЫЕ!
            # номер аннулированного подъезда совпадает с неаннулированным!

            lifts = {lift.FactoryNum: lift  # : str - Обязательное
                for lift in apartment_house.Lift}  # полученные лифты

            for porch in self.house.porches or []:  # подъезды (парадные) дома
                assert isinstance(porch, Porch)
                porch_guid: GUID = \
                    self.mapped_guid(GisObjectType.PORCH, porch.id)
                porch_guid.number = str(porch.number or 1)  # : int или null

                exported = entrances.pop(porch_guid.number, None)  # извлекаем
                if not exported:
                    self.failure(porch_guid,
                        f"Подъезд №{porch_guid.number} отсутствует в ГИС ЖКХ")
                    continue  # помещения будут выгружены вместе с подъездами

                # только один действующий подъезд с определенным номером!
                self.success(porch_guid, exported.EntranceGUID)

                for lift in porch.lifts:  # лифты в подъезде (парадной)
                    assert isinstance(lift, Lift)
                    if not lift.id:  # TODO нет идентификатора?
                        self.warning("Данные ГИС ЖКХ лифта без id в подъезде"
                            f" №{porch_guid.number} не могут быть сохранены")
                        continue  # пропускаем лифт
                    lift_guid: GUID = \
                        self.mapped_guid(GisObjectType.LIFT, lift.id)

                    match = re_match(r'заводской №\s*(.*)', flags=IGNORECASE,
                        string=lift.desc or "")
                    lift_guid.number = match.group(1) if match \
                        else lift.number  # есть не всегда!
                    if not lift_guid.number:  # лифт не имеет номера?
                        self.failure(lift_guid, "Номер лифта не определен")
                        # в том числе не найден в описании "заводской №"
                        continue  # не сопоставить с полученными данными

                    exported = lifts.pop(lift_guid.number, None)  # извлекаем
                    if not exported:
                        self.failure(lift_guid,
                            f"Лифт №{lift_guid.number} отсутствует в ГИС ЖКХ")
                    elif exported.EntranceNum != porch_guid.number:  # : str
                        self.failure(lift_guid, "Подъезд лифта не совпадает")
                    elif exported.TerminationDate:  # подъезд аннулирован?
                        self.annulment(lift_guid,
                            exported.TerminationDate, exported.LiftGUID)
                    else:  # соответствие найдено!
                        self.success(lift_guid, exported.LiftGUID)

        def _store_premises_w_rooms(self, residential_premises):

            def _store_rooms():
                """Сохранить данные ГИС ЖКХ комнат квартиры"""
                living_rooms = {living.RoomNumber: living  # : str
                    for living in residential.LivingRoom}  # комнаты в квартире

                area_rooms = {room['_id']: room for room in area['rooms']
                    if room.get('number')}  # кроме комнат 0 / без номера

                if area.get('is_shared') and not area_rooms:
                    self.warning("Коммунальная квартира"
                        f" №{area_number} не содержит комнат")

                room_guids: dict = \
                    self.mapped_guids(GisObjectType.ROOM, *area_rooms) \
                    if area_rooms else {}  # данные ГИС ЖКХ комнат квартиры

                for room_id, room in area_rooms.items():
                    room_guid: GUID = room_guids.get(room_id)
                    assert room_guid is not None, \
                        f"Отсутствует идентификатор ГИС ЖКХ помещения {room_id}"
                    room_guid.number = str(room['number'])  # : Int32
                    room_guid.desc = area_guid.desc  # "кв. 224"

                    exported = living_rooms.get(room_guid.number)  # по номеру
                    if not exported:  # комната не найдена в выгрузке?
                        if len(area_rooms) == 1:  # единственная комната?
                            self._unmap(room_guid)  # отменяем сопоставление
                            continue  # WARN переходим к следующей квартире

                        self.failure(room_guid, f"Комната №{room_guid.number}"
                            f" квартиры №{area_number} отсутствует в ГИС ЖКХ")
                    elif room.get('square', exported.Square) != exported.Square:
                        self.failure(room_guid, "Площадь комнаты не совпадает")
                    elif exported.TerminationDate:  # комната аннулирована?
                        self.annulment(room_guid,
                            exported.TerminationDate, exported.LivingRoomGUID)
                    else:  # соответствие найдено!
                        self.success(room_guid, exported.LivingRoomGUID,
                            unique=exported.LivingRoomUniqueNumber)

            area_query: dict = {
                '_id': {'$in': self.object_ids}, '_type': AreaType.LIVING_AREA,
            } if self.object_ids else {
                'house._id': self.house_id, 'is_deleted': {'$ne': True},
                '_type': AreaType.LIVING_AREA,
            }
            areas: dict = {area['_id']: area
                for area in Area.objects(__raw__=area_query).only(
                    '_type', 'is_shared', 'str_number', 'str_number_full',
                    'cadastral_number', 'gis_uid', 'rooms'
                ).as_pymongo()}
            if not areas:  # квартиры не найдены?
                self.warning("Отсутствуют жилые помещения управляемого"
                    f" {self.provider_name} дома {self.house_address}")
                return  # нечего сохранять

            residential_premises: dict = {res.PremisesNum: res
                for res in residential_premises
            if res.TerminationDate is None}  # неаннулированные квартиры

            cadastral_numbers: dict = {res.CadastralNumber:  # : str
                    res.PremisesNum for res in residential_premises.values()
                if not res.No_RSO_GKN_EGRP_Registered  # Нет связи с ГКН/ЕГРП
                    and not res.No_RSO_GKN_EGRP_Data}  # Нет данных для связи

            area_guids: dict = self.mapped_guids(GisObjectType.AREA, *areas)

            for area_id, area in areas.items():  # сохраняемые квартиры
                area_guid: GUID = area_guids.get(area_id)
                area_guid.premises_id = self.house_id  # WARN привязка к дому

                area_number: str = area['str_number'].strip()
                area_guid.number = area_number  # : str
                area_guid.desc = \
                    area.get('str_number_full') or f"кв. {area_number}"

                cadastral_number: str = (
                    area.get('cadastral_number') or 'нет'  # по умолчанию 'нет'
                ).strip()  # WARN необязательный реквизит
                if cadastral_number != 'нет':
                    premises_num: str = cadastral_numbers.get(cadastral_number)
                    if premises_num and premises_num != area_number:
                        self.warning(f"Номер квартиры {area_number}"
                            f" с кадастровым номером {cadastral_number}"
                            f" отличается от полученного {premises_num}")
                        if area_number not in residential_premises:
                            area_number = premises_num

                residential = residential_premises.pop(
                    area_number, None  # по номеру квартиры
                )  # WARN извлекаем полученные данные

                if not residential:  # квартира не найдена?
                    self.failure(area_guid, "Квартира отсутствует в ГИС ЖКХ")
                    # TODO self._unmap(area_guid)  # привязка к другому дому?
                    continue  # комнаты квартиры также будут выгружены
                elif residential.TerminationDate:  # квартира аннулирована?
                    self.annulment(area_guid,
                        residential.TerminationDate, residential.PremisesGUID)
                    # WARN комнаты будут аннулированы в _store_rooms
                else:  # получены данные ГИС ЖКХ квартиры!
                    self.success(area_guid, residential.PremisesGUID,
                        unique=residential.PremisesUniqueNumber)
                    Area.update_gis_data(area_guid.object_id,
                        residential.PremisesUniqueNumber)

                if area.get('rooms'):  # комнаты в квартире?
                    _store_rooms()  # сохраняем комнаты

        def _store_premises(self, non_residential_premises):

            area_query: dict = {
                '_id': {'$in': self.object_ids},
                '_type': {'$in': self.NON_RESIDENTIAL_AREA_TYPES},
            } if self.object_ids else {
                'house._id': self.house_id, 'is_deleted': {'$ne': True},
                '_type': {'$in': self.NON_RESIDENTIAL_AREA_TYPES},
            }
            areas: dict = {area['_id']: area for area
                in Area.objects(__raw__=area_query).only(
                    '_type', 'is_shared', 'str_number', 'str_number_full',
                    'cadastral_number', 'gis_uid',
                ).as_pymongo()}
            if not areas:  # помещения не найдены?
                self.warning("Отсутствуют нежилые помещения управляемого"
                    f" {self.provider_name} дома {self.house_address}")
                return  # нечего сохранять

            non_residential_premises: dict = {non.PremisesNum:  # № помещения
                    non for non in non_residential_premises
                if non.TerminationDate is None}  # неаннулированные помещения

            # WARN кадастровые номера помещений есть не всегда
            cadastral_numbers: dict = {non.CadastralNumber:  # : str
                    non.PremisesNum for non in non_residential_premises.values()
                if not non.No_RSO_GKN_EGRP_Registered  # Нет связи с ГКН/ЕГРП
                    and not non.No_RSO_GKN_EGRP_Data}  # Нет данных для связи
            # сопоставление уникальных номеров ГИС ЖКХ помещений с порядковыми
            unique_numbers: dict = {non.PremisesUniqueNumber:  # : str
                non.PremisesNum for non in non_residential_premises.values()}

            area_guids: dict = self.mapped_guids(GisObjectType.AREA, *areas)

            for area_id, area in areas.items():  # сохраняемые помещения
                area_guid: GUID = area_guids.get(area_id)
                area_guid.premises_id = self.house_id  # WARN привязка к дому

                existing: str = (area.get('cadastral_number') or '').strip()
                gis_uid: str = (area.get('gis_uid') or '').strip()  # Уникальный

                # Ищем по кадастровому номеру
                if existing and existing in cadastral_numbers:
                    area_number = cadastral_numbers[existing]
                # Ищем по ИЖКУ
                elif gis_uid and gis_uid in unique_numbers:
                    area_number = unique_numbers[gis_uid]
                # Ищем по номеру
                elif area['str_number'] in non_residential_premises:
                    area_number = area['str_number']  # с литерой
                else:  # некорректный номер помещения (39Н)?
                    # Получаем номер с дефисами
                    fixed_number = get_fixed_number(area['str_number'])
                    # Получаем номер с литерой и дефисами
                    number_with_hyphens = add_hyphen_before_last_N(fixed_number)

                    # Ищем по номеру в non_residential_premises
                    if fixed_number in non_residential_premises:
                        area_number = fixed_number
                    else:
                        area_number = number_with_hyphens

                non_resident = non_residential_premises.pop(
                    area_number, None  # по номеру помещения
                )  # WARN извлекаем полученные данные

                area_guid.number = area_number  # : str
                area_guid.desc = area.get('str_number_full') or \
                    f"пом. {area['str_number']}"

                # TODO в нежилых помещениях комнат нет?

                if not non_resident:  # помещение не найдено?
                    self.failure(area_guid, "Помещение отсутствует в ГИС ЖКХ")
                elif non_resident.TerminationDate:  # помещение аннулировано?
                    self.annulment(area_guid,
                        non_resident.TerminationDate, non_resident.PremisesGUID)
                else:  # получены данные ГИС ЖКХ помещения!
                    self.success(area_guid, non_resident.PremisesGUID,
                        unique=non_resident.PremisesUniqueNumber)
                    Area.update_gis_data(area_guid.object_id,
                        non_resident.PremisesUniqueNumber)

        def _store(self, export_result):  # exportHouseResultType

            if export_result.LivingHouse:  # TODO Жилой дом?
                raise NotImplementedError("Не предусмотрено"
                    " сохранение данных жилого (частного) дома")

            apartment_house = export_result.ApartmentHouse  # МКД
            basic = apartment_house.BasicCharacteristicts

            gis_house_guid: UUID = as_guid(basic.FIASHouseGuid)

            if self.fias_guid != gis_house_guid:  # получен иной идентификатор?
                if self.cadastral_number != basic.CadastralNumber:
                    raise NoGUIDError("Данные дома с иным идентификатором"
                        " ФИАС будут сохранены при совпадении кадастрового"
                        f" номера с {basic.CadastralNumber}")
                self.warning(f"Полученный идентификатор ФИАС {gis_house_guid}"
                    f" не совпадает с переданным {self.fias_guid}")

            # сопоставляем (новый) идентификатор ГИС ЖКХ дома операции
            house_guid: GUID = \
                self.mapped_guid(GisObjectType.HOUSE, self.house_id)
            house_guid.desc = self.house_address  # записываем адрес дома

            self.success(house_guid,
                gis_house_guid,  # идентификатор ГИС ЖКХ дома
                unique=export_result.HouseUniqueNumber)  # уникальный номер
            House.update_gis_data(self.house_id,
                export_result.HouseUniqueNumber)  # обновляем уникальный номер

            self._store_entrances(apartment_house)  # сохраняем подъезды и лифты
            # self.flush_guids()  # сохраняем данные дома, подъездов и лифтов

            self._store_premises(apartment_house.NonResidentialPremises)
            self._store_premises_w_rooms(apartment_house.ResidentialPremises)

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            request_fias_guid: str = request_data.get('FIASHouseGuid')

            if not request_fias_guid:  # идентификатора нет в запросе?
                if not self.fias_guid:  # отсутствует идентификатор ФИАС?
                    raise NoGUIDError("Отсутствует идентификатор ФИАС дома")
                request_data['FIASHouseGuid'] = self.fias_guid  # : UUID
            elif not self.fias_guid:  # отсутствует идентификатор ФИАС дома?
                request_data['FIASHouseGuid'] = as_guid(request_fias_guid)
            else:  # идентификатор ФИАС дома в запросе!
                assert self.fias_guid == as_guid(request_fias_guid), \
                    "Идентификатор ФИАС дома не соответствует запросу"
                request_data['FIASHouseGuid'] = self.fias_guid  # : UUID

            return True

        def _house_objects(self, *area_id_s: ObjectId) -> tuple:

            assert not self.house_id, "Идентификатор дома" \
                " операции не нуждается в определении"

            if not area_id_s:  # помещения не определены?
                return super()._house_objects()  # управляемые организацией дома

            house_areas: dict = {}

            for area in Area.objects(__raw__={
                '_id': {'$in': area_id_s},  # WARN без ограничений
            }).only('house').as_pymongo():
                house_areas.setdefault(
                    area['house']['_id'], []
                ).append(area['_id'])

            self.log(info=f"Загружаются данные ГИС ЖКХ {len(area_id_s)}"
                f" расположенных в {len(house_areas)} домах помещений")

            for house_id, area_ids in house_areas.items():
                yield house_id, area_ids  # помещения одного дома

    class importHouseUOData(SystemHouseDataLoader, HouseManagementOperation):
        """Импорт данных дома для полномочия УО"""

        IS_HOMELESS = True  # операция без (загрузки данных ГИС ЖКХ) дома

        VERSION = "11.0.10.1"
        ELEMENT_LIMIT = 100

        HOUSE_STATE_NSI_CODE = {
            'emergency': 1, 'good': 2, 'old': 3, 'unknown': 4
        }  # HouseEngineeringStatusTypes

        TIME_ZONE_NSI_CODE = {
            'Калининград': 1, 'Москва': 2, 'Симферополь': 3,
            'Волгоград': 4, 'Самара': 5, 'Екатеринбург': 6,
            'Новосибирск': 7, 'Омск': 8, 'Красноярск': 9,
            'Новокузнецк': 10, 'Иркутск': 11, 'Чита': 12,
            'Якутск': 13, 'Хандыга': 14, 'Владивосток': 15,
            'Магадан': 16, 'Сахалин': 17, 'Усть-Нера': 18,
            'Среднеколымск': 19, 'Камчатка': 20, 'Анадырь': 21
        }

        @property
        def object_type(self):

            return GisObjectType.AREA  # WARN константа

        @property
        def description(self) -> str:

            return f"{len(self.object_ids)} помещений дома" \
                f" с ид-ом ФИАС {self.fias_guid}"

        def _store(self, common_results: list):
            """
            Сохранение полученных данных ГИС ЖКХ дома и помещений

            Идентификатор ГИС ЖКХ и ФИАС выгруженного первый раз дома совпадают
            Уникальный номер (никогда) не меняется после внесения изменений
            """
            for result in common_results:
                guid: GUID = self._mapped_guids[result.TransportGUID]

                if guid.tag == GisObjectType.HOUSE:  # дом?
                    # TODO OGFImportStatusType - связь с ГКН/ЕГРП
                    self.success(guid, self.fias_guid,  # ид. ФИАС дома
                        # result.GUID - внутренний ид. ГИС ЖКХ дома (НЕ ФИАС)
                        unique=result.UniqueNumber)  # уникальный номер
                    House.update_gis_data(guid.object_id, result.UniqueNumber)
                elif guid.tag == GisObjectType.AREA:  # помещение?
                    self.success(guid, result.GUID, unique=result.UniqueNumber)
                    Area.update_gis_data(guid.object_id, result.UniqueNumber)
                else:  # Porch, Lift
                    self.success(guid, result.GUID, unique=result.UniqueNumber)

        def _apartment_house(self) -> dict:

            # WARN сопоставляем идентификатор ГИС ЖКХ дома операции
            house_guid: GUID = \
                self.mapped_guid(GisObjectType.HOUSE, self.house_id)
            house_guid.desc = self.house_address  # записываем адрес дома

            house_floor_count = max(porch['max_floor']
                for porch in self.house.porches)
            min_floor_count = min(porch['min_floor']
                for porch in self.house.porches)
            underground_floor_count = 0  # TODO нет данных о подземных этажах

            house_total_square = (
                self.house.area_overall or self.house.area_total
                or 0  # TODO отсутствует общая площадь?
            )

            house_used: datetime = self.house.service_date \
                or self.house.build_date
            assert house_used, "Год ввода дома в эксплуатацию не указан"

            house_state: dict = nsiRef.common(24,  # Состояние дома (НСИ 24)
                self.HOUSE_STATE_NSI_CODE[
                    self.house.engineering_status
                    or 'good'  # TODO по умолчанию "Исправный"
                ])

            life_cycle_stage = nsiRef.common(338, 1)  # TODO 1 - Эксплуатация

            olson_timezone = nsiRef.common(32,  # Часовая зона (НСИ 31/32)
                self.TIME_ZONE_NSI_CODE.get(self.house.gis_timezone, 2))  # MSK

            cultural_heritage = self.house.is_cultural_heritage or False

            basic_characteristics = dict(
                FIASHouseGuid=self.fias_guid,  # Идентификатор дома по ФИАС
                TotalSquare=house_total_square,  # Общая площадь здания
                FloorCount=house_floor_count or 1,  # Количество этажей дома
                UsedYear=house_used.year,  # Год ввода дома в эксплуатацию
                State=house_state,  # Состояние дома
                LifeCycleStage=life_cycle_stage,  # Стадия жизненного цикла
                OlsonTZ=olson_timezone,  # Часовая зона расположения дома
                CulturalHeritage=cultural_heritage,  # Об. культ. наследия?
            )

            if not self.house.OKTMO:
                self.warning(f"Отсутствует код ОКТМО дома {self.house_address}")
            else:  # ОбщеРос. Классификатор Территорий Муниципальных Образований
                basic_characteristics['OKTMO'] = {'code': self.house.OKTMO}

            if self.cadastral_number:  # имеется кадастровый номер дома?
                basic_characteristics['CadastralNumber'] = self.cadastral_number
            else:  # Связь с ГКН/ЕГРП отсутствует!
                basic_characteristics['No_RSO_GKN_EGRP_Registered'] = True

            create_or_update: str = ('ApartmentHouseToUpdate'
                if house_guid or  # новый дом?
                    not self.is_first  # последующая операция?
                else 'ApartmentHouseToCreate')

            return {create_or_update: house_guid.as_req(
                    BasicCharacteristicts=basic_characteristics,
                    UndergroundFloorCount=underground_floor_count,
                    MinFloorCount=min_floor_count or 1)}

        def _infrastructure(self, *porch_id_s: dict) -> dict:

            infrastructure = defaultdict(list)  # подъезды и лифты дома

            for porch_id in porch_id_s or self._house_porches:  # или все ид-ы
                porch_guid: GUID = \
                    self.mapped_guid(GisObjectType.PORCH, porch_id)

                porch: Porch = self._house_porches.get(porch_id)
                if not porch:  # подъезд не найден в доме?
                    self.failure(porch_guid, "Подъезда помещения нет в доме")
                    continue  # пропускаем некорректный подъезд

                porch_guid.number = str(porch.number or 1)

                entrance_data = dict(
                    EntranceNum=porch_guid.number,  # Номер подъезда
                    StoreysCount=porch.max_floor,  # Этажность
                    InformationConfirmed=True)  # Инф. подтверждена поставщиком!

                if porch.build_date:  # Год постройки?
                    entrance_data['CreationYear'] = porch.build_date.year

                infrastructure['EntranceToUpdate' if porch_guid
                    else 'EntranceToCreate'].append(porch_guid.as_req(
                        'EntranceGUID',  # элемента не будет без идентификатора
                        **entrance_data))

                # house.lift_count и porches.has_lift - недостоверны!
                for lift in porch.lifts:
                    assert isinstance(lift, Lift)

                    lift_guid: GUID = \
                        self.mapped_guid(GisObjectType.LIFT, lift.id)

                    # 5013-Грузовой, 5012-Грузопассажирский, 5011-Пассажирский
                    lift_type = 5011 if re_match(  # только в первой строке
                        r'пассажирский', lift.desc, IGNORECASE
                    ) or int(lift.capacity or 0) < 1000 else 5013

                    match = re_match(r'заводской №\s*(.*)', lift.desc,
                        IGNORECASE)  # нулевая группа - совпадение полностью
                    lift_guid.number = match.group(1) if match else lift.number
                    if not lift_guid.number:  # лифт не имеет номера?
                        self.failure(lift_guid, "Номер лифта не определен")
                        # в том числе не найден в описании "заводской №"
                        continue  # пропускаем без номера

                    lift_data = dict(
                        EntranceNum=porch_guid.number,  # Номер подъезда
                        FactoryNum=lift_guid.number,  # Заводской номер
                        Type=nsiRef.common(192, lift_type),
                        # TODO OGFData  # Данные ОЖФ
                    )

                    infrastructure[
                        'LiftToUpdate' if lift_guid else 'LiftToCreate'
                    ].append(lift_guid.as_req('LiftGUID', **lift_data))

            return infrastructure

        def _common_premise_data(self, area: dict) -> dict:
            """Общие данные жилых (квартир) и нежилых помещений"""
            premise_data = dict(  # TODO OGFData
                PremisesNum=self._area_guid.number,
                TotalArea=area['area_total'],  # только с общей площадью!
                InformationConfirmed=True)

            cadastral_number: str = area.get('cadastral_number')  # или None
            if cadastral_number:
                premise_data['CadastralNumber'] = cadastral_number
            else:
                premise_data['No_RSO_GKN_EGRP_Registered'] = True

            return premise_data

        def _premises_rooms(self, area: dict) -> dict:

            _rooms = defaultdict(list)  # комнаты помещения

            for room in area.get('rooms') or []:
                room_guid: GUID = \
                    self.mapped_guid(GisObjectType.ROOM, room['_id'])

                if not room.get('number'):  # комната с номером 0 или без него
                    self.failure(room_guid, "Комната имеет некорректный номер")
                    continue  # пропускаем комнату

                room_guid.number = str(room['number'])  # комнаты
                room_guid.desc = "кв. " \
                    + area.get('str_number') or str(area['number'])  # квартиры

                room_data = dict(RoomNumber=room_guid.number,
                    Square=room['square'],  # Площадь комнаты
                    InformationConfirmed=True)

                cadastral_number = (room.get('cadastral_number') or '').strip()
                if cadastral_number:  # определен кадастровый номер?
                    room_data['CadastralNumber'] = cadastral_number
                else:  # кадастровый номер отсутствует!
                    room_data['No_RSO_GKN_EGRP_Registered'] = True

                if room_guid:  # комната уже выгружалась?
                    _rooms['LivingRoomToUpdate'].append(
                        room_guid.as_req('LivingRoomGUID', **room_data))
                else:  # комната еще не выгружалась!
                    _rooms['LivingRoomToCreate'].append(
                        room_guid.as_req(**room_data))

            return _rooms

        def _residential_premise(self, area: dict):

            if not self.house.porches:  # в доме нет подъездов?
                area_porch = None
            elif area.get('porch'):  # помещение имеет ид. подъезда?
                area_porch = self._house_porches.get(area['porch'])
            # идентификатор подъезда помещения не задан
            elif len(self.house.porches) == 1:  # единственный подъезд?
                area_porch = self.house.porches[0]
                if area_porch['number']:  # подъезд с номером (НЕ null / 0)?
                    area_porch = None  # недостоверные данные!
            else:  # подъезд не определен!
                area_porch = None

            residential_data: dict = self._common_premise_data(area)

            # НСИ 30: 1 - Отдельная квартира, 2 - Коммуналка, 3 - Общежитие
            residential_data['PremisesCharacteristic'] = \
                nsiRef.common(30, 2 if area.get('is_shared') else 1)

            living_area = area.get('area_living') or None
            if living_area:  # определена жилая площадь?
                residential_data['GrossArea'] = living_area
            else:  # отсутствует значение жилой площади!
                residential_data['NoGrossArea'] = True

            if area_porch:  # определен подъезд помещения?
                residential_data['EntranceNum'] = str(area_porch['number'] or 1)
            else:  # подъезд не определен!
                residential_data['HasNoEntrance'] = True

            residential_premise: dict = {'ResidentialPremisesToUpdate'
                    if self._area_guid else 'ResidentialPremisesToCreate':
                self._area_guid.as_req('PremisesGUID', **residential_data)}

            if area.get('is_shared'):  # коммунальная квартира?
                residential_premise.update(self._premises_rooms(area))  # комн.

            return residential_premise

        def _compose(self) -> dict:

            # TODO LivingHouse  # Жилой дом
            apartment_house: dict = self._apartment_house()  # данные МКД

            self._house_porches = {porch.id: porch
                for porch in self.house.porches}  # подъезды дома

            if (not self.object_ids or  # нет идентификаторов помещений?
                    self.object_ids[0] == self.house_id):  # получен ид. дома?
                self.log(info="Выгружаются данные (инфраструктуры)"
                    f" дома {self.house_address}")

                # добавляем данные всех подъездов и лифтов дома
                apartment_house.update(self._infrastructure())

                return dict(  # без помещений
                    ApartmentHouse=apartment_house,  # дом с инфраструктурой
                    InheritMissingValues=None)  # для InformationConfirmed

            self.log(info=f"Формируются данные {len(self.object_ids)}"
                f" помещений (квартир) дома {self.house_address}")

            # загружаем идентификаторы ГИС ЖКХ помещений (квартир)
            area_guids: dict = \
                self.mapped_guids(GisObjectType.AREA, *self.object_ids)

            premises = defaultdict(list)  # данные помещений дома
            porch_ids = set()  # идентификаторы подъездов

            for area in Area.objects(id__in=self.object_ids).as_pymongo():
                self._area_guid: GUID = area_guids[area['_id']]
                # номер помещения в соответствии с форматом Росреестра
                self._area_guid.number = get_fixed_number(area['str_number'])

                if self._is_skippable(self._area_guid):  # не обновлять?
                    continue  # пропускаем выгруженное помещение

                if area.get('area_total') is None:  # отсутствует общая площадь?
                    self.failure(self._area_guid,
                        "Общая площадь помещения не указана")
                    continue  # не выгружаем без общей площади (0.0 допускается)

                if area.get('porch'):  # помещение имеет ид. подъезда?
                    porch_ids.add(area['porch'])  # добавляем ид. в набор

                # region ЖИЛОЕ ПОМЕЩЕНИЕ (КВАРТИРА)
                if AreaType.LIVING_AREA in area['_type']:  # жилое помещение?
                    self._area_guid.desc = f"кв. {area['str_number']}"

                    residential_premise: dict = self._residential_premise(area)
                    if residential_premise:  # получены данные квартиры?
                        premises['ResidentialPremises'] \
                            .append(residential_premise)
                    continue  # к следующему (жилому) помещению
                # endregion ЖИЛОЕ ПОМЕЩЕНИЕ (КВАРТИРА)

                # region НЕЖИЛОЕ ПОМЕЩЕНИЕ
                self._area_guid.desc = f"пом. {area['str_number']}"

                non_residential_data = self._common_premise_data(area)

                non_residential_data['IsCommonProperty'] = \
                    bool(area.get('common_property'))  # общее имущество?

                non_residential_premise = self._area_guid.as_req('PremisesGUID',
                    **non_residential_data)

                create_or_update: str = 'NonResidentialPremiseToUpdate' \
                    if self._area_guid else 'NonResidentialPremiseToCreate'
                premises[create_or_update].append(non_residential_premise)
                # endregion НЕЖИЛОЕ ПОМЕЩЕНИЕ

            if not premises:  # отсутствуют данные помещений?
                raise NoRequestWarning("Отсутствуют подлежащие"
                    " выгрузке в ГИС ЖКХ помещения")
            apartment_house.update(premises)  # добавляем данные помещений

            # добавляем данные подъездов и лифтов выгружаемых помещений дома
            apartment_house.update(self._infrastructure(*porch_ids))

            # InheritMissingValues не указывается для InformationConfirmed
            return dict(ApartmentHouse=apartment_house)  # дом и помещения

        def binded_areas(self):
            """
            Обслуживаемые организацией помещения дома
            """
            with self.load_context:  # WARN сохраняем только в случае ошибки
                binded_area_ids: list = Area.objects(__raw__={
                    'house._id': self.house_id, 'is_deleted': {'$ne': True},
                    **Area.get_binds_query(self.binds_permissions, True),
                }).distinct('id')  # ид-ы обслуживаемых помещений дома
                if not binded_area_ids:
                    raise NoDataError("Отсутствуют обслуживаемые"
                        f" организацией помещения в доме {self.house_address}")

            self.log(info=f"Выгружаются данные {len(self.object_ids)}"
                f" помещений дома {self.house_address}")

            self(*binded_area_ids)

    class exportAccountData(ExportOperation):
        """Получить перечень лицевых счетов"""

        VERSION = "10.0.1.1"
        ELEMENT_LIMIT = 500

        _account_type = None  # тип лицевых счетов

        @property
        def description(self) -> str:
            if self.object_ids:
                return f"Загрузка {len(self.object_ids)} {get_account_type_name(self.object_type)}"
            else:
                return f"ФИАС: {self.request.get('FIASHouseGuid') or 'ОТСУТСТВУЕТ'}"

        @property
        def account_type_name(self) -> str:
            """Название текущего типа ЛС"""
            return get_account_type_name(self._account_type)

        @property
        def by_house(self) -> bool:
            """Тип выгрузки. По дому или по списку ЛС"""
            return True if not self.object_ids else False

        def _store_tenant(self, tenant: dict):
            """exportAccountResultType"""
            account_number: str = (tenant['number'] or '').strip()
            assert len(account_number) == 13, "Некорректный номер (ЛС) жильца"

            account_guid: GUID = self._account_guids[tenant['_id']]
            tenant_area: dict = tenant.get('area')  # помещение ЛС
            if tenant_area is not None:
                account_guid.desc = tenant_area.get('str_number_full') or \
                    tenant_area['str_number']  # номер помещения как описание

            exported = self._results.get(account_number)
            if not exported:  # отсутствует в полученных данных?
                self.missing(account_guid)  # подлежит выгрузке в ГИС ЖКХ
                return
            elif exported.Closed:  # лицевой счет закрыт?
                self.annulment(account_guid,
                     exported.Closed.CloseDate, exported.AccountGUID)
                return
            else:  # получены данные ГИС ЖКХ лицевого счёта!
                self.success(
                    guid=account_guid,
                    gis=exported.AccountGUID,
                    unique=exported.ServiceID,  # идентификатор ЖКУ
                    number=exported.UnifiedAccountNumber)  # ЕЛС

            unified_number: str = exported.UnifiedAccountNumber
            if tenant.get('gis_uid') != unified_number or (  # ЕЛС?
                exported.isUOAccount and
                    tenant.get('hcs_uid') != exported.ServiceID  # ИЖКУ?
            ):
                self.log(warn="Выполняется обновление номера ЕЛС"
                    f" {sb(tenant.get('gis_uid'))} на {unified_number}"
                    f" и идентификатора ЖКУ {sb(tenant.get('hcs_uid'))}"
                    f" на {exported.ServiceID} ЛС №{account_number}")
                Tenant.update_gis_data(tenant['_id'],  # обновляем документ
                    unified_number, exported.ServiceID)

        def _store(self, export_results: list):

            # распределяем полученные данные ГИС ЖКХ по типам
            typed_results: dict = {}  # 'ObjectType': 'AccountNumber': Result
            for current in export_results:
                account_number: str = (current.AccountNumber or '').strip()
                if len(account_number) not in {11, 13}:
                    self.log(warn="Данные ЛС с (некорректным) номером"
                        f" {account_number} сохранению не подлежат")
                    continue

                account_type: str = (
                    GisObjectType.UO_ACCOUNT if current.isUOAccount else
                    GisObjectType.CR_ACCOUNT if current.isCRAccount else
                    GisObjectType.TKO_ACCOUNT if current.isTKOAccount else
                    GisObjectType.RSO_ACCOUNT if current.isRSOAccount else
                    GisObjectType.RC_ACCOUNT if current.isRCAccount else
                    GisObjectType.OGV_OMS_ACCOUNT if current.isOGVorOMSAccount
                    else None
                )
                assert account_type, f"Тип ЛС №{account_number} не определен"
                results: dict = typed_results.setdefault(account_type, {})

                previous = results.get(account_number)  # или None
                closed = current.Closed.CloseDate if current.Closed else None
                if not previous or not closed or (  # или закрыт после прежнего?
                    previous.Closed and previous.Closed.CloseDate < closed
                ):  # WARN заменяем закрытые ЛС созданными с номером или новыми
                    results[account_number] = current
                elif closed:  # прежние данные закрытого ЛС!
                    self.log(warn="Получены (исторические) данные закрытого"
                        f" {fmt_period(closed, True)} ЛС №{account_number}")
            provider_ids = [self.provider_id]
            if self.relation_id:
                provider_ids.append(self.relation_id)
            typed_tenants: dict = get_typed_accounts(*self.object_ids, **{
                'account.area.house._id': self.house_id,  # индекс
                # получатель платежа
                'owner': {'$in': provider_ids},
                'doc.status': {'$in': CONDUCTED_STATUSES},  # проведенные
            })  # при наличии идентификаторов остальные аргументы отбрасываются
            if not typed_tenants:  # жильцы с начислениями не найдены?
                untyped_tenants: list = \
                    get_responsible_tenants(
                        provider_ids,
                        self.house_id
                    )
                if untyped_tenants:
                    typed_tenants = {GisObjectType.UO_ACCOUNT: untyped_tenants}
                    self.log(f"Загружены идентификаторы {len(untyped_tenants)}"
                        " ответственных квартиросъемщиков без начислений:\n\t"
                            + ', '.join(map(str, untyped_tenants)))

            for self._account_type, tenant_ids in typed_tenants.items():
                if self._account_type not in typed_results:  # нет ЛС типа?
                    if self.by_house:
                        self.warning(f"Отсутствуют данные ГИС ЖКХ {len(tenant_ids)}"
                            f" {sb(self.account_type_name)} управляемого"
                            f" {self.provider_name} дома {self.house_address}")
                    continue

                self._results: dict = typed_results[self._account_type]
                self.log(f"Получены данные ГИС ЖКХ {len(self._results)}"
                    f" ЛС типа {sb(self._account_type)}:\n\t"
                        + ', '.join(number for number in self._results))

                # загружаем идентификаторы ГИС ЖКХ лицевых счетов данного типа
                self._account_guids: dict = \
                    self.mapped_guids(self._account_type, *tenant_ids)

                tenants = Tenant.objects(__raw__={
                    '_id': {'$in': tenant_ids},  # : list
                    'is_deleted': {'$ne': True},
                }).only(
                    'number', 'gis_uid', 'hcs_uid', 'area'
                ).as_pymongo()  # : QuerySet
                self.log(f"Подлежат сохранению данные ГИС ЖКХ {tenants.count()}"
                    f" {self.account_type_name} управляемого"
                    f" {self.provider_name} дома {self.house_address}")

                for tenant in tenants:  # данные жильцов
                    self._store_tenant(tenant)
                self.flush_guids()  # Сохраняем данные по типам (UO, CR и т.д.)

        def _import(self):

            _import = HouseManagement.importAccountData(  # выгружаем в ГИС ЖКХ
                self.provider_id, self.house_id,  # лицевые счета (жильцов) дома
                update_existing=False  # отсутствующие (без идентификаторов)
            )
            self.lead(_import)  # будет выполнена после завершения текущей

            assert not _import.is_saved, \
                "Запись о последующей операции не должна быть сохранена"
            _import.prepare(*self._missing_ids)  # WARN сохраняем последующую

            self.save()  # WARN сохраняем предшествующую запись об операции

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if not request_data.get('FIASHouseGuid') and not object_id_s:
                request_data['FIASHouseGuid'] = self.fias_guid  # : UUID

            self.log(info="Загружаются данные ЛС управляемого"
                f" {self.provider_name} дома {self.house_address}")

            return True

        def _load_accounts_data(self, *tenant_id_s: ObjectId):
            self._typed_tenant_guids: dict = {}  # 'AccountType': TenantId: GUID
            typed_accounts: dict = get_typed_accounts(*tenant_id_s)
            assert typed_accounts, f"Загрузка возможна только по ЛС с начислениями"

            for account_type, typed_ids in typed_accounts.items():
                if (len(tenant_id_s) > len(typed_ids) and  # без начислений?
                        account_type == GisObjectType.UO_ACCOUNT):  # ЛС КУ?
                    untyped_ids: list = [
                        _id for _id in tenant_id_s if _id not in typed_ids
                    ]  # без (направления платежа) начислений
                    typed_ids += untyped_ids

                    self.warning(f"Добавлены в загрузку {len(untyped_ids)} "
                                 + get_account_type_name(account_type) +
                                 " без (направлений платежа) начислений")
                self._typed_tenant_guids[account_type] = typed_ids

        def prepare(self, *tenant_id_s: ObjectId):
            """Подготовка к загрузке ЛС по направлению платежа"""
            if not tenant_id_s:  # если не указаны жильцы
                super().prepare() # без аргументов - идентификаторов жильцов
                return

            self._load_accounts_data(*tenant_id_s) #  загружаем данные по ЛС

            for account_type, typed_ids in self._typed_tenant_guids.items():
                super().prepare(*typed_ids, object_type=account_type)

        def _account_data(self, tenant: dict):
            """
            Данные лицевого счета

            AccountGUID, ServiceId, UnifiedAccountNumber
            """
            # В будущем может понадобится еще AccountGUID или ServiceID
            unified_account_number: str = tenant.get('gis_uid')  # WARN null=True
            service_id: str = tenant.get('gis_hcs')  # WARN null=True
            account_guid = None

            return {'UnifiedAccountNumber' : unified_account_number}

        def _compose(self) -> dict:
            # Если выгрузка по дому - нет необходимости дополнять запрос
            if self.by_house:
                return {}

            # Получаем список жильцов
            tenants = Tenant.objects(__raw__={
                '_id': {'$in': self.object_ids},
            }).exclude(
                'settings', 'b_settings', 'coefs', 'tasks',
                'old_numbers', '_binds', 'place_origin', 'rooms',
            ).as_pymongo()

            # Извлекаем ЕЛС и формируем множество уникальных значений
            unified_account_numbers = {
                item['UnifiedAccountNumber'] for item in
                self._produce(self._account_data, tenants)
                if item.get('UnifiedAccountNumber')
            }
            assert unified_account_numbers, \
                "У выгружаемых жильцов отсутсвуют ЕЛС"

            # Возвращаем результат в требуемом формате
            return {'UnifiedAccountNumber': list(unified_account_numbers)}

        def house_tenants(self):
            """Лицевые счета всех ответственных квартиросъемщиков"""

            with self.load_context:  # WARN сохраняем только в случае ошибки
                provider_ids = [self.provider_id]
                if self.relation_id:
                    provider_ids.append(self.relation_id)

                responsible_tenant_ids: list = get_responsible_tenants(
                    provider_ids,
                    self.house_id,
                )

                if not responsible_tenant_ids:
                    raise NoDataError("Отсутствуют подлежащие загрузке"
                                      " в ГИС ЖКХ квартиросъемщики")

            self.log(info=f"Загружаются данные "
                          f"{len(responsible_tenant_ids)} "
                          f"ответственных квартиросъемщиков дома "
                          f"{self.house_address}")

            self(*responsible_tenant_ids)

    class importAccountData(HouseManagementOperation):
        """
        Передать данные лицевых счетов

        При повторной выгрузке без ид. ГИС ЖКХ возвращается ошибка:
        Найден актуальный лицевой счет с номером и набором помещений
        """
        VERSION = "10.0.1.1"
        ELEMENT_LIMIT = 100

        REQUIREMENTS = {
            GisObjectType.LEGAL_ENTITY: 30,  # % загруженных ЮЛ от числа ЛС
            GisObjectType.AREA: 70,
        }

        REAL_PAYER_NAME: bool = False  # True - ФИО, False - "Жилец кв. 1"

        @property
        def description(self) -> str:

            assert self.object_type, "Тип выгружаемых ЛС не определен"

            return f"{len(self.object_ids)} " \
                f"{get_account_type_name(self.object_type)}"

        def _store(self, common_results: list):

            for result in common_results:
                # TODO result.UniqueNumber (спонтанно) может быть не пустым?
                imported = result.ImportAccount  # : ImportAccount(Type)

                account_guid: GUID = self._mapped_guids[result.TransportGUID]

                if account_guid.deleted:  # закрытый ЛС?
                    self.annulment(account_guid, gis=result.GUID)
                    continue  # к следующему результату

                self.success(account_guid, result.GUID,
                    # номер ЛС не сохраняется (№ помещения в описании)
                    unique=imported.ServiceID,  # ИЖКУ
                    number=imported.UnifiedAccountNumber)  # ЕЛС

                Tenant.update_gis_data(account_guid.object_id,
                    imported.UnifiedAccountNumber, imported.ServiceID)

        def _account_data(self, tenant: dict):
            """
            Данные лицевого счета

            Ответственный квартиросъемщик / Плательщик / Жилец
            """
            account_guid: GUID = self._typed_guids.get(tenant['_id'])
            if self._is_skippable(account_guid):  # не обновлять?
                return  # пропускаем выгруженный ЛС

            tenant_number: str = tenant.get('number')  # WARN null=True
            if not tenant_number:
                self.failure(account_guid, "Отсутствует номер лицевого счета")
                return  # пропускаем ЛС без номера

            tenant_family: dict = tenant.get('family') or {}  # есть НЕ всегда!
            # плательщик (householder) может отсутствовать ~ коммерческое жилье?
            householder_id = tenant_family.get('householder') or tenant['_id']

            area_id: ObjectId = tenant['area']['_id']  # идентификатор помещения
            area_guid: GUID = self._area_guids.get(area_id)  # или None
            if not area_guid:  # идентификатор ГИС ЖКХ помещения не загружен?
                self.failure(account_guid,
                    "Не загружен идентификатор ГИС ЖКХ помещения")
                return  # пропускаем без идентификатора помещения

            area: dict = self._areas[area_id]  # существующее помещение ЛС
            is_residential: bool = AreaType.LIVING_AREA in area['_type']

            area_number: str = area.get('str_number_full') \
                or f"{'кв.' if is_residential else 'пом.'} {area['str_number']}"

            account_guid.desc = area_number  # "пом. 1Н"

            if area['house']['_id'] != self.house_id:  # иной дом помещения?
                self.failure(account_guid, "Иной идентификатор дома помещения")
                return  # TODO пропускаем ЛС "чужого" дома
            if self.options.get('as_private'):
                tenant['_type'][0] = TenantType.PRIVATE_TENANT
                tenant['entity'] = None
            if TenantType.PRIVATE_TENANT in tenant['_type']:  # ФЛ
                if tenant.get('entity'):
                    self.failure(account_guid, "Присутствует идентификатор ЮЛ")
                    return  # пропускаем ФЛ с идентификатором ЮЛ
                payer_info: dict = {'Ind': dict(
                    Sex={
                        GenderType.MALE: 'M', GenderType.FEMALE: 'F'
                    }.get(tenant.get('sex')),  # Необязательное
                    DateOfBirth=tenant.get('birth_date'),  # Необязательное
                )}

                if self.REAL_PAYER_NAME:  # выгружаем ФИО?
                    payer_info['Ind']['Surname'] = tenant.get(
                        'last_name', 'Не определено'
                    )
                    payer_info['Ind']['FirstName'] = tenant.get(
                        'first_name', 'Не определено'
                    )
                    payer_info['Ind']['Patronymic'] = tenant.get(
                        'patronymic_name', 'Не определено'
                    )
                else:  # не выгружаем ФИО!
                    payer_info['Ind']['Surname'] = \
                        "Жилец" if is_residential else "Владелец"
                    payer_info['Ind']['FirstName'] = area_number
                    payer_info['Ind']['Patronymic'] = None
            elif TenantType.LEGAL_TENANT in tenant['_type']:
                if not tenant.get('entity'):
                    self.failure(account_guid,
                        "Отсутствует привязка ЮЛ к организации")
                    return  # пропускаем без идентификатора ЮЛ
                if not tenant.get('ogrn'):  # нет ОГРН ЮЛ?
                    self.failure(account_guid,
                        "Отсутствует реквизит (ОГРН) ЮЛ")

                entity_guid: GUID = self._entity_guids.get(tenant['entity'])
                if not entity_guid or not entity_guid.version:  # ид. версии
                    self.failure(account_guid,
                        "Отсутствует идентификатор ГИС ЖКХ ЮЛ")
                    return  # пропускаем без идентификатора ГИС ЖКХ

                payer_info = {'Org': {'orgVersionGUID': entity_guid.version}}
            else:  # не ФЛ и не ЮЛ?!
                self.failure(account_guid,
                    "Тип плательщика (ФЛ или ЮЛ) не определен")
                return  # пропускаем ЛС без плательщика

            accommodation = dict(
                PremisesGUID=area_guid.gis,  # Идентификатор ГИС ЖКХ помещения
                # FIASHouseGuid - Идентификатор дома по ФИАС
                # LivingRoomGUID - Идентификатор комнаты ГИС ЖКХ
            )  # Помещение

            account_type: dict = {f"is{self.object_type}": True}  # вид ЛС

            account_guid.deleted = None  # WARN сбрасываем признак аннулирования

            statuses: dict = tenant.get('statuses')  # состояние (ЛС) жителя
            if statuses:  # Проживает / Собственник / Зарегистрирован / Учет
                accounting: dict = statuses.get('accounting') or {}  # бух. учет
                opened: datetime = accounting.get('date_from')
                if not opened:  # не подлежит расчету?
                    self.warning("Дата начала учета лицевого счета"
                        f" №{tenant_number} не определена")
                closed: datetime = accounting.get('date_till') \
                    if not self.options.get('previous_month') \
                    else datetime.now() - relativedelta(months=1)
                if closed and self.options.get('export_closed'):  # выгружаем закрытые?
                    account_guid.gis = None  # представляем, как новый ЛС
                else:
                    if not is_between(later=closed):  # учет не ведется?
                        if not account_guid and not self.is_updating:
                            self.failure(account_guid,
                                "Закрытый ЛС не подлежит выгрузке в ГИС ЖКХ")
                            return  # пропускаем закрытый ЛС

                        account_type.update(Closed={
                            'CloseReason': nsiRef.common(22, 5),  # Причина, НСИ 22:
                            # 1 - Окончание действия договора соц. найма,
                            # 2 - Окончание договора аренды,
                            # 3 - Окончание договора найма,
                            # 4 - Окончание предоставления жил. пом. жилищным кооп.,
                            # 5 - Окончание права собственности,
                            # 6 - Перевод помещения в нежилое, 7 - Снос дома,
                            # 8 - Объединение ЛС, 9 - Изменение реквизитов ЛС,
                            # 10 - Ошибка ввода, 11 - Расторжение договора,
                            # 12 - Смена исполнителя ЖКУ,
                            # 13 -Переход исполнителя ЖКУ на самостоятельные расчеты.
                            'CloseDate': closed,
                        })  # ClosedAccountAttributesType
                        account_guid.deleted = closed  # аннулируется (в _store)
                        self.log(info=f"Лицевой счет №{tenant_number} с датой"
                            f" окончания учета {fmt_period(closed, True)}"
                            " подлежит закрытию в ГИС ЖКХ")

                ownership: dict = statuses.get('ownership') or {}  # собственник
                property_share: list = ownership.get('property_share') or [0, 1]
                # доля - числитель и знаменатель: [1, 1] - 100%, [0, 1] - нет
                if property_share[0] > 0:  # (со)владелец помещения?
                    assert property_share[1] > 0, \
                        "Некорректное значение (знаменателя) доли владения"
                    accommodation['SharePercent'] = round(
                        property_share[0] / property_share[1] * 100, 2
                    )  # : float
                elif area.get('is_shared'):  # коммунальная квартира?
                    self.warning(f"Доля владения (ЛС) жителя №{tenant_number}"
                        f" в коммунальной квартире {area_number} не определена")

            # договоры: Ресурсоснабжения, Социального найма, Обращения с ТКО
            # Если в ГИС размещены сведения о выбранном способе формирования
            # фонда кап. ремонта, то в основании ЛС (для КР) необходимо указать
            # Протокол общего собрания собственников.
            # Добавить Протокол ОСС как основание открытия существующего ЛС
            # можно выполнив импорт ЛС по AccountGUID.
            account_reasons = None  # None - действующий Устав / ДУ

            area_history: list = area.get('area_total_history')
            total_square: float = area.get('area_total') or 0.0 \
                if not area_history or len(area_history) == 1 \
                else area_history[-1]['value']  # последнее значение
            residential_square: float = area.get('area_living') or 0.0

            return account_guid.as_req('AccountGUID', **account_type,
                AccountReasons=account_reasons,  # Основания ЛС
                AccountNumber=tenant_number,  # : str
                TotalSquare=round(total_square, 4),  # Общая площадь для ЛС
                ResidentialSquare=residential_square,  # Жилая площадь
                HeatedArea=residential_square,  # TODO Отапливаемая площадь
                LivingPersonsNumber=self._area_living.get(householder_id, 0),
                Accommodation=[accommodation],
                PayerInfo=payer_info)

        def _get_householder_mates(self, *area_id_s: ObjectId) -> dict:

            from app.accruals.cipca.source_data.areas import get_mates

            return {householder: data['summary']['living']
                # householder: summary: { 'registered', 'living',... }
                for householder, data in get_mates(  # кол-во жильцов квартир
                    get_period(),  # поддерживается только первый день месяца
                    self.provider_id, areas=area_id_s
                ).items()}

        def _compose(self) -> dict:

            assert self.object_type in GUID.ACCOUNT_TAGS, \
                "Некорректный (неподдерживаемый) тип ЛС операции"

            self._areas: dict = {area['_id']: area  # данные помещений
                for area in Area.objects(__raw__={
                    '_id': {'$in': self._area_ids},
                }).only(
                    '_type', 'house', 'is_shared',
                    'number', 'str_number', 'str_number_full',
                    'area_total', 'area_total_history', 'area_living',
                ).as_pymongo()}

            self._area_living: dict = self._get_householder_mates(*self._areas)
            self.log("Количество жильцов с ответственным квартиросъемщиком:"
                + sp(f"{_id} = {_count}"
                    for _id, _count in self._area_living.items()))

            # загружаем идентификаторы ГИС ЖКХ лицевых счетов заданного типа
            self._typed_guids = \
                self.mapped_guids(self.object_type, *self.object_ids)

            tenants = Tenant.objects(__raw__={
                '_id': {'$in': self.object_ids},
                # TODO 'area.house._id' - дополнительный фильтр?
            }).exclude(
                'settings', 'b_settings', 'coefs', 'tasks',
                'old_numbers', '_binds', 'place_origin', 'rooms',
            ).as_pymongo()

            return {'Account':  # Множественное
                self._produce(self._account_data, tenants)}

        def _props(self, tenant: dict) -> dict:

            assert tenant.get('entity') and \
                TenantType.LEGAL_TENANT in tenant['_type'], \
                f"Лицевой счет {tenant['number']} не принадлежит ЮЛ"

            # WARN ИНН не является критерием поиска организации в ГИС ЖКХ
            props: dict = {}  # реквизиты (организации) ЮЛ

            ogrn: str = ogrn_or_not(tenant.get('ogrn'))  # или пустая строка
            if is_ogrn(ogrn):  # корректный ОГРН?
                props['ogrn'] = ogrn  # : str
                kpp: str = kpp_or_not(tenant.get('kpp'))  # или пустая строка
                if kpp:  # WARN без ОГРН не используется
                    props['kpp'] = kpp  # : str
                    self.log(f"Подлежит выгрузке ЛС {tenant['number']}"
                        f" ЮЛ {tenant['entity']} с ОГРН {ogrn} и КПП {kpp}")
                else:  # без филиалов?
                    self.log(info=f"Подлежит выгрузке ЛС {tenant['number']}"
                        f" ЮЛ {tenant['entity']} с ОГРН {ogrn}, но без КПП")
            else:  # TODO ОГРН в LegalTenant?
                self.warning("Некорректные реквизиты (ОГРН)"
                    f" юридического лица {tenant['str_name']}")

            return props

        def _preload(self):

            from app.gis.services.org_registry_common import OrgRegistryCommon

            entity_props: dict = {}  # идентификаторы и реквизиты ЮЛ
            self._area_ids: list = []  # идентификаторы помещений жителей дома

            for tenant in Tenant.objects(__raw__={
                '_id': {'$in': self.object_ids},  # WARN до распределения
                # TODO 'area.house._id': self.house_id,
            }).only(
                'number', 'area', 'entity', '_type',
                'ogrn', 'kpp', 'short_name', 'str_name',
            ).as_pymongo():
                area: dict = tenant.get('area')
                assert area is not None, \
                    f"Лицевой счет {tenant['_id']} не связан с помещением"
                if area['_id'] not in self._area_ids:
                    self._area_ids.append(area['_id'])
                if self.options.get('as_private'):
                    tenant['_type'][0] = TenantType.PRIVATE_TENANT
                    tenant['entity'] = None
                    tenant['ogrn'] = None
                entity_id: ObjectId = tenant.get('entity')

                if entity_id is not None:  # идентификатор ЮЛ?
                    if TenantType.LEGAL_TENANT in tenant['_type']:
                        entity_props[entity_id] = self._props(tenant)
                    else:  # PrivateTenant или OtherTenant?
                        self.warning("Некорректный тип подлежащего"
                            f" выгрузке ЛС {tenant['number']} ЮЛ")
                        continue  # пропускаем ЮЛ с некорректным типом
                elif tenant.get('ogrn'):  # ОГРН ФЛ?
                    self.log(warn=f"Подлежащий выгрузке ЛС {tenant['number']}"
                        f" ФЛ {tenant['str_name']} имеет ОГРН {tenant['ogrn']}")

            # загружаем идентификаторы ГИС ЖКХ (организаций) ЮЛ (если есть)
            self._entity_guids: dict = {} if not entity_props else \
                OrgRegistryCommon.load_entity_guids(self, entity_props)

            # загружаем идентификаторы ГИС ЖКХ помещений выгружаемых ЛС
            self._area_guids: dict = {} if not self._area_ids else \
                HouseManagement.load_area_guids(self, *self._area_ids)

        def prepare(self, *tenant_id_s: ObjectId):
            """Подготовка к выгрузке ЛС по направлению платежа"""
            typed_accounts: dict = get_typed_accounts(*tenant_id_s)

            for account_type, typed_ids in typed_accounts.items():
                if (len(tenant_id_s) > len(typed_ids) and  # без начислений?
                        account_type == GisObjectType.UO_ACCOUNT):  # ЛС КУ?
                    untyped_ids: list = [
                        _id for _id in tenant_id_s if _id not in typed_ids
                    ]  # без (направления платежа) начислений
                    typed_ids += untyped_ids  # необходимы для работы с ПУ

                    self.warning(f"Добавлены в выгрузку {len(untyped_ids)} "
                        + get_account_type_name(account_type) +
                        " без (направлений платежа) начислений")

                super().prepare(*typed_ids, object_type=account_type)

        def payment_accounts(self):
            """Лицевые счета, имеющие начисления за последний период"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                provider_ids = [self.provider_id]
                if self.relation_id:
                    provider_ids.append(self.relation_id)
                last_accrual_docs: list = \
                    get_last_accrual_doc_ids(
                        provider_ids, self.house_id)
                if not last_accrual_docs:  # нет документов начислений?
                    raise NoDataError("Для определения типа ЛС"
                        " необходим (проведенный) документ начислений")
                self.log(f"Найдено {len(last_accrual_docs)} документов"
                    f" начислений управляющей {self.house_id}"
                    f" организации {self.provider_id}")
                accrual_accounts: list = Accrual.objects(__raw__={
                    'doc._id': {'$in': last_accrual_docs},  # индекс
                    'is_deleted': {'$ne': True},
                }).distinct('account._id')  # идентификаторы имеющих начисления
                if not accrual_accounts:
                    raise NoDataError("Отсутствуют имеющие начисления"
                        " лицевые счета для выгрузки в ГИС ЖКХ")

            self.log(info=f"Выгружаются данные {len(accrual_accounts)}"
                f" имеющих начисления ЛС дома {self.house_address}")

            self(*accrual_accounts)

        def responsible_tenants(self):
            """Лицевые счета ответственных квартиросъемщиков"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                provider_ids = [self.provider_id]
                if self.relation_id:
                    provider_ids.append(self.relation_id)
                responsible_tenants: list = \
                    get_responsible_tenants(
                        provider_ids,
                        self.house_id
                    )
                if not responsible_tenants:
                    raise NoDataError("Отсутствуют подлежащие выгрузке"
                        " в ГИС ЖКХ ответственные квартиросъемщики")

            self.log(info=f"Выгружаются данные {len(responsible_tenants)}"
                f" ответственных квартиросъемщиков дома {self.house_address}")

            self(*responsible_tenants)

        def period_tenants(self, date_from: datetime, date_till: datetime):
            """Лицевые счета, имеющие начисления за указанный период"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                provider_ids = [self.provider_id]
                if self.relation_id:
                    provider_ids.append(self.relation_id)
                period_accrual_docs: list = \
                    get_accrual_doc_ids(
                        provider_ids, self.house_id, date_from, date_till)
                if not period_accrual_docs:  # нет документов начислений?
                    raise NoDataError("Для указанного периода отсутствуют "
                        "проведенные документы начислений ")
                self.log(f"Найдено {len(period_accrual_docs)} документов"
                    f" начислений управляющей {self.house_id}"
                    f" организации {self.provider_id}")
                accrual_accounts: list = Accrual.objects(__raw__={
                    'doc._id': {'$in': period_accrual_docs},  # индекс
                    'is_deleted': {'$ne': True},
                }).distinct('account._id')  # идентификаторы имеющих начисления

            self(*accrual_accounts)

        def archive_tenants(self):
            """Лицевые счета, подлежащие закрытию"""
            with self.load_context:  # WARN сохраняем только в случае ошибки
                provider_ids = [self.provider_id]
                if self.relation_id:
                    provider_ids.append(self.relation_id)
                date_till = datetime.now().replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0)

                date_from = date_till - relativedelta(years=5)
                accrual_docs: list = \
                    get_accrual_doc_ids(
                        provider_ids, self.house_id, date_from, date_till)
                if not accrual_docs:  # нет документов начислений?
                    raise NoDataError("Для указанного периода отсутствуют "
                        "проведенные документы начислений ")

                accrual_accounts: list = Accrual.objects(__raw__={
                    'doc._id': {'$in': accrual_docs},  # индекс
                    'is_deleted': {'$ne': True},
                }).distinct('account._id')  # идентификаторы имеющих начисления

                closed_tenants: list = Tenant.objects(__raw__={
                    '_id': {'$in': accrual_accounts},  # : list
                    'statuses.accounting.date_till': {'$ne': None},
                }).distinct('id')  # идентификаторы закрытых ЛС с начислениями
            self(*closed_tenants)

        def _house_objects(self, *tenant_id_s: ObjectId) -> tuple:

            assert not self.house_id, "Идентификатор дома" \
                " операции не нуждается в определении"

            if not tenant_id_s:  # лицевые счета не определены?
                return super()._house_objects()  # управляемые организацией дома

            house_tenants: dict = {}

            for tenant in Tenant.objects(__raw__={
                '_id': {'$in': tenant_id_s}
            }).only('area.house').as_pymongo():
                area: dict = tenant.get('area')  # WARN может отсутствовать
                if area is not None:  # ЛС содержит данные помещения?
                    house_tenants.setdefault(
                        area['house']['_id'], []  # идентификатор дома
                    ).append(tenant['_id'])
                else:  # отсутствуют данные помещения!
                    self.failure(self.mapped_guid(  # WARN сопоставляем
                        GisObjectType.UO_ACCOUNT, tenant['_id']
                    ), "Отсутствуют данные о помещении ЛС")

            self.log(warn=f"Выгружаются лицевые счета {len(house_tenants)}"
                f" управляемых {self.provider_name} домов:\n\t"
                + '\n\t'.join(f"{h}: {', '.join(str(t) for t in ts)}"
                    for h, ts in house_tenants.items()))

            for house_id, tenant_ids in house_tenants.items():
                yield house_id, tenant_ids  # идентификаторы дома и жителей

    class exportMeteringDeviceData(ExportOperation):
        """
        Получить перечень приборов учета

        Можно использовать только один из элементов запроса:
        1. Вид прибора учета (НСИ 27): ИПУ, ОДПУ, Общий (квартирный), Комнатный
        2. Коммунальный ресурс (НСИ 2): ХВС, ГВС, ЭЭ, ГС, ТЭ,...
        """
        VERSION = "11.1.0.2"

        REQUIREMENTS = {GisObjectType.AREA: 70}

        @cached_property
        def get_meter_areas(self) -> list:
            """Идентификаторы помещений установки ИПУ"""
            return AreaMeter.objects(__raw__={
                '_id': {'$in': self.object_ids}, '_type': 'AreaMeter',
            }).distinct('area._id')

        @property
        def municipal_resource(self) -> dict:
            """Данные (nsiRef) коммунального ресурса"""
            municipal_resource: dict = self.request.get('MunicipalResource')
            assert isinstance(municipal_resource, dict), \
                "Коммунальный ресурс ПУ не (корректно) определен"
            return municipal_resource

        @property
        def resource_name(self) -> str:
            """Название (или код) коммунального ресурса"""
            assert isinstance(self.municipal_resource, dict), \
                "Коммунальный ресурс ПУ не (корректно) определен"

            resource_name: str = self.municipal_resource.get('Name')  # или None

            return sb(resource_name) if resource_name else \
                f"с кодом {self.municipal_resource['Code']}"  # Обязательное

        @property
        def description(self) -> str:

            return f"ПУ ресурса {self.resource_name}"

        def _store_meter(self, meter: dict):

            def resource_codes(device) -> set:
                """Полученные коды ресурсов ПУ"""
                if device.MunicipalResourceNotEnergy:  # Максимум 3
                    return {item.MunicipalResource.Code  # : str
                        for item in device.MunicipalResourceNotEnergy}
                elif device.MunicipalResourceEnergy:  # Многотарифный (ЭЭ)
                    return {'3'}  # TODO неизменный?
                elif device.MunicipalResources:  # Максимум 3
                    return {item.MunicipalResource.Code  # : str
                        for item in device.MunicipalResources}

            meter_guid: GUID = self._meter_guids[meter['_id']]  # или новый

            meter_guid.premises_id = get_premisses_id(meter)
            meter_guid.desc = get_description(meter)

            serial_number: str = get_serial_number(meter)  # или None
            if not is_correct_sn(serial_number):  # без серийного номера?
                self.failure(meter_guid, "Некорректный серийный номер")
                return
            meter_guid.number = serial_number  # не unique

            if meter.get('area'):  # ИПУ?
                area_guid: GUID = self._area_guids.get(meter['area']['_id'])
                if not area_guid:  # не загружены данные ГИС ЖКХ помещения?
                    self.failure(meter_guid,
                        "Не загружен идентификатор ГИС ЖКХ помещения")
                    return
                key: tuple = (str(area_guid), serial_number)  # : str, str
            else:  # ОДПУ!
                key: tuple = (str(self.fias_guid), serial_number)

            exported = self._metering_devices.pop(key, None)  # WARN извлекаем

            if not exported:  # отсутствует среди полученных из ГИС ЖКХ?
                self.missing(meter_guid)  # подлежит выгрузке после сохранения
            elif str(get_resource_code(meter)) not in resource_codes(exported):
                self.failure(meter_guid,
                    "Коммунальный ресурс ПУ отличается от полученного")
            elif exported.MeteringOwner and str(self.provider_guid.root) \
                    not in exported.MeteringOwner.orgRootEntityGUID:  # "чужой"?
                self.failure(meter_guid,  # ОДПУ (не всегда) - часть ОИ дома
                    "Прибор учета подконтролен иной организации")
            elif meter_guid and exported.StatusRootDoc == 'Archival':  # !Active
                # WARN версии ПУ имеют свой (независящий от текущей) статус
                self.annulment(meter_guid,
                    exported.UpdateDateTime, exported.MeteringDeviceVersionGUID)
            else:  # местонахождение, ресурс, владелец и серийный № - совпали!
                self.success(meter_guid,
                    gis=exported.MeteringDeviceVersionGUID,  # : str -> UUID
                    root=exported.MeteringDeviceRootGUID,  # : str -> UUID
                    unique=exported.MeteringDeviceGISGKHNumber)  # : str

                AreaMeter.update_gis_data(  # унифицированный метод (BasicMeter)
                    meter['_id'], exported.MeteringDeviceGISGKHNumber
                )  # обновляем уникальный идентификатор

        def _store_house_meters(self, meter_ids: list):

            self._meter_guids: dict = \
                self.mapped_guids(GisObjectType.HOUSE_METER, *meter_ids)

            for meter in HouseMeter.objects(__raw__={
                # WARN **HouseMeter.working_meter_query в get_resource_meters
                '_id': {'$in': meter_ids},  # '_type': 'HouseMeter'
            }).only('_type', 'serial_number', 'house').as_pymongo():
                self._store_meter(meter)  # сохраняем данные ОДПУ

        def _store_area_meters(self, meter_ids: list):

            self._area_guids: dict = self.owned_guids(GisObjectType.AREA,
                *self.get_meter_areas)  # идентификаторы помещений установки

            self._meter_guids: dict = \
                self.mapped_guids(GisObjectType.AREA_METER, *meter_ids)

            for meter in AreaMeter.objects(__raw__={
                # WARN **AreaMeter.working_meter_query в get_resource_meters
                '_id': {'$in': meter_ids},  # '_type': 'AreaMeter'
            }).only('_type', 'serial_number', 'area').as_pymongo():
                self._store_meter(meter)  # сохраняем данные ИПУ

        def _store(self, results):

            def _premise_guids(characteristics) -> list:

                if characteristics.ResidentialPremiseDevice:  # жилое помещение?
                    return characteristics.ResidentialPremiseDevice.PremiseGUID
                elif characteristics.NonResidentialPremiseDevice:  # нежилое?
                    return characteristics.NonResidentialPremiseDevice \
                        .PremiseGUID  # идентификатор ГИС ЖКХ помещения
                elif characteristics.LivingRoomDevice:  # комнатный ПУ?
                    return characteristics.LivingRoomDevice.LivingRoomGUID
                elif characteristics.CollectiveApartmentDevice:  # общий ПУ?
                    return characteristics.CollectiveApartmentDevice.PremiseGUID
                elif characteristics.CollectiveDevice:  # ОДПУ?
                    # WARN идентификатор ФИАС дома установки
                    return characteristics.CollectiveDevice.FIASHouseGuid
                else:  # тип места установки не определен!
                    return []

            def _metering_devices() -> dict:

                metering_devices: dict = {}  # (AreaGUID, № ПУ): данные ГИС ЖКХ

                for exported in results:  # : MeteringDeviceDataResultType
                    assert exported.StatusVersion == 'true', \
                        f" Получен ПУ №{exported.MeteringDeviceGISGKHNumber}" \
                        f" со статусом версии {sb(exported.StatusVersion)}"
                    characteristics = exported.BasicChatacteristicts
                    serial_number: str = \
                        characteristics.MeteringDeviceNumber  # Обязательное
                    for premise_guid in _premise_guids(characteristics):
                        key: tuple = (premise_guid, serial_number)  # : str, str
                        metering_devices[key] = exported

                return metering_devices

            assert self.object_ids, \
                "Идентификаторы подлежащих загрузке ПУ не определены"

            self.log(info=f"Получены данные ГИС ЖКХ {len(results)}"
                f" ПУ ресурса {self.resource_name}")

            self._metering_devices: dict = _metering_devices()

            area_meters, house_meters = get_typed_meters(*self.object_ids)

            self.log(info="Подлежат сохранению данные ГИС ЖКХ"
                f" {len(area_meters)} ИПУ и {len(house_meters)} ОДПУ"
                f" дома {self.house_address}")

            if house_meters:
                self._store_house_meters(house_meters)
            if area_meters:
                self._store_area_meters(area_meters)

        def _import(self):

            _import = HouseManagement.importMeteringDeviceData(  # выгружаем
                self.provider_id, self.house_id,  # приборы учета
                update_existing=False  # отсутствующие (без идентификаторов)
            )
            self.lead(_import)  # будет выполнена после завершения текущей

            assert not _import.is_saved, \
                "Запись о последующей операции не должна быть сохранена"
            _import.prepare(*self._missing_ids)  # WARN сохраняем последующую

            self.save()  # WARN сохраняем предшествующую запись об операции

        def _preload(self):

            if self.get_meter_areas:  # помещения установки ИПУ?
                HouseManagement.load_area_guids(self, *self.get_meter_areas)

        def _request(self) -> dict:

            request_data: dict = super()._request()  # копия данных запроса

            if 'FIASHouseGuid' not in request_data:  # Вариант №3?
                request_data.update({
                    'IsCurrentOrganization': True,  # WARN только для ОДПУ
                    'FIASHouseGuid': self.fias_guid,
                    # UpdateDateTime - Дата модификации
                })

            return request_data

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if not self.fias_guid:  # не заполнены данные дома?
                raise NoGUIDError("Отсутствует идентификатор ФИАС дома")

            if not self.provider_guid.root:  # не загружены данные организации?
                raise NoGUIDError("Отсутствует (корневой) идентификатор"
                    f" поставщика информации {self.provider_name}")

            if 'MunicipalResource' not in request_data:  # ресурс не определен?
                return False

            return True

        def prepare(self, *meter_id_s: ObjectId, **request_data):
            """Подготовка к загрузке приборов учета по типу ресурса"""
            if not meter_id_s:  # идентификаторы загружаемых ПУ не определены?
                meter_id_s = concat(
                    *get_house_meters(self.house_id, only_working=True)
                )  # объединяем идентификаторы ИПУ и ОДПУ

            resourced: dict = get_resource_meters(meter_id_s,
                request_data.get('object_type'))  # ИПУ или ОДПУ?

            for resource_code, meters_ids in resourced.items():
                self.log(info="Подлежат загрузке данные ГИС ЖКХ"
                    f" {len(meters_ids)} найденных ИПУ и ОДПУ"
                    f" коммунального ресурса с кодом {resource_code}")

                # WARN общий код разных типов коммунальных ресурсов ИПУ и ОДПУ
                municipal_resource: dict = nsiRef.common(2, resource_code)

                super().prepare(*meters_ids, **request_data,
                    # или MeteringDeviceType - ИПУ, ОДПУ, общий, комнатный ПУ
                    MunicipalResource=municipal_resource)  # коммунальный ресурс

        def house_meters(self):
            """
            Приборы учета (помещений) дома
            """
            with self.load_context:  # WARN сохраняем только в случае ошибки
                area_meters, house_meters = \
                    get_house_meters(self.house_id, only_working=True)
                if not area_meters and not house_meters:
                    raise NoDataError("Отсутствуют подлежащие загрузке"
                        " данных ГИС ЖКХ ПУ (помещений) дома")

            self.log(info=f"Найдены {len(area_meters)} действующих ИПУ"
                f" и {len(house_meters)} ОДПУ управляемого {self.provider_name}"
                f" дома {self.house_address}")

            # TODO выбор определенного типа ресурса (object_type)
            self(*area_meters + house_meters)  # + имеет приоритет

        def period_meters(self, date_from: datetime, date_till: datetime):
            """
            Приборы учета (помещений) дома по периодам действия
            """
            with self.load_context:  # WARN сохраняем только в случае ошибки
                area_meters, house_meters = \
                    get_house_meters(self.house_id, only_working=True)
                if not area_meters and not house_meters:
                    raise NoDataError("Отсутствуют подлежащие загрузке"
                        " данных ГИС ЖКХ ПУ (помещений) дома")

                dated_area_meters = AreaMeter.objects(
                    id__in=area_meters,
                    working_start_date__gte=date_from,
                    working_start_date__lte=date_till,
                ).distinct('_id')

                dated_house_meters = HouseMeter.objects(
                    id__in=house_meters,
                    working_start_date__gte=date_from,
                    working_start_date__lte=date_till,
                ).distinct('_id')

                if not dated_area_meters and not dated_house_meters:
                    raise NoDataError("Отсутствуют подлежащие загрузке"
                                      " данных ГИС ЖКХ ПУ (помещений) дома"
                                      " за указанный период")

            self.log(info=f"Найдены {len(dated_area_meters)} действующих ИПУ"
                f" и {len(dated_house_meters)} ОДПУ управляемого {self.provider_name}"
                f" дома {self.house_address} за указанный период")

            self(*dated_area_meters + dated_house_meters,
            CommissioningDateFrom=date_from, CommissioningDateTo=date_till)  # + имеет приоритет

    class importMeteringDeviceData(HouseManagementOperation):
        """Передать данные приборов учета"""

        VERSION = "11.1.0.8"
        ELEMENT_LIMIT = 100

        REQUIREMENTS = {
            GisObjectType.AREA: 70,
            GisObjectType.UO_ACCOUNT: 70,
        }

        @property
        def is_collective(self) -> bool:
            """Выгрузка данных ИПУ?"""
            assert self.object_type in GUID.METER_TAGS, \
                "Тип подлежащих выгрузке ПУ не (корректно) определен"

            return self.object_type == GisObjectType.HOUSE_METER

        @property
        def description(self) -> str:

            if self.is_collective:
                return f"{len(self.object_ids)} ОДПУ дома"

            return f"{len(self.object_ids)} ИПУ помещений дома"

        def _store(self, common_results: list):

            for result in common_results:
                imported = result.importMeteringDevice  # : importMeteringDevice

                meter_guid: GUID = self._mapped_guids[result.TransportGUID]

                self.success(meter_guid,
                    gis=result.GUID,  # ~ MeteringDeviceVersionGUID
                    root=imported.MeteringDeviceGUID,  # MeteringDeviceRootGUID
                    unique=result.UniqueNumber)  # : str

                AreaMeter.update_gis_data(  # унифицированный метод (BasicMeter)
                    meter_guid.object_id, result.UniqueNumber
                )  # обновляем уникальный идентификатор

        def _check_meter(self, device: MeteringDevice):

            if not device.serial_number:  # is_correct_sn?
                raise ObjectError("Некорректный серийный (заводской) номер")

            if device.installed and device.commissioned and \
                    device.installed > device.commissioned:  # вернется ошибка
                raise ObjectError("Дата ввода в эксплуатацию раньше установки")

            if any(val < 0 for val in device.initial_values):  # или readings
                # WARN периодические проверяются при выгрузке показаний
                raise ObjectError("Отрицательные начальные показания")

            if device.is_remote_metering:  # Автоматизированный счетчик?
                self.warning("Передача показаний автоматизированного ПУ"
                    " недоступна пользователям ГИС ЖКХ")  # WARN предупреждение

        def _basic_characteristics(self, device: MeteringDevice) -> dict:
            """"MeteringDeviceBasicCharacteristicsType"""

            def device_type() -> str:
                """Тип установки ПУ"""
                if device.is_house_meter:  # ОДПУ дома?
                    return 'CollectiveDevice'
                elif device.area_id in self._shared_areas:  # коммунальный ПУ?
                    return 'CollectiveApartmentDevice'
                elif device.is_living_area:  # ИПУ квартиры?
                    return 'ResidentialPremiseDevice'
                elif device.is_not_living_area:  # ИПУ нежилого помещения?
                    return 'NonResidentialPremiseDevice'

                # TODO ApartmentHouseDevice - ИПУ жилого (частного) дома
                # TODO LivingRoomDevice - Комнатный ИПУ (нет в Системе)
                raise NotImplementedError("Тип установки не поддерживается")

            basic_characteristics: dict = {
                **device.basic_characteristics(),
                'VerificationInterval': nsiRef.common(16, device.check_interval)
            }  # : MeteringDeviceBasicCharacteristicsType
            # WARN отличается от MeteringDeviceToUpdateAfterDevicesValuesType

            # region CollectiveDevice - Характеристики общедомового ПУ
            if device.is_house_meter:  # (коллективный) ОбщеДомовой ПУ?
                basic_characteristics['CollectiveDevice'] = {  # ~ device_type()
                    'FIASHouseGuid': self.fias_guid,
                    # TODO TemperatureSensingElementInfo, если TemperatureSensor
                    # TODO PressureSensingElementInfo, если PressureSensor=true
                    # TODO ProjectRegistrationNode - Проект(ы) узла учета
                    # TODO Certificate - Акт(ы) ввода узла учета в эксплуатацию
                }

                return basic_characteristics
            # endregion CollectiveDevice - Характеристики общедомового ПУ

            # в коммунальной - от 1 и более, в обычной - не более одного ЛС
            account_guids: list = self._tenant_guids.get(device.area_id)
            if not account_guids:  # не загружены идентификаторы ЛС?
                raise ObjectError("Нет данных ГИС ЖКХ плательщика")

            # TODO ApartmentHouseDevice - Характеристики ИПУ жилого дома

            # TODO LivingRoomDevice - Характеристики комнатного ИПУ

            # region [Non]ResidentialPremiseDevice / CollectiveApartmentDevice
            premise_guid: GUID = self._area_guids.get(device.area_id)
            if not premise_guid:  # не загружен идентификатор помещения?
                raise ObjectError("Нет данных ГИС ЖКХ помещения")

            basic_characteristics[device_type()] = {
                'PremiseGUID': [premise_guid.gis],  # Множественное
                'AccountGUID': account_guids[0],
                # TODO Certificate - Акт(ы) ввода узла учета в эксплуатацию
            }
            return basic_characteristics
            # endregion [Non]ResidentialPremiseDevice/CollectiveApartmentDevice

        def _full_information(self, device: MeteringDevice) -> dict:
            """"MeteringDeviceFullInformationType"""
            device_information: dict = {  # WARN опечатка в названии элемента
                'BasicChatacteristicts': self._basic_characteristics(device),
            }  # : MeteringDeviceFullInformationType

            if True:  # TODO LinkedWithMetering - связей с другими ПУ нет?
                device_information['NotLinkedWithMetering'] = True

            if device.okei_unit not in METER_OKEI_UNITS or (device.is_energy
                    and device.okei_unit != MeasurementUnits.KILOWATT_PER_HOUR):
                raise ObjectError("Некорректная единица измерения ПУ")

            if device.is_energy and device.transformation_ratio <= 0:
                raise ObjectError("Коэффициент трансформации строго больше 0")

            if device.is_consumed_volume:  # КР ПУ (ЭЭ, ТЭ, ГС, ГВ, ХВ, СВ)
                municipal_resource: dict = {
                    'MunicipalResource': device.municipal_resource,
                    'Unit': device.okei_unit,
                }
                if device.is_energy:  # электроэнергия?
                    municipal_resource.update({
                        'TariffCount': device.tariff_count,
                        'TransformationRatio': device.transformation_ratio,
                    })
                device_information['MunicipalResources'] = [
                    municipal_resource
                ]  # Максимум 3
            elif device.is_energy:  # Последние показания и сведения о ПУ ЭЭ
                device_information['MunicipalResourceEnergy'] = {
                    'Unit': device.okei_unit,  # WARN только '245'
                    'TransformationRatio': device.transformation_ratio,
                    **device.multi_rate_values
                }  # единственный элемент
            else:  # Последние показания и коммунальный ресурс ПУ
                device_information['MunicipalResourceNotEnergy'] = [{
                    'Unit': device.okei_unit,  # обязателен для нестандартных ЕИ
                    **device.one_rate_value  # включает MunicipalResource
                }]  # Максимум 3

            return device_information

        def _after_values(self, device: MeteringDevice) -> dict:
            """MeteringDeviceToUpdateAfterDevicesValuesType"""
            characteristics: dict = {
                **device.basic_characteristics(),
                # TODO Certificate - Акты ввода узла учета в эксплуатацию
                # TODO AddressChatacteristicts - Изменение адреса установки
            }  # : MeteringDeviceToUpdateAfterDevicesValuesType

            if True:  # TODO изменение лицевых счетов?
                characteristics['AccountGUID'] = \
                    self._tenant_guids.get(device.area_id)

            if device.is_energy:  # Вариант №2
                # Необходимо прислать все актуальные базовые показания
                # в соответствии с видом ПУ по количеству тарифов
                # (даже если требуется отредактировать только одно показание)
                characteristics['MunicipalResourceEnergy'] = {
                    'TransformationRatio': device.transformation_ratio,
                    **device.multi_rate_values,
                }  # единственный элемент
            else:  # Вариант №1
                # Коммунальный ресурс (ТЭ, Газ, ГВ, ХВ, СВ)
                # должен быть указан тот же, что и при создании ПУ
                characteristics['MunicipalResourceNotEnergy'] = [
                    device.one_rate_value
                ]  # Максимум 3

            if True:  # TODO LinkedWithMetering - связей с другими ПУ нет?
                characteristics['NotLinkedWithMetering'] = True

            return characteristics

        def _update_data(self, device: MeteringDevice) -> dict:

            update_data: dict = {}  # : DeviceDataToUpdate

            # TODO LinkedWithMetering - Связать с другими заведенными в ГИС ЖКХ
            if device.replaced:  # Замена на другой?
                if device.is_house_meter:  # ОДПУ?
                    raise ObjectError("Замененный ОДПУ не подлежит выгрузке")

                if device.replacing_id is None:  # нет рабочего ПУ на стояке?
                    raise ObjectError("Замещающий по стояку ПУ не найден")
                replacing_guid: GUID = \
                    self._meter_guids.get(device.replacing_id)
                if not replacing_guid:  # замещающий ПУ не выгружен?
                    # выгрузить замещенный как закрытый без данных замещающего
                    update_data['ArchiveDevice'] = device.archive()
                else:
                    update_data['ReplaceDevice'] = device.replace(replacing_guid)
            elif device.disassembled:  # Архивация (без замены)?
                update_data['ArchiveDevice'] = device.archive()
            # WARN UpdateAfterDevicesValues обрабатывается вне данного метода
            else:  # Обновление до внесения показаний!
                update_data['UpdateBeforeDevicesValues'] = \
                    self._full_information(device)

            return update_data

        def _metering_device(self, meter: dict) -> Optional[dict]:

            # WARN выброшенные ObjectError обрабатываются в _produce
            meter_guid: GUID = self._meter_guids[meter['_id']]  # или новый
            if self._is_skippable(meter_guid):  # не подлежит выгрузке?
                return  # пропускаем

            device: MeteringDevice = MeteringDevice(meter)

            meter_guid.number = device.serial_number  # : str
            meter_guid.premises_id = \
                device.area_id if device.is_area_meter else device.house_id
            meter_guid.desc = get_description(meter)

            self._check_meter(device)  # выбрасывает исключение

            if not meter_guid:  # без данных ГИС ЖКХ?
                return meter_guid.as_req(
                    DeviceDataToCreate=self._full_information(device)
                )  # создаем новый ПУ
            # Определяем данные для обновления на основе состояния прибора учета
            # Если закрыт или заменен
            if device.disassembled or device.replaced:
                update_data: dict = self._update_data(device)
            elif meter_guid.updated:  # После начала внесения показаний?
                update_data: dict = {
                    'UpdateAfterDevicesValues': self._after_values(device)
                }
            else:
                update_data: dict = self._update_data(device)

            return meter_guid.as_req(DeviceDataToUpdate={
                'MeteringDeviceVersionGUID': meter_guid.gis,  # TODO версии?
                **update_data,
            })  # обновляем данные ПУ

        def _area_meters(self) -> dict:

            def get_area_tenant_guids() -> dict:
                """Идентификаторы ГИС ЖКХ (ЛС) жильцов в помещениях"""
                assert self._tenant_guids, "Требуются идентификаторы ГИС ЖКХ ЛС"

                area_tenant_guids: dict = {}  # AreaId: [ TenantGUID,... ]

                for tenant in Tenant.objects(__raw__={
                    '_id': {'$in': self._tenant_ids}, 'area': {'$ne': None},
                }).only('area').as_pymongo():
                    tenant_guid: GUID = self._tenant_guids.get(tenant['_id'])
                    if not tenant_guid:  # отсутствуют данные ГИС ЖКХ ЛС?
                        continue

                    tenant_guids: list = area_tenant_guids.setdefault(
                        tenant['area']['_id'], []
                    )
                    # Duplicate unique value...declared for identity constraint
                    if tenant_guid.gis not in tenant_guids:
                        tenant_guids.append(tenant_guid.gis)

                return area_tenant_guids

            if self._area_ids:
                self._shared_areas: list = Area.objects(__raw__={
                    '_id': {'$in': self._area_ids},  # ~ AreaMeter.area._id
                    'is_shared': True,  # WARN CommunalArea - недостоверный признак
                }).distinct('id')
                self._tenant_guids: dict = get_area_tenant_guids()  # перезаписываем

            self._meter_guids: dict = \
                self.mapped_guids(GisObjectType.AREA_METER, *self.object_ids)

            return {'MeteringDevice':  # Множественное
                self._produce(self._metering_device, AreaMeter.objects(__raw__={
                    '_id': {'$in': self.object_ids},  # '_type': 'AreaMeter'
                }).as_pymongo())}  # : QuerySet

        def _house_meters(self) -> dict:

            # получаем сопоставленные идентификаторы подлежащих выгрузке ОДПУ
            self._meter_guids: dict = \
                self.mapped_guids(GisObjectType.HOUSE_METER, *self.object_ids)

            house_meters = HouseMeter.objects(__raw__={
                '_id': {'$in': self.object_ids},  # '_type': 'HouseMeter'
            }).as_pymongo()  # : QuerySet

            return {'MeteringDevice':  # Множественное
                self._produce(self._metering_device, house_meters)}

        def _compose(self) -> dict:

            if self.is_collective:  # ОДПУ?
                return self._house_meters()

            return self._area_meters()  # ИПУ!

        def _preload(self):

            if self.is_collective:  # ОДПУ?
                return  # WARN идентификаторы жильцов и помещений не требуются
            if not self.object_ids:
                self._area_ids = []
            else:
                self._area_ids: list = AreaMeter.objects(__raw__={
                    '_id': {'$in': self.object_ids},  # '_type': 'AreaMeter'
                }).distinct('area._id')
                if self._area_ids:  # найдены помещения установки ИПУ?
                    self._area_guids = \
                        HouseManagement.load_area_guids(self, *self._area_ids)
                else:  # требуются данные помещений установки ИПУ!
                    raise NoDataError("Отсутствуют данные помещений установки ИПУ")
                provider_ids = [self.provider_id]
                if self.relation_id:
                    provider_ids.append(self.relation_id)
                self._tenant_ids: list = get_responsible_tenants(
                    provider_ids,
                    self.house_id,
                    account__area__id__in=self._area_ids  # сужаем ореол поиска
                )
                if not self._tenant_ids:  # плательщики не найдены?
                    raise NoDataError("Отсутствуют данные ответственных"
                        " квартиросъемщиков помещений установки ИПУ")
                self._tenant_guids: dict = \
                    HouseManagement.load_account_guids(self, *self._tenant_ids)

        def prepare(self, *meter_id_s: ObjectId):
            """Подготовка к выгрузке ИПУ и ОДПУ"""
            assert meter_id_s, \
                "Требуются идентификаторы подлежащих выгрузке в ГИС ЖКХ ПУ"

            area_meters, house_meters = get_typed_meters(*meter_id_s)

            if area_meters:  # ИПУ?
                super().prepare(*area_meters,
                    object_type=GisObjectType.AREA_METER)  # WARN извлекается

            # WARN загрузка ОДПУ становится порожденной от выгрузки ИПУ
            if house_meters:  # идентификаторы ОДПУ?
                super().prepare(*house_meters,
                    object_type=GisObjectType.HOUSE_METER)  # WARN извлекается

        def working_meters(self):
            """
            Действующие приборы учета (помещений) дома
            """
            with self.load_context:  # WARN сохраняем только в случае ошибки
                area_meters, house_meters = \
                    get_house_meters(self.house_id, only_working=True)
                if not area_meters and not house_meters:
                    raise NoDataError("Отсутствуют подлежащие выгрузке"
                        " в ГИС ЖКХ действующие ПУ (помещений) дома")

            self.log(info="Подлежат выгрузке данные действующих"
                f" {len(area_meters)} ИПУ и {len(house_meters)} ОДПУ"
                f" управляемого {self.provider_name} дома {self.house_address}")

            self(*area_meters + house_meters)  # + имеет приоритет

        def closed_meters(self):
            """
            Закрытые приборы учета (помещений) дома
            """
            with self.load_context:  # WARN сохраняем только в случае ошибки
                closed_area_meters, closed_house_meters = \
                    get_house_meters(self.house_id, only_closed=True)
                if not closed_area_meters and not closed_house_meters:
                    raise NoDataError("Отсутствуют подлежащие выгрузке"
                        " в ГИС ЖКХ закрытые ПУ (помещений) дома")

            self.log(info="Подлежат выгрузке данные закрытых"
                f" {len(closed_area_meters)} ИПУ и {len(closed_house_meters)} ОДПУ"
                f" управляемого {self.provider_name} дома {self.house_address}")

            self(*closed_area_meters + closed_house_meters)  # + имеет приоритет