from typing import Optional

from datetime import datetime

from django.utils.functional import cached_property

from app.gis.core.async_operation import AsyncOperation
from app.gis.core.web_service import WebService
from app.gis.core.custom_operation import ExportOperation, ImportOperation
from app.gis.core.exceptions import GisError, NoDataError, NoGUIDError

from app.gis.services.house_management import HouseManagement

from app.gis.utils.common import as_guid, get_period, fmt_period
from app.gis.utils.meters import MeteringDeviceTypeCode, \
    metering_interval, get_description, get_serial_number, \
    get_resource_code, get_resource_type, get_premisses_id

from app.gis.models.choices import GisObjectType
from app.gis.models.guid import GUID
from app.gis.models.nsi_ref import nsiRef

from app.meters.models.meter import AreaMeter, HouseMeter, \
    ReadingsValidationError, MeterDataValidationError, \
    VOLUME_METER, ELECTRIC_METER

from processing.models.choices import ReadingsCreator, READINGS_CREATORS_CHOICES
from processing.data_producers.associated.base import get_houses_meters_periods


CREATOR_NAMES = dict(READINGS_CREATORS_CHOICES)


class MeteringOperation:

    @cached_property
    def house(self):  # -> House
        """Данные дома операции"""
        assert isinstance(self, AsyncOperation)

        from app.house.models.house import House
        house: House = House.objects(id=self.house_id).only(
            'gis_metering_start', 'gis_metering_end', 'gis_collective',
        ).first()
        assert house is not None, "Данные дома операции не загружены"

        return house

    @staticmethod
    def is_area_meter(meter_data: dict) -> bool:
        """Индивидуальный прибор учета?"""
        assert isinstance(meter_data, dict), "Некорректный тип данных ПУ"

        types: list = meter_data.get('_type')
        assert types is not None, "Данные ПУ не содержат информацию о типе"

        return any('Area' in _type for _type in types)  # in str

    def get_object_type(self, meter_data: dict) -> str:
        """Получить тип (по месту установки) ПУ ~ ИПУ или ОДПУ"""
        return GisObjectType.AREA_METER if self.is_area_meter(meter_data) \
            else GisObjectType.HOUSE_METER


