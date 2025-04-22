from app.gis.core.async_operation import AsyncOperation
from app.gis.core.exceptions import GisError

from app.gis.models.guid import GUID


class ExportOperation(AsyncOperation):

    # рекомендуется перезапускать запрос, в случае долгой обработки ГИС ЖКХ
    GET_STATE_DELAY = [5, 10, 30, 60, 120, 300, 900, 1800, 3600]

    _missing_ids = set()  # перечень отсутствующих (идентификаторов) объектов

    @property
    def is_import(self) -> bool:

        return False

    def missing(self, guid: GUID):
        """
        Данные объекта отсутствуют в ГИС ЖКХ
        """
        guid.reset()  # сбрасываем (неактуальные) данные ГИС ЖКХ

        self.failure(guid, f"Данные {guid.title} отсутствуют в ГИС ЖКХ")

        if not self['export_missing']:  # не выгружаем отсутствующие?
            return
        elif guid.object_id in self._missing_ids:  # уже в списке?
            self.log(warn=f"Данные {guid.tag}: {guid.object_id} повторно"
                " добавляются в список подлежащих выгрузке в ГИС ЖКХ")
            return

        self._missing_ids.add(guid.object_id)  # WARN подлежит выгрузке
        self.log(info=f"Данные {guid.tag}: {guid.object_id} подлежат"
            f" выгрузке в ГИС ЖКХ после завершения {self.record_id}")

    def _import(self):
        """
        Переопределяемый метод выгрузки отсутствующих в ГИС ЖКХ данных
        """
        self.warning("Выгрузка отсутствующих в ГИС ЖКХ"
            " данных не поддерживается операцией")

    def conclude(self):

        if self['export_missing'] and self._missing_ids:  # отсутствующие?
            self.log(warn=f"Требуется выгрузка {len(self._missing_ids)}"
                " отсутствующих в ГИС ЖКХ (идентификаторов) объектов")
            self._import()  # вызываем переопределяемый метод выгрузки

        super().conclude()  # выполняем последующую операцию


class ImportOperation(AsyncOperation):

    @property
    def is_import(self) -> bool:

        return True

    @property
    def is_updating(self) -> bool:
        """Обновлять выгруженные (имеющиеся) в ГИС ЖКХ данные?"""
        # повторная выгрузка разрешена или автоматическая выгрузка?
        return self['update_existing'] or self.is_scheduled

    def _issue(self, transport_guid: str, errors: list):
        """
        Зафиксировать полученные с транспортным идентификатором ошибки
        """
        error_message: str = GisError.message_of(*errors)  # все ошибки

        if transport_guid in self._mapped_guids:  # сопоставлен?
            guid: GUID = self._mapped_guids[transport_guid]  # не извлекаем
            self.failure(guid, error_message)  # подлежит сохранению с ошибкой
        else:  # (транспортный) идентификатор НЕ сопоставлен!
            self.warning(error_message)

    def _restore_mapping(self):

        self._mapped_guids: dict = GUID.assemble(self.record_id)  # str : GUID

        self.log(f"Загружены {len(self._mapped_guids)} сопоставленных"
            f" (транспортных) идентификатора операции {self.record_id}")

    def _parse(self, state_result) -> list:

        if state_result.ErrorMessage:  # : zeep.objects.ErrorMessageType
            raise GisError.from_result(state_result.ErrorMessage)

        import_results: list = []

        for common_result in state_result.ImportResult:  # : CommonResultType
            if common_result.Error:  # получена ошибка?  # Множественное
                self._issue(common_result.TransportGUID, common_result.Error)
            elif common_result.TransportGUID in self._mapped_guids:
                import_results.append(common_result)  # готовим к сохранению
            else:  # транспортный идентификатор не сопоставлен!
                self.warning("Не сопоставлены данные ГИС ЖКХ с транспортным"
                    f" идентификатором {common_result.TransportGUID}")

        return import_results

    def _store(self, import_results: list):
        """
        Сохранить полученный идентификатор (с данными) ГИС ЖКХ
        """
        self.log(warn="Метод сохранения результата выполнения операции"
            " импорта не переопределен и используется обобщенный")

        for result in import_results:
            guid: GUID = self._mapped_guids[result.TransportGUID]  # : str

            self.success(guid, result.GUID,  # идентификатор сущности ГИС ЖКХ
                unique=result.UniqueNumber,  # Уникальный реестровый номер
                updated=result.UpdateDate)  # Дата модификации  # Обязательное

    def _is_skippable(self, guid: GUID) -> bool:
        """
        Объект НЕ подлежит повторной выгрузке в ГИС ЖКХ?
        """
        if guid is None:  # данные ГИС ЖКХ отсутствуют?
            return True  # TODO assert?
        elif guid.deleted:  # объект аннулирован?
            return False  # допускается повторная выгрузка
        elif self.is_updating:  # принудительное обновление?
            return False  # подлежит выгрузке в любом случае
        elif guid.gis:  # имеется идентификатор ГИС ЖКХ?
            self._unmap(guid)  # WARN отменяем транспортное сопоставление
            return True  # не подлежит повторной выгрузке
        else:  # отсутствуют данные ГИС ЖКХ!
            return False  # подлежит выгрузке в ГИС ЖКХ

    def _filter(self, object_ids: tuple) -> list:
        """
        Получить только идентификаторы объектов без данных ГИС ЖКХ
        """
        # обновляются принудительно, без типа или идентификаторов объектов?
        if self.is_updating or not self.object_type or not object_ids:
            return super()._filter(object_ids)  # стандартный фильтр операции

        ids_with_guids: dict = self.owned_guids(self.object_type, *object_ids)

        no_guid_ids: list = [_id for _id in object_ids
            if _id is not None and _id not in ids_with_guids]

        self.log(warn=f"Получены {len(no_guid_ids)} подлежащих выгрузке"
            f" из {len(object_ids) or 'отсутствующих'} аргументов запроса"
            f" операции {self.record_id}")

        return no_guid_ids


