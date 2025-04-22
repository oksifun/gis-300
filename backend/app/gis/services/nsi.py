from collections import defaultdict

from app.gis.core.web_service import WebService
from app.gis.core.async_operation import AsyncOperation
from app.gis.core.custom_operation import ExportOperation, ServiceOperation
from app.gis.core.exceptions import NoRequestWarning, NoGUIDError, PendingSignal

from app.gis.utils.common import as_guid, get_time, sb
from app.gis.utils.nsi import get_element_name, get_element_unit, \
    get_actual_elements, get_last_elements, resource_nsi_code_of, \
    okei_code_of, service_nsi_code_of, PRIVATE_GROUP, REFERENCE_NAMES

from app.gis.models.nsi_ref import nsiRef, PRIVATE_SERVICES

from processing.models.billing.service_type import \
    ServiceTypeGisName, ServiceTypeGisBind


class Nsi(WebService):
    """
    Асинхронный сервис частной НСИ

    Нельзя создать элементы с одним названием и ЕИ в одном справочнике

    Элементы справочника с одним названием, но разными ЕИ считаются разными
    """

    @classmethod
    def load_provider_refs(cls, _import: AsyncOperation, *reg_num_s: int):
        """
        Загрузить данные элементов (частных) справочников услуг организации
        """
        prov_refs: dict = {}  # { RegistryNumber : { 'Code' : as_req } }

        for ref in nsiRef.provider_services(_import.provider_id, *reg_num_s):
            assert isinstance(ref, ServiceTypeGisName)
            prov_refs.setdefault(ref.reg_num, {})[ref.code] = ref.as_req

        if all(reg_num in prov_refs for reg_num in reg_num_s):
            _import.log(info=f"Загружены данные {', '.join(prov_refs)}"
                f" частных справочников (услуг) организации")
            return prov_refs  # возвращаем требуемые
        elif 'Service' in _import.acquired:  # нет требования загрузки?
            raise NoGUIDError("Не загружены идентификаторы"
                " ГИС ЖКХ элементов частных справочников (услуг)")

        _export = cls.exportDataProviderNsiItem(
            _import.provider_id, _import.house_id
        )
        _import.follow(_export)  # ставим текущую операцию в очередь

        _export.private_services()  # инициируем загрузку справочников услуг

        # WARN запись об операции сохраняется при выходе из контекста
        raise PendingSignal("Операция отложена до завершения"
            " загрузки справочников услуг ГИС ЖКХ организации")

    class exportDataProviderNsiItem(ExportOperation):
        """Получить данные справочников поставщика информации"""

        IS_HOMELESS = True  # операция без (загрузки данных ГИС ЖКХ) дома

        VERSION = "10.0.1.2"

        @property
        def description(self) -> str:

            return f"№{self.request['RegistryNumber']}"  # Int32

        def _housing_services(self):
            """
            Создать "Жилищные услуги" (НИС 50) организации
            """
            REGISTRY_NUMBER = 50

            nsi_title: str = REFERENCE_NAMES.get(REGISTRY_NUMBER) \
                or "Жилищные услуги"

            existing: dict = {gis['position_number']: gis['gis_title']
                for gis in ServiceTypeGisName.objects(
                    provider=self.provider_id, closed=None,
                    reference_number=str(REGISTRY_NUMBER),  # WARN не int
                ).as_pymongo()}

            missing: dict = {ref['code']: ref['name']
                for ref in nsiRef.elements(REGISTRY_NUMBER)
                    if ref['code'] not in existing}

            if missing:
                for code, name in missing.items():
                    ServiceTypeGisName(
                        provider=self.provider_id, created=get_time(),
                        gis_title=name, position_number=code,  # : str
                        reference_number=str(REGISTRY_NUMBER),  # WARN не int
                        reference_name=nsi_title,
                    ).save()

                self.log(warn=f"Добавлены {sb(nsi_title)} организации: "
                    + ', '.join(sb(name) for name in missing.values()))
            else:
                self.log(info=f"Найдены {sb(nsi_title)} организации: "
                    + ', '.join(sb(name) for name in existing.values()))

        def _store_element(self, element):
            """
            Сохранить услугу (элемент 1, 51 или 337 частного справочника)

            :param element: NsiElementType
            """
            code: str = element.Code  # код элемента справочника
            name = get_element_name(element.NsiElementField, self._item_name)
            unit: str = get_element_unit(element.NsiElementField)  # ЕИ

            desc = f"№{self._reg_num}.{code}: {sb(name)}"  # описание элемента
            actual_or_not = 'актуальном' if element.IsActual \
                else 'аннулированном'

            # ищем среди имеющихся и ИЗВЛЕКАЕМ элемент справочника услуг
            existing: ServiceTypeGisName = self._gis_names.pop(code, None)

            if not existing:  # услуга не найдена по коду?
                created = element.StartDate or element.Modified \
                    or self._item_created  # или дата создания *справочника*
                existing = ServiceTypeGisName(
                    provider=self.provider_id, gis_title=name,
                    created=created,  # closed запишем позже
                    reference_name=REFERENCE_NAMES[self._reg_num],
                    reference_number=str(self._reg_num), position_number=code,
                    guid=as_guid(element.GUID)
                )  # создаем, но НЕ сохраняем услугу ГИС ЖКХ
                self.log(warn=f"Создана запись (GisName) об {actual_or_not}"
                    f" элементе справочника услуг {desc}")
            elif str(existing.guid) != element.GUID:  # иной ид-р ГИС ЖКХ?
                # идентификаторы ГИС ЖКХ сущностей СИТ и ППАК - отличаются!
                if existing.guid:  # ид. ГИС ЖКХ уже был загружен?
                    self.warning(f"Элемент справочника услуг {desc} имеет"
                        " отличный от полученного идентификатор ГИС ЖКХ")
                else:  # ид. ГИС ЖКХ загружен не был!
                    self.log(warn=f"Элемент справочника услуг {desc}"
                        " не имеет (загруженного) идентификатора ГИС ЖКХ")
                # необязательно преобразовывать str при записи в UUIDField
                existing.guid = as_guid(element.GUID)  # записываем ид. ГИС ЖКХ

            if element.IsActual:  # актуальный элемент справочника?
                existing.closed = None
            else:  # элемент справочника неактуальный или недействующий!
                existing.closed = element.Modified or element.EndDate

            if existing.name in self._provider_binds:  # сопоставленные услуги?
                self.log(f"С элементом справочника {desc}"
                    " сопоставлены услуги: " + ', '.join(str(bind[0])
                        for bind in self._provider_binds.get(existing.name)))
            elif not existing.closed:  # не сопоставлены с актуальным элементом?
                self.log(warn=f"С элементом справочника {desc}"
                    " НЕ сопоставлены услуги тарифного плана")

            if existing.name != name:  # другое название элемента?
                existing.gis_title = name  # корректируем название элемента
                self.warning(f"Элемент справочника услуг {desc} имел"
                    f" отличное от полученного название {sb(name)}")

            existing.okei_code = unit  # записываем единицу измерения

            # обновляем связи (GisBind) услуг (ServiceType) с эл. НСИ (GisName)
            # updated_binds: int = ServiceTypeGisBind.objects(
            #     provider=self.provider_id, gis_title=name, closed=None
            # ).update(closed=found.closed)  # кол-во измененных записей
            # if updated_binds:  # сопоставления услуг обновлены?
            #     self.log.debug(f"Обновлено {updated_binds} сопоставлений"
            #     f" услуги ГИС ЖКХ {sb(name)} оказываемой {self.provider_id}")
            existing.save()  # сохраняем услугу (с идентификатором) ГИС ЖКХ
            self.log(f"Запись (GisName) об {actual_or_not} элементе {desc}"
                f" сохранена с ид. {existing.id}")

        def _store_item(self, nsi_item):
            """Сохранить частный справочник услуг"""
            def _not_actual_or_guid(ref) -> str:
                return " - НЕ актуален!" if ref.closed \
                    else f" ~ {ref.guid or 'БЕЗ идентификатора'}"

            # находим последние (включай актуальные) версии элементов
            elements: list = get_last_elements(nsi_item.NsiElement)
            self.log(info=f"Получены данные {len(elements)} элементов"
                f" справочника услуг №{self._reg_num}:\n\t"
                    + ('\n\t'.join(f"{elem.Code} ~ {elem.GUID}"
                        for elem in elements) or 'ОТСУТСТВУЮТ'))

            # допускаются услуги с одним названием, но разными ЕИ!
            self._gis_names: dict = {ref.code: ref for ref in
                nsiRef.provider_services(self.provider_id, self._reg_num,
                    only_actual=False)}  # в том числе аннулированные
            self.log(f"Имеющиеся элементы справочника №{self._reg_num}:\n\t"
                + ('\n\t'.join(f"{code}: {ref} {_not_actual_or_guid(ref)}"
                    for code, ref in self._gis_names.items()) or 'ОТСУТСТВУЮТ'))

            self._provider_binds = ServiceTypeGisBind.mappings_of(
                self.agent_id or self.provider_id)  # услуги УО сопоставляет РЦ
            self.log("Сопоставленные с элементами справочников услуги:\n\t"
                + ('\n\t'.join(f"{title}: "
                    + ', '.join(bind[1] or str(bind[0]) for bind in binds)
                        for title, binds in self._provider_binds.items())
                or 'ОТСУТСТВУЮТ'))

            for element in elements:  # элементы справочника услуг
                self._item_created = nsi_item.Created  # может понадобиться
                self._store_element(element)

            self.log(info=f"Принадлежащий {self.provider_name}"
                f" справочник услуг №{self._reg_num} сохранен")

        def _store(self, export_result):  # : NsiItemType

            self._reg_num: int = export_result.NsiItemRegistryNumber  # № спр.
            self._item_name: str = PRIVATE_GROUP.get(self._reg_num)  # название

            if self._reg_num in PRIVATE_SERVICES:  # справочник услуг?
                self._store_item(export_result)  # сохраняем справочник
                self._housing_services()  # WARN создаем "Жилищные услуги"
            # TODO работы и услуги организации (НСИ 59, 219) есть в Системе
            else:  # иной (НЕ услуг) частный справочник загружаем как общий!
                for element in get_actual_elements(export_result.NsiElement):
                    element_name: str = get_element_name(
                        element.NsiElementField, self._item_name)

                    # TODO собрать элементы справочника и сохранить все вместе
                    nsiRef.store(element.GUID, self._reg_num, element.Code,
                        element_name, self.provider_id)
                    self.log(f"Полученный элемент с кодом {element.Code}"
                        f" (частного) справочника №{self._reg_num} сохранен")

                self.warning(f"Принадлежащий {self.provider_name} (частный)"
                    f" справочник №{self._reg_num} сохранен как общий")

        def private_services(self):
            """
            Загрузить частные справочники услуг (1, 51, 337) организации
            """
            for registry_number in PRIVATE_SERVICES:
                self.log(info=f"Загружается принадлежащий {self.provider_name}"
                    f" частный справочник услуг №{registry_number}")

                self(RegistryNumber=registry_number)

        def by_reg_num(self, registry_number: int):

            assert registry_number in PRIVATE_GROUP, \
                f"Справочник №{registry_number} не является частным"

            self.log(info=f"Загружается принадлежащий {self.provider_name}"
                f" частный справочник №{registry_number}")

            self(RegistryNumber=registry_number)

    class importAdditionalServices(ServiceOperation):
        """Передать данные справочника 1: Дополнительные услуги"""

        VERSION = "10.0.1.2"
        ELEMENT_LIMIT = 1000

        def _additional_service(self, reference: ServiceTypeGisName):

            service_binds: list = self._provider_binds.get(reference.name)
            if not service_binds:  # услуги не сопоставлены?
                self.warning(f"С элементом справочника ДУ {sb(reference.name)}"
                    " не сопоставлены услуги (ТП) организации")
                return  # пропускаем несопоставленные элементы справочника

            if not reference.okei_code:  # отсутствует код ед. измерения?
                reference.okei_code = \
                    okei_code_of(*{bind[1] for bind in service_binds})
                self.warning(f"Код единицы измерения ДУ {sb(reference.name)}"
                    f" определен как {reference.okei_code}")

            additional_service_data = dict(
                TransportGUID=self._map(reference).transport,  # сохраняем!
                AdditionalServiceTypeName=reference.name,
                OKEI=reference.okei_code,  # WARN обязательный атрибут!
            )
            if not reference.guid:  # элемент справочника не имеет ид. ГИС ЖКХ?
                # ошибка в случае существования идентичной услуги в ГИС ЖКХ!
                self.log(info="В справочнике ДУ создается новый элемент"
                    f" {sb(reference.name)} с ЕИ {sb(reference.okei_code)}")
            else:  # элемент справочника услуг был изменен!
                self.log(info="В справочнике ДУ обновляется имеющийся элемент"
                    f" {sb(reference.name)} с ЕИ {sb(reference.okei_code)}")
                additional_service_data['ElementGuid'] = reference.guid

            return additional_service_data

        def _compose(self):

            references = ServiceTypeGisName.objects(id__in=self.object_ids)
            if references.count() == 0:  # элементы справочника не найдены?
                raise NoRequestWarning("Справочник дополнительных услуг"
                    " организации не содержит ни одного элемента")

            self.log(f"Загруженные элементы справочника доп. услуг:\n\t"
                + '\n\t'.join(('Аннулированный' if ref.closed else 'Актуальный')
                    + f" {ref.reg_num}.{ref.code}: {ref.name}"
                        f" ~ {ref.guid or 'БЕЗ идентификатора'}"
                for ref in references if isinstance(ref, ServiceTypeGisName)))

            return {'ImportAdditionalServiceType':  # Множественное
                self._produce(self._additional_service, references)}

        def actual(self):
            """
            Выгрузить в ГИС ЖКХ актуальные Дополнительные услуги организации
            """
            actual_service_ids: list = \
                nsiRef.provider_services(self.provider_id, 1).distinct('id')

            self(*actual_service_ids)

        # TODO RecoverAdditionalServiceType, DeleteAdditionalServiceType

    class importMunicipalServices(ServiceOperation):
        """Передать данные справочника 51: Коммунальные услуги"""

        VERSION = "11.0.0.4"
        ELEMENT_LIMIT = 1000

        def _municipal_service(self, reference: ServiceTypeGisName):

            service_binds: list = self._provider_binds.get(reference.name)
            if not service_binds:  # услуги не сопоставлены?
                self.warning(f"С элементом справочника КУ {sb(reference.name)}"
                    " не сопоставлены услуги (ТП) организации")
                return  # не выгружаем несопоставленные элементы справочника

            service_codes: set = {bind[1] for bind in service_binds}  # : str

            service_nsi_ref: dict = \
                nsiRef.common(3, service_nsi_code_of(*service_codes))
            assert service_nsi_ref, \
                f"Вид КУ (НСИ 3) {sb(reference.name)} не определен"

            resource_nsi_ref: dict = \
                nsiRef.common(2, resource_nsi_code_of(*service_codes))
            assert resource_nsi_ref, \
                f"Вид КР (НСИ 2) услуги {sb(reference.name)} не определен"

            if not reference.okei_code:  # отсутствует код ед. измерения?
                reference.okei_code = okei_code_of(*service_codes)
                self.warning(f"Код единицы измерения КУ {sb(reference.name)}"
                    f" определен как {reference.okei_code}")

            municipal_service_data = dict(
                TransportGUID=self._map(reference).transport,  # сохраняем!
                MunicipalServiceRef=service_nsi_ref,
                MainMunicipalServiceName=reference.name,
                MunicipalResourceRef=resource_nsi_ref,
                # GeneralNeeds, SelfProduced, OKEI - не используются!
                SortOrderNotDefined=True,  # порядок сортировки не задан?
            )
            if reference.guid:  # элемент справочника с ид. ГИС ЖКХ?
                self.log(info="В справочнике КУ обновляется имеющийся элемент"
                    f" {sb(reference.name)} с ЕИ {sb(reference.okei_code)}")
                municipal_service_data['ElementGuid'] = reference.guid
                # ошибка в случае существования идентичной услуги в ГИС ЖКХ!
            else:  # элемент справочника без ид. ГИС ЖКХ!
                self.log(info=f"В справочнике КУ создается новый элемент"
                    f" {sb(reference.name)} с ЕИ {sb(reference.okei_code)}")

            return municipal_service_data  # : dict

        def _compose(self):

            references = ServiceTypeGisName.objects(id__in=self.object_ids)
            if references.count() == 0:  # элементы справочника не найдены?
                raise NoRequestWarning("Справочник коммунальных услуг"
                    " организации не содержит ни одного элемента")

            self.log("Загруженные элементы справочника коммунальных услуг:\n\t"
                + '\n\t'.join(('Аннулированный' if ref.closed else 'Актуальный')
                    + f" {ref.reg_num}.{ref.code}: {ref.name}"
                        f" ~ {ref.guid or 'БЕЗ идентификатора'}"
                for ref in references if isinstance(ref, ServiceTypeGisName)))

            return {'ImportMainMunicipalService':  # Множественное
                self._produce(self._municipal_service, references)}

        def actual(self):
            """
            Выгрузить в ГИС ЖКХ актуальные Коммунальные услуги организации
            """
            actual_service_ids: list = \
                nsiRef.provider_services(self.provider_id, 51).distinct('id')

            self(*actual_service_ids)

        # TODO RecoverMainMunicipalService, DeleteMainMunicipalService

    class importGeneralNeedsMunicipalResource(ServiceOperation):
        """
        Передать данные справочника 337: Коммунальные ресурсы на ОДН в МКД
        """
        VERSION = "12.2.2.1"
        ELEMENT_LIMIT = 1000

        def _general_resource(self, reference: ServiceTypeGisName):

            general_municipal_resource_data = dict(
                TransportGUID=self._map(reference).transport,
                GeneralMunicipalResourceName=reference.name,
                MunicipalResourceRef=self._resource_nsi_ref,
                OKEI=reference.okei_code,  # WARN обязательный атрибут?!
                SortOrderNotDefined=True,  # порядок сортировки не задан?
            )
            if reference.guid:  # элемент справочника с ид. ГИС ЖКХ?
                self.log(info="В справочнике комм. ресурсов на ОДН обновляется"
                    f" существующий элемент {sb(reference.name)}")
                general_municipal_resource_data['ElementGuid'] = reference.guid
            else:  # элемент справочника без ид. ГИС ЖКХ!
                # ошибка в случае существования идентичной услуги в ГИС ЖКХ!
                self.log(info="В справочнике комм. ресурсов на ОДН"
                    f" создается новый элемент {sb(reference.name)}")

            return general_municipal_resource_data

        def _compose(self):

            references = ServiceTypeGisName.objects(id__in=self.object_ids)
            if references.count() == 0:  # элементы справочника не найдены?
                raise NoRequestWarning("Справочник комм. ресурсов на ОДН"
                    " организации не содержит ни одного элемента")

            self.log("Элементы справочника комм. ресурсов на ОДН:\n\t"
                + '\n\t'.join(('Аннулированный' if ref.closed else 'Актуальный')
                    + f" {ref.reg_num}.{ref.code}: {ref.name}"
                        f" ~ {ref.guid or 'БЕЗ идентификатора'}"
                for ref in references if isinstance(ref, ServiceTypeGisName)))

            # region ГРУППИРОВКА ЭЛЕМЕНТОВ ПО РЕСУРСУ
            grouped = defaultdict(list)  # int : [ ServiceTypeGisName ]

            for reference in references:
                service_binds: set = self._provider_binds.get(reference.name)
                if not service_binds:  # сопоставления не найдены?
                    self.warning(f"Для КР на ОДН {sb(reference.name)}"
                        " не сопоставлены услуги тарифного плана")
                    continue  # пропускаем ресурс без сопоставления

                self.log(f"Сопоставления {sb(reference.name)}:"
                    f" {', '.join(str(bind[0]) for bind in service_binds)}")

                service_codes: set = {bind[1] for bind in service_binds}

                if not reference.okei_code:  # отсутствует код ед. измерения?
                    reference.okei_code = okei_code_of(*service_codes)
                    self.warning(f"Код единицы измерения {reference.okei_code}"
                        f" определен для ресурса на ОДН {sb(reference.name)}")

                resource_nsi_code: int = resource_nsi_code_of(*service_codes)
                grouped[resource_nsi_code].append(reference)
            # endregion ГРУППИРОВКА ЭЛЕМЕНТОВ ПО РЕСУРСУ

            municipal_resources: list = []

            for resource_code, references in grouped.items():
                assert resource_code in {1, 2, 3, 8}, \
                    "Может быть: 1 - ХВ, 2 - ГВ, 3 - ЭЭ, 8 - Сточные воды"

                self._resource_nsi_ref: dict = nsiRef.common(2, resource_code)

                general_resources: list = \
                    self._produce(self._general_resource, references)

                top_level_municipal_resource = dict(
                    TransportGUID=self.generated_guid,  # не подлежит сохранению
                    ParentCode=resource_code,
                    ImportGeneralMunicipalResource=general_resources  # 1000
                )
                municipal_resources.append(top_level_municipal_resource)

            if not municipal_resources:  # нечего выгружать?
                raise NoRequestWarning("Отсутствуют подлежащие"
                    " выгрузке в ГИС ЖКХ ресурсы на ОДН организации")

            self.log(info=f"Выгружаются данные {len(municipal_resources)}"
                f" принадлежащих {self.provider_name} комм. ресурсов на ОДН")

            return dict(TopLevelMunicipalResource=municipal_resources)

        def actual(self):
            """
            Выгрузить в ГИС ЖКХ актуальные КР на ОДН организации
            """
            actual_service_ids: list = \
                nsiRef.provider_services(self.provider_id, 337).distinct('id')

            self(*actual_service_ids)

        # TODO RecoverGeneralMunicipalResource, DeleteGeneralMunicipalResource
