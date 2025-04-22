from uuid import UUID
from bson import ObjectId

from mongoengine import Document, QuerySet, \
    ObjectIdField, UUIDField, IntField, StringField, BooleanField

from processing.models.billing.service_type import ServiceTypeGisName

from app.gis.utils.common import sb, as_guid
from app.gis.utils.nsi import NSI_GROUP, NSIRAO_GROUP, PRIVATE_GROUP, \
    get_list_group


PRIVATE_SERVICES: dict = {
    1: 'Вид дополнительной услуги',
    51: 'Коммунальные услуги',  # частные случаи "Вида КУ" (НСИ 3)
    337: 'Вид потребляемого при СОИ коммунального ресурса'
         ' (главный коммунальный ресурс)'  # частные случаи НСИ 2?
}


class nsiRef(Document):
    """Ссылка на элемент справочника"""

    meta = {
        'db_alias': 'legacy-db',
        'collection': 'NSI',
        'indexes': [  # 'guid' - primary_key
            'reg_num', 'provider_id',
            {
                'fields': ['reg_num', 'code', 'okei', 'provider_id'],
                # TODO или reg_num_1_code_1_provider_id_1?
                'unique': True
            }
        ], 'index_background': True, 'auto_create_index': False,
    }

    guid = UUIDField(primary_key=True,
        verbose_name="Идентификатор ГИС ЖКХ элемента")

    reg_num = IntField(required=True, verbose_name="Реестровый № справочника")
    code = StringField(required=True, verbose_name="Уникальный код элемента")

    name = StringField(default=None, max_length=1200,
        verbose_name="Название (значение) элемента")

    okei = StringField(verbose_name="Код единицы измерения объема услуги")

    # только для частных справочников поставщиков информации
    provider_id = ObjectIdField(verbose_name="Идентификатор организации")

    is_sit = BooleanField(verbose_name="Данные тестового сервера?")

    _cached_common: dict = {}  # кэшированные элементы общих справочников

    def __hash__(self):
        return hash(self.guid)

    def __eq__(self, other):
        return self.guid == other.guid

    def __ne__(self, other):
        return not(self == other)  # ВАЖНО!

    def __str__(self):
        """Название и/или код элемента справочника"""
        return f"{self.code}-{self.name}" if self.name else self.code

    def __repr__(self):
        """Описание элемента справочника"""
        return f"{self.reg_num}.{self.code}: {self.name}" \
            f" ~ {self.guid or 'БЕЗ идентификатора'}"

    @property
    def group(self) -> str:
        """Группа справочника"""
        return get_list_group(self.reg_num)

    @property
    def as_req(self) -> dict:
        """Ссылка на НСИ"""
        return {'GUID': str(self.guid), 'Code': self.code, 'Name': self.name}

    @property
    def number(self) -> str:
        """Номер (регистрационный с кодом) элемента справочника"""
        return f"{self.reg_num}.{self.code}"  # 1.3

    @classmethod
    def by_code(cls, registry_number: int, code: str or int,
            provider_id: ObjectId = None):
        """
        Найти ссылку на элемент справочника (организации) по коду
        """
        if not code:  # nsiRef(Any, 0/None) = None
            return None

        query = dict(reg_num=registry_number, code=str(code))
        if provider_id:
            query['provider_id'] = provider_id

        nsi_ref: nsiRef = cls.objects(**query).first()  # или None
        return nsi_ref

    @classmethod
    def store(cls, element_guid: str, registry_number: int, element_code: str,
            element_name: str = None, provider_id=None) -> 'nsiRef' or None:
        """
        Создать (или обновить) ссылку на справочник
        """
        if not isinstance(element_guid, UUID):
            element_guid = as_guid(element_guid)
        assert isinstance(element_guid, UUID), \
            "Некорректный идентификатор элемента справочника"

        nsi_ref: nsiRef or None = cls.objects(guid=element_guid).first()  # PK

        if not nsi_ref:  # ссылка не найдена по идентификатору ГИС ЖКХ?
            nsi_ref = cls.by_code(registry_number, element_code,
                provider_id)  # по рег. номеру справочника и коду элемента

        # идентификатор элемента справочника отличается на ППАК и СИТ
        if nsi_ref and nsi_ref.guid != element_guid:
            nsi_ref.delete()  # WARN изменить ключ нельзя ~ создается новая
            nsi_ref = None  # далее создается новая ссылка

        if not nsi_ref:  # ссылка не найдена по коду или удалена?
            nsi_ref = cls(guid=element_guid, provider_id=provider_id,
                reg_num=registry_number, code=element_code)  # TODO okei

        nsi_ref.name = element_name  # WARN название может быть изменено в ЛК
        nsi_ref.save()  # сохраняем ссылку на справочник

        return nsi_ref  # : nsiRef

    @classmethod
    def remove(cls, element_guid) -> None:
        """
        Удалить ссылку на справочник
        """
        cls.objects(guid=element_guid).delete()  # атомарная операция

    @classmethod
    def elements(cls, registry_number: int) -> list:
        """
        Ссылки на все элементы указанного справочника
        """
        return cls.objects(__raw__={
            'reg_num': registry_number
        }).as_pymongo()

    @classmethod
    def codes(cls, registry_number: int) -> list:
        """
        Коды всех элементов указанного справочника
        """
        return [elem['code'] for elem in cls.elements(registry_number)]

    @classmethod
    def verbose(cls, registry_number: int, with_guid=False) -> str:

        nsi_item_name: str = NSI_GROUP.get(registry_number,
            NSIRAO_GROUP.get(registry_number,
                PRIVATE_GROUP.get(registry_number, None)))  # название спр.

        nsi_elements = '; '.join(f"{element['code']}-{element['name']}"
            + (f" ({element['_id']})" if with_guid else '')
                for element in cls.elements(registry_number))

        return f"{nsi_item_name}: {nsi_elements}"

    @classmethod
    def common_services(cls, *reg_num_s: int) -> QuerySet:
        """
        Элементы общих справочников услуг

        3 - Коммунальные услуги (2 - Коммунальные ресурсы)
        50 - Жилищные услуги
        """
        if not reg_num_s:  # номера не определены?
            reg_num_s = (3, 50)  # справочники услуг

        return cls.objects(__raw__={'reg_num': {'$in': reg_num_s}})

    @classmethod
    def provider_services(cls, provider_id: ObjectId, *reg_num_s: int,
            only_actual: bool = True) -> QuerySet:
        """
        Элементы частных справочников поставщика информации

        1 - Дополнительные услуги, 51 - Коммунальные услуги
        337 - Вид коммунального ресурса (потребление при СОИ) (гл. комм. ресурс)
        """
        reference_numbers: list = [str(reg_num)  # WARN сохранены в виде строк
            for reg_num in (reg_num_s or PRIVATE_SERVICES)
                if reg_num in PRIVATE_SERVICES]

        query = {'provider': provider_id,  # Accrual.owner, НЕ doc.provider
            'reference_number': {'$in': reference_numbers}}

        if only_actual:   # только актуальные элементы?
            query['closed'] = None  # также выбираются записи БЕЗ поля closed

        return ServiceTypeGisName.objects(__raw__=query).order_by(
            'reference_number'  # position_number сортирует как строки
        )  # не as_pymongo

    @classmethod
    def common(cls, registry_number: int, code: int or str) -> dict:
        """
        Получить ссылку на элемент общесистемного справочника

        :param registry_number: регистрационный номер справочника
        :param code: код элемента справочника : строка или число
        """
        item_number: str = f"{registry_number}.{code}"

        if item_number not in cls._cached_common:
            nsi_ref = cls.by_code(registry_number, code)
            assert nsi_ref, "Общесистемный справочник" \
                f" №{registry_number} не загружен из ГИС ЖКХ" \
                f" или элемент {sb(code)} не найден"

            cls._cached_common[item_number] = nsi_ref.as_req

        return cls._cached_common[item_number]

    @classmethod
    def private(cls, registry_number, code, provider_id) -> dict or None:
        """
        Получить ссылку на элемент частного справочника услуг

        :param registry_number: регистрационный номер справочника
        :param code: код элемента справочника : ожидается строка или число
        :param provider_id: идентификатор организации, владеющей справочником
        """
        gis_ref: ServiceTypeGisName = ServiceTypeGisName.objects(
            provider=provider_id,
            reference_number=str(registry_number),
            position_number=str(code),
            closed=None,
        ).order_by('-created').first() if code else None  # код 0 не встречается

        return gis_ref.as_req if gis_ref else None