class HouseManagementOperation(ImportOperation):

    def _parse(self, state_result) -> list:

        if state_result.ErrorMessage:  # : zeep.objects.ErrorMessageType
            raise GisError.from_result(state_result.ErrorMessage)

        common_results: list = []

        for import_result in state_result.ImportResult:  # : ImportResult
            if import_result.ErrorMessage:  # : ErrorMessageType
                raise GisError.from_result(import_result.ErrorMessage)

            for common_result in import_result.CommonResult:  # Множественное
                if common_result.Error:  # получена ошибка?
                    self._issue(common_result.TransportGUID,  # : str
                        common_result.Error)  # Множественное!
                elif common_result.TransportGUID in self._mapped_guids:
                    common_results.append(common_result)  # готовим к сохранению
                else:  # транспортный идентификатор не сопоставлен!
                    self.warning("Не сопоставлены данные ГИС ЖКХ с транспортным"
                        f" идентификатором {common_result.TransportGUID}")

        return common_results


class ServiceOperation(ImportOperation):

    _provider_mappings: dict = None  # сопоставленные услуги (ТП) провайдера

    from processing.models.billing.service_type import ServiceTypeGisName

    @property
    def _provider_binds(self) -> dict:
        """Сопоставления услуг (ТП) провайдера с элементами справочников"""
        from processing.models.billing.service_type import ServiceTypeGisBind

        if not self._provider_mappings:  # не загружались?
            self._provider_mappings: dict = \
                ServiceTypeGisBind.mappings_of(self.provider_id)
            self.log("Сопоставленные с элементами справочников"
                " услуги провайдера:\n\t" + '\n\t'.join(f"{title}: "
                    + ', '.join(bind[1] or str(bind[0]) for bind in binds)
                        for title, binds in self._provider_mappings.items()))

        return self._provider_mappings

    @staticmethod
    def _desc(reference: ServiceTypeGisName) -> str:
        """Описание элемента частного справочника"""
        return f"{reference.reg_num}.{reference.code}: «{reference.name}»"

    def _map(self, ref: ServiceTypeGisName) -> ServiceTypeGisName:
        """
        Сопоставить элемент частного справочника

        :param ref: экземпляр элемента справочника
        """
        ref.record_id = self.record_id  # привязываем к (записи об) операции
        ref.transport = self.generated_guid  # : UUID - новый идентификатор

        ref.is_changed = True  # (безальтернативно) подлежит сохранению

        self._mapped_guids[str(ref.transport)] = ref  # WARN не GUID

        return ref.save()  # возвращаем сохраненный элемент справочника

    def _restore_mapping(self):

        self._mapped_guids: dict = \
            ServiceOperation.ServiceTypeGisName.assemble(self.record_id)

        self.log(f"Загружены {len(self._mapped_guids)} сопоставленных"
            f" элементов справочников операции {self.record_id}")

    def _issue(self, transport_guid: str, errors: list):

        error_message: str = GisError.message_of(*errors)  # описание ошибок

        if transport_guid in self._mapped_guids:  # сопоставлен?
            ref: ServiceOperation.ServiceTypeGisName = \
                self._mapped_guids[transport_guid]  # : str
            # невозможно сохранить ошибку в элементе справочника
            self.warning(f"Для элемента справочника {self._desc(ref)}"
                f" получена ошибка: {error_message}")
        else:  # (транспортный) идентификатор НЕ сопоставлен!
            self.warning(f"С транспортным идентификатором {transport_guid}"
                f" получена ошибка: {error_message}")

    def _parse(self, state_result):

        if state_result.ErrorMessage:  # : zeep.objects.ErrorMessageType
            raise GisError.from_result(state_result.ErrorMessage)

        import_results: list = []

        for common_result in state_result.ImportResult:  # : CommonResultType
            # WARN в случае ошибки элемент результата отсутствует!
            if common_result.Error:  # ошибка элемента справочника?
                self._issue(common_result.TransportGUID, common_result.Error)
            elif common_result.TransportGUID in self._mapped_guids:
                import_results.append(common_result)
            else:  # транспортный идентификатор не сопоставлен!
                self.warning("Не сопоставлены данные ГИС ЖКХ элемента"
                    f" №{common_result.UniqueNumber} с транспортным"
                    f" идентификатором {common_result.TransportGUID}")

        return import_results

    def _store(self, import_results: list):

        for result in import_results:
            ref: ServiceOperation.ServiceTypeGisName = \
                self._mapped_guids[result.TransportGUID]  # : str

            ref.guid = result.GUID  # записываем ид. элемента

            if ref.code != result.UniqueNumber:
                self.log(warn=f"Код элемента справочника {self._desc(ref)}"
                    f" разнится с полученным из ГИС ЖКХ: {result.UniqueNumber}")
                ref.position_number = result.UniqueNumber

            ref.record_id = None  # обнуляем идентификатор записи об операции

            ref.save()  # WARN сохраняем ServiceTypeGisName

            self.log(info=f"Элемент справочника услуг {self._desc(ref)}"
                f" сохранен с ид. ГИС ЖКХ {ref.guid}")

    def flush_guids(self):

        pass  # TODO элементы справочника сохраняются по одному!