class DeviceMetering(WebService):
    """
    Асинхронный сервис управления приборами учета и передачей показаний

    MeteringDeviceVersionGUID - ед. вариант при изменении данных ПУ
    MeteringDeviceRootGUID - ед. вариант при загрузке показаний ПУ

    При загрузке данных и выгрузке показаний может использоваться любой из ид.
    """

    class exportMeteringDeviceHistory(MeteringOperation, ExportOperation):
        """
        Получить историю показаний ПУ

        При неуказанном интервале снятия выгружаются показания:
        - с первого числа предыдущего месяца
        - до последнего дня текущего месяца (включительно)
        """

        VERSION = "10.0.1.1"

        @property
        def description(self) -> str:

            date_from: str = \
                fmt_period(self.request['inputDateFrom'], with_day=True)
            date_to: str = \
                fmt_period(self.request['inputDateTo'], with_day=True)

            return f"Снятые с {date_from} по {date_to}"

        def _parse(self, state_result):

            error_message = state_result.ErrorMessage  # без ошибки = None
            if error_message:  # : zeep.objects.ErrorMessageType
                # "Нет объектов для экспорта" тоже является ErrorMessage
                raise GisError.from_result(error_message)  # исключение!

            # PagedOutput не заполняется для одного элемента FIASHouseGuid!
            assert not state_result.PagedOutput, \
                "В запросе должен быть ровно один ФИАС-идентификатор дома"

            history: list = state_result.exportMeteringDeviceHistoryResult

            return history

        def _store_metering(self, meter: AreaMeter or HouseMeter):

            assert isinstance(meter, (AreaMeter, HouseMeter))
            meter_data: dict = meter.to_mongo().to_dict()

            serial_number: str = get_serial_number(meter_data)  # или None

            # WARN предварительно загружены имеющие корневые идентификаторы
            meter_guid: GUID = self._meter_guids.get(meter.id)
            if meter_guid is None:
                meter_guid: GUID = self.created_guid(
                    self.get_object_type(meter_data), meter.id,
                    number=serial_number,
                    premises_id=get_premisses_id(meter_data),
                    desc=get_description(meter_data),
                )  # подлежит сохранению (с ошибкой, без идентификатора)
            elif serial_number and meter_guid.number != serial_number:  # иной?
                meter_guid.number = serial_number  # обновляем серийный номер

            self._map(meter_guid)  # сопоставляем идентификатор операции

            if not meter_guid:  # отсутствует (корневой) идентификатор ГИС ЖКХ?
                self.failure(meter_guid, "Не загружен идентификатор ГИС ЖКХ ПУ")
                return

            if meter.is_deleted:  # удален?
                self.failure(meter_guid, "Получены показания удаленного ПУ")
                return

            exported = self._device_values.pop(meter_guid.root)  # 3 типа:

            if exported.ControlValue:  # TODO Контрольные показания
                self.warning("Получены (не обрабатываемые) контрольные"
                    f" показания ПУ №{serial_number}")
            if exported.VerificationValue:  # TODO Показания поверки
                self.warning("Получены (не обрабатываемые)"
                    f" показания поверки ПУ №{serial_number}")

            if not exported.CurrentValue:  # Текущие показания?
                self.failure(meter_guid, "Текущие показания ПУ"
                    " отсутствуют в полученных данных")
                return

            if len(exported.CurrentValue) == 1:  # показания переданы один раз?
                current = exported.CurrentValue[0]
            else:  # показания переданы более одного раза!
                last_entered = max(value.DateValue  # EnterIntoSystem - внесено
                    for value in exported.CurrentValue)  # Дата снятия показания
                current = next(value for value in exported.CurrentValue
                    if value.DateValue == last_entered)  # последние показания

            # WARN переданные гражданами показания имеют orgPPAGUID = None
            if current.orgPPAGUID == str(self.ppaguid):  # текущей организацией?
                self.failure(meter_guid, "Получены внесенные сотрудником"
                    f" {current.ReadingsSource} показания")  # Кем внесено (ФИО)
                return

            current_values: list = [  # Показания (15 знаков до запятой,7-после)
                int(float(current.MeteringValueT1)),  # : str
                int(float(current.MeteringValueT2 or 0)),
                int(float(current.MeteringValueT3 or 0))
            ] if not hasattr(current, 'MeteringValue') else [
                int(float(current.MeteringValue))  # OneRateDeviceValue
            ]

            person_or_employee = "Гражданин" if not current.orgPPAGUID \
                else f"Сотрудник {current.orgPPAGUID}"
            self.log(info=f"{person_or_employee} {current.ReadingsSource}"
                f" внес {fmt_period(current.DateValue, with_day=True)}"
                f" в ГИС ЖКХ показания ПУ №{serial_number}: "
                    + ', '.join(str(value) for value in current_values))

            # GIS_TENANT / GIS_SYSTEM / SYSTEM/AUTOMATIC/WORKER/TENANT/REGISTRY
            creator: str = ReadingsCreator.GIS_SYSTEM if current.orgPPAGUID \
                else ReadingsCreator.GIS_TENANT  # сотрудник или гражданин

            if current.Period:  # Обязательное?
                current_period = datetime(day=1,  # первый день месяца
                    year=current.Period.Year, month=current.Period.Month)
                if current_period != self.period:
                    self.warning(f"Запрошенные за {fmt_period(self.period)}"
                        f" показания переданы за {fmt_period(current_period)}")
            else:  # WARN может отсутствовать в полученных данных!
                current_period = self.period

            try:  # попытаемся сохранить полученные показания
                meter.add_readings(
                    period=current_period,
                    values=current_values,  # : float-FLOAT_READINGS_ALLOW_TYPES
                    creator=creator, actor_id=None,  # TODO кто внес в Систему
                    values_are_deltas=meter.resource_type in VOLUME_METER,
                    comment=CREATOR_NAMES.get(creator),
                )  # WARN не сохраняет
                meter.save()  # сохраняем ПУ с показаниями
            except ReadingsValidationError as readings_error:
                self.failure(meter_guid, str(readings_error))
            except MeterDataValidationError as meter_error:
                self.failure(meter_guid, str(meter_error))
            else:  # полученные показания успешно сохранены!
                self.success(meter_guid,
                    updated=current.DateValue)  # дата снятия показаний

        def _store_area_meterings(self):

            area_meters = AreaMeter.objects(__raw__={
                '_id': {'$in': self.object_ids},
                '_type': 'AreaMeter',
                 'is_automatic': {'$ne': True},
            })  # WARN документы (со всеми полями) для add_readings

            self.log(info="Сохраняются переданные гражданами и сотрудниками"
                f" организаций показания {area_meters.count()} ИПУ за"
                f" {fmt_period(self.period)} дома {self.house_address}")

            for meter in area_meters:  # ИПУ
                self._store_metering(meter)  # сохраняем показания

        def _store_house_meterings(self):

            house_meters = HouseMeter.objects(__raw__={
                '_id': {'$in': self.object_ids}, '_type': 'HouseMeter',
            })  # WARN документы (со всеми полями) для add_readings

            self.log(info="Сохраняются переданные сотрудниками"
                f" организаций показания {house_meters.count()} ОДПУ за"
                f" {fmt_period(self.period)} дома {self.house_address}")

            for meter in house_meters:  # ОДПУ
                self._store_metering(meter)

        def _store(self, export_results: list):

            def get_device_values() -> dict:
                """
                {
                    MeteringDeviceRootGUID: UUID - корневой ид. ПУ
                    : Values: {
                        CurrentValue: list,
                        ControlValue: list,
                        VerificationValue: list,
                        excludeISValues:
                            True - только переданные в ЛК и другими ИС показания
                            None - все показания
                    }
                } извлеченные из exportMeteringDeviceHistoryResultType
                """
                return {as_guid(exported.MeteringDeviceRootGUID):  # : str
                    exported.OneRateDeviceValue.Values  # BaseValue - начальные
                        if exported.OneRateDeviceValue
                    else exported.ElectricDeviceValue.Values
                        if exported.ElectricDeviceValue
                    else exported.VolumeDeviceValue
                        if exported.VolumeDeviceValue else None  # НЕ список!
                for exported in export_results}

            # сопоставляем полученные показания с корневыми идентификаторами ПУ
            self._device_values: dict = get_device_values()  # RootGUID: Values
            assert self._device_values, \
                "В полученных данных отсутствуют (показания) ПУ"  # недостижимо?

            self.log(info="Получены внесенные в ГИС ЖКХ показания"
                f" {len(export_results)} ПУ дома {self.house_address}")

            # загружаем данные ГИС ЖКХ по корневым идентификаторам ПУ
            self._meter_guids: dict = \
                self.root_owned_guids(*self._device_values)  # MeterId: GUID
            if not self._meter_guids:  # не загружены (корневые) идентификаторы?
                raise NoGUIDError("Отсутствуют идентификаторы"
                    " ГИС ЖКХ полученных (показаний) ПУ")

            if not self.object_ids:  # сохранить все полученные показания?
                self._record.object_ids = [*self._meter_guids]
            else:  # определены загружаемые (показания) ПУ!
                self._record.object_ids = list(
                    {*self.object_ids}.intersection({*self._meter_guids})
                )
            if not self.object_ids:  # перечень ПУ пуст?
                raise NoDataError("Подлежащие сохранению"
                    " (показания) ПУ не определены")

            device_types: list = self.request.get('MeteringDeviceType')  # None?
            if not device_types or any(ref['Code'] in {
                MeteringDeviceTypeCode.INDIVIDUAL,  # ИПУ
                MeteringDeviceTypeCode.COMMON,  # общеквартирный ИПУ
                MeteringDeviceTypeCode.ROOM,  # комнатный ИПУ
            } for ref in device_types):
                self._store_area_meterings()  # сохраняем показания ИПУ

            if not device_types or any(ref['Code'] in {
                MeteringDeviceTypeCode.COLLECTIVE,  # ОДПУ
            } for ref in device_types):
                self._store_house_meterings()  # сохраняем показания ОДПУ

        def root_owned_guids(self, *root_guid_s) -> dict:
            """
            Загрузить данные ГИС ЖКХ по корневым идентификаторам ПУ

            :returns: MeterId: MappedGUID
            """
            meter_guids: dict = {guid.object_id: guid
                for guid in GUID.objects(__raw__={
                    'provider_id': self.provider_id,  # индекс
                    'tag': {'$in': [*GUID.METER_TAGS]},  # ИПУ и ОДПУ
                    'root': {'$in': root_guid_s},  # по корневым идентификаторам
                })}

            self.log(f"Загружены данные ГИС ЖКХ {len(meter_guids)} ПУ из"
                f" {len(root_guid_s)} запрошенных по корневым идентификаторам")

            return meter_guids

        def _request(self) -> dict:

            request_data: dict = super()._request()  # копия данных запроса

            # WARN в результате возвращается ФИАС дома при нескольких в запросе
            request_data['FIASHouseGuid'] = [self.fias_guid]  # Множественное

            if 'MeteringDeviceType' not in request_data:  # тип ПУ не определен?
                request_data['MeteringDeviceType'] = [
                    nsiRef.common(27, code) for code in {
                        MeteringDeviceTypeCode.INDIVIDUAL,  # ИПУ
                        MeteringDeviceTypeCode.COLLECTIVE,  # ОДПУ
                        MeteringDeviceTypeCode.COMMON,  # Общий (квартирный)
                        MeteringDeviceTypeCode.ROOM,  # Комнатный
                    }]  # WARN AssertionError при незагруженном справочнике
            # TODO или MunicipalResource - Вид коммунального ресурса (НСИ 2)

            return request_data

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if not self.fias_guid:  # не определен ФИАС дома?
                raise NoGUIDError("Отсутствует идентификатор ФИАС дома")

            if 'period' not in request_data:  # не определен для операции?
                return False

            return True

        def house_meterings(self, metering_period: datetime = None,
                exclude_self: bool = True, exclude_others: bool = True,
                exclude_archived: bool = True):
            """
            Загрузка показаний (поверок) ПУ из ГИС ЖКХ за (текущий) период

            Для нескольких домов выгрузка осуществляется блоками по 1000 ПУ

            :param metering_period: период сдачи загружаемых показаний
            :param exclude_self: кроме внесенных (шаблонами) организацией?
            :param exclude_others: кроме внесенных иными организациями (РСО)?
            :param exclude_archived: исключая показания архивированных ПУ?
            """
            with self.load_context as context:  # WARN сохраняем в случае ошибки
                # период (месяц и год) следующих показаний ПУ дома
                house_period: datetime = get_houses_meters_periods(
                    self.provider_id, house=self.house_id  # не для всех
                ).get(self.house_id)  # ид. дома : период показаний
                if not metering_period:  # период не определен?
                    metering_period = house_period
                    self.log(warn=f"Для дома {self.house_id} определен период"
                        f" {fmt_period(metering_period)} передачи показаний ПУ")
                elif self['update_existing']:  # форсированная загрузка?
                    self.warning("Принудительная загрузка показаний ПУ за"
                        f" {fmt_period(house_period)} может привести"
                        " к ошибкам при сохранении")
                elif metering_period < house_period:  # более ранние показания?
                    raise NoDataError("Возможна загрузка показаний ПУ только за"
                        f" {fmt_period(house_period)} или последующий периоды")

                # inputDateFrom - Необязательное (1 число пред. месяца)
                # inputDateTo - Необязательное (текущая дата)
                date_from, date_till = metering_interval(
                    self.house.gis_metering_start,
                    self.house.gis_metering_end,
                    metering_period
                )  # : tuple

            if context.exception:  # ошибка плановой операции?
                return  # завершаем выполнение

            self.log(info="Загружаются снятые (переданные)"
                f" с {fmt_period(date_from, True)}"
                f" по {fmt_period(date_till, True)}"
                f" показания ПУ дома {self.house_address}")

            self(
                # TODO ExportMeteringDeviceRootGUID - постраничная выгрузка
                period=metering_period,  # WARN извлекается
                SerchArchived=not exclude_archived,  # ArchiveDateFrom...To
                inputDateFrom=date_from,  # Дата снятия показаний "С"
                inputDateTo=date_till,  # Дата снятия показаний "По"
                ExcludePersonAsDataSource=False,  # WARN введенные гражданами
                ExcludeCurrentOrgAsDataSource=exclude_self,
                ExcludeOtherOrgAsDataSource=exclude_others,
                # WARN excludeISValues - устаревшая функциональность
            )

    class importMeteringDeviceValues(MeteringOperation, ImportOperation):
        """Передать показания ПУ"""

        VERSION = "10.0.1.1"
        ELEMENT_LIMIT = 1000

        REQUIREMENTS = {
            GisObjectType.AREA_METER: 70,
            GisObjectType.HOUSE_METER: 0,
        }

        @property
        def description(self) -> Optional[str]:

            return f"За {fmt_period(self.period)}"

        @property
        def is_house_meters(self) -> bool:
            """Выгрузка показаний ОДПУ?"""
            # WARN отличается от is_area_meter в MeteringOperation
            return self.request.get('FIASHouseGuid') is not None

        def _store(self, import_results: list):

            for result in import_results:
                meter_guid: GUID = self._mapped_guids[result.TransportGUID]

                # WARN полученная "Дата модификации" во временной зоне +03:00
                self.success(meter_guid, updated=result.UpdateDate)

        def _metering_values(self, meter: dict) -> Optional[dict]:

            meter_guid: GUID = self._mapped_guids[meter['_id']]  # или новый
            if not meter_guid:  # WARN gis = MeteringDeviceVersionGUID
                meter_guid.number = get_serial_number(meter)  # : str или None
                meter_guid.premises_id = get_premisses_id(meter)
                meter_guid.desc = get_description(meter)
                self.failure(meter_guid, "Не загружен идентификатор ГИС ЖКХ ПУ")
                return

            current_reading: dict = next(iter(
                reading for reading in meter['readings']
                if reading['period'] == self.period  # за период
                and len(reading['values']) > 0  # по умолчанию = []
            ), None)  # показания за период
            if not current_reading:  # нет показаний за период?
                self.failure(meter_guid, "Отсутствуют показания ПУ за период")
                return

            if current_reading.get('created_by') in {
                ReadingsCreator.GIS_TENANT, ReadingsCreator.GIS_SYSTEM,
            }:  # получены из ГИС ЖКХ?
                self._unmap(meter_guid)  # исключаем из подлежащих выгрузке
                return

            current_value: dict = meter_guid.as_req(
                DateValue=current_reading['created_at'],  # снятия показаний
                Period={  # WARN только в xsd
                    'Year': current_reading['period'].year,  # : short 1920-2050
                    'Month': current_reading['period'].month,  # : int 1-12
                }  # Период, за который передаются показания
            )

            resource_type: str = get_resource_type(*meter['_type'])
            municipal_resource: dict = \
                nsiRef.common(2, get_resource_code(resource_type))

            if resource_type in VOLUME_METER:  # объем потребленных ресурсов?
                # T1 - обязателен, T2, T3 - опциональны
                current_value.update(
                    MunicipalResource=municipal_resource,
                    **{f"MeteringValueT{i}": str(value) for i, value
                        in enumerate(current_reading['values'], start=1)},
                )
                device_values = dict(VolumeDeviceValue={
                    'CurrentValue': [current_value],  # Максимум 3
                    # TODO ControlValue - Контрольный объем
                    # TODO VerificationValue - Сведения о поверке
                })
            elif resource_type in ELECTRIC_METER:  # многотарифный?
                current_value.update(
                    {f"MeteringValueT{i}": str(value) for i, value
                        in enumerate(current_reading['values'], start=1)}
                )
                device_values = dict(ElectricDeviceValue={
                    'CurrentValue': current_value,  # WARN единственный элемент
                    # TODO ControlValue - Контрольный объем
                    # TODO VerificationValue - Сведения о поверке
                })
            else:  # однотарифный!
                current_values: list = current_reading['values']
                assert len(current_values) == 1, "Неверное количество показаний"
                current_value.update(
                    MunicipalResource=municipal_resource,
                    MeteringValue=str(current_values[0]),
                )
                device_values = dict(OneRateDeviceValue={
                    'CurrentValue': [current_value],  # Максимум 3
                    # TODO ControlValue - Контрольный объем
                    # TODO VerificationValue - Сведения о поверке
                })

            return dict(
                MeteringDeviceVersionGUID=meter_guid.gis,
                # или MeteringDeviceRootGUID - Корневой идентификатор ПУ
                **device_values,
            )

        def _compose(self) -> dict:

            if self.object_type == GisObjectType.AREA_METER:  # AreaMeter?
                meters: list = AreaMeter.objects(__raw__={
                    '_id': {'$in': self.object_ids}, '_type': 'AreaMeter',
                }).only('_type', 'area', 'readings').as_pymongo()
            else:  # HouseMeter!
                meters: list = HouseMeter.objects(__raw__={
                    '_id': {'$in': self.object_ids}, '_type': 'HouseMeter',
                }).only('_type', 'house', 'readings').as_pymongo()

            self.mapped_guids(self.object_type, *self.object_ids)  # до _produce

            return {'MeteringDevicesValues':  # Множественное
                self._produce(self._metering_values, meters)}

        def _preload(self):

            # WARN сопоставляются при формировании запроса операции
            self._meter_guids = HouseManagement.load_meter_guids(self,
                self.object_type, *self.object_ids)

        def _filter(self, object_ids: tuple) -> list:

            return super(ImportOperation, self)._filter(object_ids)  # не None

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            if request_data.get('object_type') not in GUID.METER_TAGS:  # тип?
                return False

            if 'period' not in request_data:  # не определен для операции?
                return False

            return True

        def area_meterings(self, metering_period: datetime = None):
            """
            Передача показаний ИПУ помещений дома за (текущий) период

            Начиная с 13.1.4.1 можно передать показания за любой период!

            Текущее показание – ежемесячно импортируемые показания ПУ
            размещается в ГИС ЖКХ плательщиком или организацией, оказывающей
            коммунальные услуги. Текущее показание не может быть меньше
            ближайшего по дате в прошлом контрольного, но может быть меньше
            предыдущего текущего показания.

            Передавать показания ПУ необходимо по мере поступления информации
            в Информационную систему поставщика информации в целях отражения
            в ГИС ЖКХ актуальных сведений.

            Контрольные показания снимаются при поверке ПУ и размещаются
            в ГИС ЖКХ организацией, оказывающей коммунальные услуги.
            Исполнитель имеет право осуществлять не чаще 1 раза в 6 месяцев
            проверку состояния ПУ и правильность снятия показаний потребителем.
            """
            with self.load_context as context:  # WARN сохраняем в случае ошибки
                if not metering_period:
                    metering_period = get_period()  # или текущий
                elif metering_period.day != 1:
                    metering_period = get_period(metering_period)

                meter_ids: list = AreaMeter.objects(__raw__={
                    'area.house._id': self.house_id,  # в помещениях дома
                    'readings.period': metering_period,  # за месяц показаний
                    **AreaMeter.working_meter_query(),  # действующие ИПУ
                }).distinct('id')  # получаем идентификаторы ИПУ с показаниями

                if not meter_ids:  # нет ИПУ с показаниями за период?
                    raise NoDataError("Отсутствуют подлежащие выгрузке ИПУ"
                        f" с показаниями за {fmt_period(metering_period)}")

            if context.exception:  # ошибка плановой операции?
                return  # завершаем выполнение

            self.log(info="Выгружаются показания за"
                f" {fmt_period(metering_period)} {len(meter_ids)}"
                f" ИПУ помещений управляемого {self.provider_name}"
                f" дома {self.house_address}")

            self(*meter_ids,
                period=metering_period, object_type=GisObjectType.AREA_METER)

        def house_meterings(self, metering_period: datetime = None):
            """Передача показаний ОДПУ дома за (текущий) период"""
            with self.load_context as context:  # WARN сохраняем в случае ошибки
                if not self.house.gis_collective:
                    self.warning("Выгрузка показаний ОДПУ выполняется"
                        " вопреки запрету выгрузки показаний ПУ дома")

                if not metering_period:
                    metering_period = get_period()  # или текущий
                elif metering_period.day != 1:
                    metering_period = get_period(metering_period)

                meter_ids: list = HouseMeter.objects(__raw__={
                    'house._id': self.house_id,  # установленные в доме
                    'readings.period': metering_period,  # за месяц показаний
                    **HouseMeter.working_meter_query(),  # действующие ОДПУ
                }).distinct('id')  # получаем идентификаторы ОДПУ с показаниями

                if not meter_ids:  # нет ОДПУ с показаниями за период?
                    raise NoDataError("Отсутствуют подлежащие выгрузке ОДПУ"
                        f" с показаниями за {fmt_period(metering_period)}")

            if context.exception:  # ошибка плановой операции?
                return  # завершаем выполнение

            self.log(info="Выгружаются показания за"
                f" {fmt_period(metering_period)} {len(meter_ids)}"
                f" ОДПУ управляемого {self.provider_name}"
                f" дома {self.house_address}")

            self(*meter_ids, FIASHouseGuid=self.fias_guid,  # Необязательное(?)
                period=metering_period, object_type=GisObjectType.HOUSE_METER)
