from app.gis.core.web_service import WebService
from app.gis.core.custom_operation import ExportOperation

from app.gis.models.choices import GisManagerContext
from app.gis.models.nsi_ref import nsiRef

from app.gis.utils.common import sb
from app.gis.utils.nsi import get_item_name, \
    get_element_name, get_actual_elements


class NsiItemExportOperation(ExportOperation):

    def _store(self, export_result):  # : NsiItemType
        """
        Сохранить данные элементов общих справочников
        """
        registry_number: int = export_result.NsiItemRegistryNumber
        item_name: str = get_item_name(registry_number)

        self.log(warn=f"Сохранение элементов справочника №{registry_number}"
            " может занять продолжительное время")  # TODO bulk_write

        # TODO полученные элементы справочников сохраняются по одному
        for element in get_actual_elements(export_result.NsiElement):
            element_name: str = get_element_name(element.NsiElementField,
                item_name)  # имя поля иногда совпадает с названием спр-ка

            # сохраняем запись NSI, GUID сохранять не нужно!
            nsiRef.store(element.GUID, registry_number, element.Code,
                element_name)  # без provider_id - общий справочник
            self.log("Сохранен элемент общего справочника"
                f" №{registry_number}.{element.Code}: {sb(element_name)}")

        self.log(info=f"Элементы общего справочника №{registry_number}:"
            f" {sb(item_name)} успешно сохранены")


class NsiCommon(WebService):
    """Асинхронный сервис экспорта общих справочников подсистемы НСИ"""

    IS_COMMON = True  # сервис с анонимными операциями (без домов)

    class exportNsiList(ExportOperation):

        VERSION = "10.0.1.2"
        GET_STATE_DELAY = [2, 5, 10, 30, 60]

        # TODO _store

    class exportNsiItem(NsiItemExportOperation):

        VERSION = "10.0.1.2"
        GET_STATE_DELAY = [2, 5, 10, 30, 60]

        @property
        def description(self) -> str:

            return f"№{self.request['RegistryNumber']}"  # Int32

    class exportNsiPagingItem(NsiItemExportOperation):

        VERSION = "10.0.1.2"
        GET_STATE_DELAY = [5, 10, 30, 60, 120]

        @property
        def description(self) -> str:

            return f"№{self.request['RegistryNumber']}" \
                f" стр. {self.request.get('Page') or 1}"  # постраничная

        def _parse(self, state_result):

            with self.manager(GisManagerContext.PARSE):  # WARN в случае ошибки
                nsi_paging_item = state_result.NsiPagingItem  # стр. справочника

                registry_number: int = nsi_paging_item.NsiItemRegistryNumber
                assert self.request['RegistryNumber'] == registry_number

                total_pages: int = nsi_paging_item.TotalPages
                current_page: int = nsi_paging_item.CurrentPage
                assert self.request['Page'] == current_page

                # записываем номер страницы и их общее количество
                # self._record.fraction = [current_page, total_pages]

                if current_page < total_pages:  # не последняя страница?
                    next_record = self._record.heir(  # идентичная операция
                        Page=current_page + 1  # со следующим номером страницы
                    )
                    next_record.save()  # WARN не сохраняется при создании

                    self.log(warn=f"Загружается {current_page + 1} страница из"
                        f" {total_pages} общего справочника №{registry_number}:"
                        f" {sb(get_item_name(registry_number))}")
                    self.execute(next_record.generated_id)  # следующая операция
                    # WARN текущая запись сохраняется менеджером (в store)

            return nsi_paging_item  # элемент передается в метод сохранения
