from bson import ObjectId

from app.gis.core.web_service import WebService
from app.gis.core.async_operation import AsyncOperation
from app.gis.core.custom_operation import ExportOperation
from app.gis.core.exceptions import NoGUIDError, PendingSignal, NoDataError

from app.gis.utils.common import sb
from app.gis.utils.providers import is_ogrn, ogrn_or_not, kpp_or_not

from app.gis.models.choices import GisObjectType
from app.gis.models.guid import GUID


from processing.models.billing.legal_entity import LegalEntity  # НЕ LegalTenant


class OrgRegistryCommon(WebService):
    """Асинхронный сервис обмена сведениями о поставщиках информации"""

    TARGET_NAMESPACE = 'organizations-registry-common'
    IS_COMMON = True  # сервис с анонимными операциями

    @classmethod
    def load_org_guid(cls, self: AsyncOperation):
        """
        Загрузить идентификатор ГИС ЖКХ организации
        """
        assert not self.IS_ANONYMOUS, "Анонимной операции" \
            " не требуется идентификатор ГИС ЖКХ поставщика информации"
        assert not self.provider_guid, "Загрузка идентификатора" \
            " ГИС ЖКХ поставщика информации не требуется"

        if (not self['load_requirements']  # WARN не has_requirements
                or GisObjectType.PROVIDER in self.acquired):  # не первый раз?
            raise NoGUIDError("Не загружен идентификатор"
                " ГИС ЖКХ (организации) поставщика информации")

        self.acquired[GisObjectType.PROVIDER] = 0  # признак загрузки

        _export = cls.exportOrgRegistry()  # WARN анонимная операция
        self.follow(_export)  # сохраняем запись текущей операции

        criteria: dict = _export.provider_criteria(self.provider_id)
        _export.prepare(SearchCriteria=[criteria])  # WARN Множественное

        # WARN данные поставщика информации обновляются при загрузке записи
        raise PendingSignal("Операция отложена до завершения"
            " загрузки данных ГИС ЖКХ поставщика информации")  # исключение

    @classmethod
    def load_entity_guids(cls, self: AsyncOperation, entities: dict):
        """
        Загрузить идентификаторы ГИС ЖКХ (организаций) ЮЛ
        """
        assert entities, "Список реквизитов требуемых юр. лиц пуст"

        entity_guids: dict = \
            self.required_guids(GisObjectType.LEGAL_ENTITY, *entities)

        if self.is_required(GisObjectType.LEGAL_ENTITY):  # требуется?
            _export = cls.exportOrgRegistry(
                self.provider_id  # WARN для отображения в списке операций
            )
            self.follow(_export)  # сохраняем запись о текущей операции

            # WARN только если нет данных или идентификатора ГИС ЖКХ
            entity_props: dict = {entity_id: props for entity_id, props
                in entities.items() if not entity_guids.get(entity_id)}  # bool

            search_criteria: list = _export.entity_criteria(entity_props)
            _export.prepare(SearchCriteria=search_criteria)  # Множественное!

            # запись об операции сохраняется при выходе из контекста
            raise PendingSignal("Операция отложена до завершения"
                " загрузки идентификаторов ГИС ЖКХ юр. лиц(а)")

        return entity_guids

    class exportOrgRegistry(ExportOperation):
        """Экспорт сведений из реестра организаций"""

        IS_ANONYMOUS = True  # анонимная операция (без дома)
        VERSION = "10.0.2.1"

        GET_STATE_DELAY = [2, 5, 10, 30, 60]

        @property
        def description(self) -> str:

            return '; '.join(f"{key}: {value}"
                for criteria in self.request['SearchCriteria']
                    for key, value in criteria.items())

        def _agent_ops(self, *id_s: ObjectId, **request_data) -> bool:

            return False  # WARN всегда выполняется текущей организацией

        def _restore_mapping(self):

            self._mapped_guids: dict = {}  # ProviderId: GUID
            self._ogrn_ids: dict = {}  # 'ОГРН': [ ProviderId,... ]

            for org_guid in GUID.objects(__raw__={
                'record_id': self.record_id,  # сопоставленные операции
                'unique': {'$ne': None},  # с ОГРН
            }):
                self._mapped_guids[org_guid.object_id] = org_guid

                self._ogrn_ids.setdefault(org_guid.unique, []) \
                    .append(org_guid.object_id)  # филиалы организации с ОГРН?

            assert self._mapped_guids, "Не найдены сопоставленные" \
                f" операции {self.record_id} идентификаторы организаций"

            self.log(info="Загружены сопоставленные по ОГРН идентификаторы"
                f" организаций операции {self.record_id}:\n\t"
                    + '\n\t'.join(f"{ogrn} ~ {', '.join(str(i) for i in ids)}"
                        for ogrn, ids in self._ogrn_ids.items()))

        def _store_org(self, exported):

            def get_ogrn(org) -> str:
                """ОГРН организации"""
                return (org.Legal.OGRN if org.Legal else  # юридическое лицо
                    org.Subsidiary.OGRN if org.Subsidiary else  # подразделение
                    org.Entrp.OGRNIP if org.Entrp else  # инд. предприниматель
                    None)  # НЕТ у ForeignBranchType - Филиал/Представит.Ино.ЮЛ

            def get_kpp(org) -> str:
                """КПП организации"""
                return (org.Legal.KPP if org.Legal else
                    org.Subsidiary.KPP if org.Subsidiary else
                    org.ForeignBranch.KPP if org.ForeignBranch else
                    None)  # НЕТ у EntpsType

            def _inn(org) -> str:
                """ИНН организации"""
                return (org.Legal.INN if org.Legal else
                    org.Subsidiary.INN if org.Subsidiary else
                    org.EntpsType.INN if org.EntpsType else
                    org.ForeignBranch.INN if org.ForeignBranch else
                    None)  # поле есть у всех видов организаций!

            def get_short_name(org) -> str:
                """Сокращенное наименование"""
                return ((org.Legal.ShortName if org.Legal
                    else f"ИП {org.Entrp.Surname} {org.Entrp.FirstName[:1]}."
                        f" {org.Entrp.Patronymic[:1]}." if org.Entrp
                    else org.ForeignBranch.ShortName if org.ForeignBranch
                    else org.Subsidiary.ShortName if org.Subsidiary
                else None) or '').strip()

            def get_full_name(org) -> str:
                """Полное наименование"""
                return ((org.Legal.FullName if org.Legal
                    else f"ИП {org.Entrp.Surname} {org.Entrp.FirstName[:1]}."
                        f" {org.Entrp.Patronymic[:1]}." if org.Entrp
                    else org.ForeignBranch.FullName if org.ForeignBranch
                    else org.Subsidiary.FullName if org.Subsidiary
                else None) or '').strip()

            def get_registration_date(org):  # datetime
                """Дата государственной регистрации"""
                return org.Legal.StateRegistrationDate if org.Legal \
                    else org.Entrp.StateRegistrationDate if org.Entrp \
                    else org.ForeignBranch.AccreditationStartDate \
                    if org.ForeignBranch else None  # Subsidiary

            version = exported.OrgVersion  # "версия" организации
            if version.ForeignBranch:  # TODO представительство иностранного ЮЛ?
                self.warning("Сохранение данных ГИС ЖКХ представительства"
                    " иностранного юридического лица не поддерживается")
                return  # данные представительства не подлежат сохранению

            ogrn: str = get_ogrn(version)
            assert ogrn, "Не определен ОГРН организации (поставщика информации)"

            org_name: str = get_short_name(version)  # Необязательное
            if org_name in {'', '-', '---'}:
                self.log(warn="Краткое наименование организации"
                    f" с ОГРН {ogrn} отсутствует в ГИС ЖКХ")
                org_name: str = get_full_name(version)  # ЗАГЛАВНЫМИ БУКВАМИ

            if not exported.isRegistered:  # True или None
                self.log(warn="Получены данные ГИС ЖКХ (филиала) организации"
                    f" {sb(org_name)} без регистрации (личного кабинета)")

            kpp: str = get_kpp(version)  # Код Причины Постановки (на учет)

            provider_ids: list = self._ogrn_ids.get(ogrn)  # по ОГРН
            if not provider_ids:  # организация не найдена?
                self.warning("Отсутствует сопоставление идентификатора"
                    f" организации {sb(org_name)} с ОГРН {ogrn}")
                provider_guid = None
            elif len(provider_ids) == 1:  # организация без филиалов?
                provider_id: ObjectId = provider_ids[0]  # единственный
                provider_guid = self._mapped_guids.get(provider_id)
                assert isinstance(provider_guid, GUID), \
                    f"Идентификатор организации {provider_id} не сопоставлен"

                provider_kpp: str = kpp_or_not(provider_guid.number)
                if not provider_kpp:  # = ''
                    self.log(warn=f"Получены данные организации {sb(org_name)}"
                        f" с отсутствующим в Системе КПП {kpp}")
                elif kpp and provider_kpp != kpp:
                    self.warning(f"Получены данные организации {sb(org_name)}"
                        f" с отличным от {sb(provider_kpp)} КПП {kpp}")
                # WARN данные найденной без КПП организации подлежат сохранению
            else:  # более одной организации с данным ОГРН!
                provider_guid = None
                for provider_id in provider_ids:
                    potential_guid = self._mapped_guids.get(provider_id)

                    if potential_guid is None:  # сопоставление не найдено?
                        continue
                    elif kpp_or_not(potential_guid.number) == kpp:  # по КПП?
                        provider_guid = potential_guid
                        break  # найдено точное соответствие
                    elif provider_guid.number is None:  # без КПП?
                        provider_guid = potential_guid
                        continue  # WARN продолжим искать с КПП

            if not isinstance(provider_guid, GUID):
                self.warning("Отсутствуют данные организации"
                    f" {sb(org_name)} с ОГРН {ogrn} и КПП {kpp}")
                return  # отсутствует подлежащий сохранению идентификатор

            if (version.Subsidiary and  # филиал (обособленное подразделение)?
                    provider_guid.is_changed):  # уже встречался (с другим КПП)?
                self.warning(f"Отброшены данные ГИС ЖКХ филиала с КПП {kpp}"
                    f" организации {sb(org_name)} с ОГРН {ogrn}")
                return  # данные филиала не подлежат сохранению

            # PPA - ид. зарегистрированной орг-ии, при создании Version = Root
            ppa_guid: str = (exported.orgPPAGUID  # Необязательное
                or version.orgVersionGUID)  # Обязательное

            provider_guid.desc = org_name  # записываем название организации

            # TODO roles: list = exported.organizationRoles (повторяются)

            if not version.IsActual:  # неактуальная запись?
                self.annulment(provider_guid, version.lastEditingDate, ppa_guid)
                return  # пропускаем неактуальную запись реестра

            self.success(provider_guid, ppa_guid,
                # ОГРН и КПП организации сохранены при формировании запроса
                exported.orgRootEntityGUID,  # ид. корневой сущности
                version.orgVersionGUID,  # ид. версии организации
                updated=get_registration_date(version))  # Дата регистрации

        def _store(self, export_results: list):

            self.log(f"Получены данные {len(export_results)} (филиалов)"
                " организаций из реестра поставщиков информации ГИС ЖКХ")

            for exported in export_results:  # : exportOrgRegistryResultType
                self._store_org(exported)  # сохраняем данные организации

        def _validate(self, object_id_s: tuple, request_data: dict) -> bool:

            search_criteria: list = request_data.get('SearchCriteria')

            if not isinstance(search_criteria, list) \
                    or len(search_criteria) < 1:
                raise NoDataError("Критерии поиска организации не сформированы")

            return True

        def _search_criteria(self, *props: str) -> dict:
            """Критерии поиска по реквизитам"""
            criteria: dict = {}

            for prop in props:  # : tuple
                if isinstance(prop, int):
                    prop = str(prop)
                else:
                    prop: str = (prop or '').strip()  # обрезаем пробелы

                if not prop:  # пустой реквизит?
                    continue
                elif len(prop) == 15:  # 1: ОГРНИП?
                    return {'OGRNIP': prop}  # WARN единственный реквизит
                elif len(prop) == 13:  # 2.1: ОГРН?
                    criteria['OGRN'] = prop
                elif len(prop) == 9:  # # 2.2: КПП?
                    criteria['KPP'] = prop  # WARN может содержать лат. буквы
                elif len(prop) == 11:  # 3: Номер Записи об Аккредитации
                    return {'NZA': prop}  # WARN единственный реквизит
                elif len(prop) == 10:  # ИНН?
                    self.warning("Для поиска организации"
                        f" не может использоваться ИНН {prop}")
                else:  # неверная длина реквизита!
                    self.warning(f"Значение {prop} реквизита"
                        " организации имеет некорректную длину")

            # if criteria:  # определены критерии поиска?
            # зарегистрированные (имеющие личные кабинет) организации
            # criteria['isRegistered'] = True  # фиксированное True
            return criteria

        def provider_criteria(self, provider_id: ObjectId) -> dict:
            """
            Критерии поиска данных (организации) поставщика информации
            """
            # WARN сопоставленные идентификаторы сохраняется в _prepare
            provider_guid: GUID = \
                self.mapped_guid(GisObjectType.PROVIDER, provider_id)

            provider: dict = self.get_provider_data(provider_id,
                'ogrn', 'kpp',  # inn не используется в запросе ГИС ЖКХ
                'str_name')  # полное наименование организации

            provider_guid.desc = provider['str_name']  # в качестве описания

            ogrn: str = ogrn_or_not(provider.get('ogrn'))  # или пустая строка
            if is_ogrn(ogrn):  # корректный ОГРН?
                provider_guid.unique = ogrn  # сопоставление по ОГРН
            else:  # отсутствует или некорректный ОГРН организации!
                self.failure(provider_guid, "Некорректный ОГРН организации")
                return {}  # WARN возвращаем пустые критерии поиска

            kpp: str = kpp_or_not(provider.get('kpp'))  # или пустая строка
            if kpp:  # обособленное подразделение?
                provider_guid.number = kpp  # ранее хранился ИНН
            else:  # без филиалов?!
                self.warning("Для получения достоверных данных"
                    f" необходим корректный КПП организации с ОГРН {ogrn}")

            return self._search_criteria(ogrn, kpp)

        def providers(self, *provider_id_s: ObjectId):
            """
            Загрузить данные организаций

            :param provider_id_s: при отсутствии загружаются данные:
            1. Обслуживаемых текущей (РЦ) управляющих домами организаций
            2. Выполняющей операцию организации (поставщика информации)
            """
            if provider_id_s:  # определенные организации?
                pass  # используем полученный список идентификаторов
            elif self._house_providers:  # управляемые организациями дома?
                provider_id_s: tuple = (
                    self.agent_id or self.provider_id,  # РЦ
                    *self.provider_houses  # УО
                )
            elif self.provider_id:  # поставщик информации?
                provider_id_s: tuple = (self.provider_id,)
            else:  # организация не определена!
                raise NoDataError("Отсутствуют идентификаторы"
                    " подлежащих загрузке организаций")

            search_criteria: list = []
            for provider_id in provider_id_s:
                provider_criteria: dict = self.provider_criteria(provider_id)
                if not provider_criteria:  # критерии не сформированы?
                    continue  # пропускаем организацию

                criteria_desc: str = ', '.join(f"{name}: {value}"
                    for name, value in provider_criteria.items())
                if provider_criteria in search_criteria:  # идентичные?
                    self.log(warn="Сформированы идентичные критерии"
                        f" поиска {provider_id} по {criteria_desc}")
                else:  # новый критерий поиска организации?
                    search_criteria.append(provider_criteria)
                    self.log(info=f"Сформированы корректные критерии"
                        f" поиска {provider_id} по {criteria_desc}")

            self(SearchCriteria=search_criteria)  # WARN Множественное

        def entity_criteria(self, entity_props: dict) -> list:
            """
            Критерии поиска данных (организации) ЮЛ
            """
            with self.load_context:  # WARN сохраняем только в случае ошибки
                legal_entities: dict = {entity['_id']: entity  # ObjectId: dict
                    for entity in LegalEntity.objects(__raw__={
                        '_id': {'$in': [*entity_props]}  # ~ Tenant.entity
                    }).only('ogrn', 'current_details', 'details').as_pymongo()}

            search_criteria: list = []  # критерии поиска (организаций) ЮЛ

            # WARN сопоставленные идентификаторы сохраняется в _prepare
            for entity_id, entity_guid in self.mapped_guids(
                GisObjectType.LEGAL_ENTITY, *legal_entities  # ~ LegalEntity.id
            ).items():  # идентификаторы ГИС ЖКХ для существующих LegalEntity
                assert isinstance(entity_guid, GUID)

                props: dict = entity_props.get(entity_id)  # из (Legal)Tenant
                legal_entity: dict = legal_entities[entity_id]

                current_details: dict = legal_entity.get('current_details')
                if current_details and current_details.get('current_name'):
                    entity_guid.desc = current_details['current_name']

                ogrn: str = (
                    props.get('ogrn') or legal_entity.get('ogrn') or ''
                ).strip()
                if not ogrn:  # не определен ОГРН юр. лица?
                    self.failure(entity_guid, "Не определен ОГРН юр. лица")
                    continue  # пропускаем юр. лиц без ОГРН
                entity_guid.unique = ogrn  # записываем ОГРН как уникальный

                kpp: str = props.get('kpp')  # обязателен для загрузки филиалов
                entity_guid.number = kpp  # записываем КПП как (обычный) номер

                criteria: dict = self._search_criteria(ogrn, kpp)
                if 'OGRN' not in criteria:  # ОГРН нет в критериях поиска?
                    self.failure(entity_guid, "В критериях поиска"
                        " отсутствует ОГРН (организации) ЮЛ")
                elif criteria in search_criteria:  # существующий критерий?
                    continue  # одна организация может иметь
                else:  # новый критерий поиска организации?
                    search_criteria.append(criteria)
                    self.log(info=f"Сформированы критерии поиска ЮЛ {entity_id}"
                        f" по ОГРН {ogrn} и КПП {kpp or 'ОТСУТСТВУЕТ'}")

            return search_criteria

        def by_guid(self, guid: str):
            """
            Загрузить данные организации с идентификатором ГИС ЖКХ
            """
            self(SearchCriteria=[{'orgPPAGUID': guid}])


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    g = '4fb0487f-c23d-4407-b081-df7692764bd9'  # ПАО Сбербанк
    OrgRegistryCommon.exportOrgRegistry(get_state=True).by_guid(g)
