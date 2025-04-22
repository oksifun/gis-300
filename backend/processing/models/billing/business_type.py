from typing import Optional

from bson import ObjectId
from mongoengine import Document, StringField

from app.permissions.mixins import PermissionsMixin
from app.permissions.core.tools import PermissionEnum


class BusinessType(Document, PermissionsMixin):
    """
    Аварийное обслуживание ~ aob
    Водоотведение и канализирование ~ vik
    Вывоз мусора ~ vmr
    Государственные и муниципальные органы ~ gov
    Демо-доступ ~ demo
    Застройщик ~ dev
    Кабельное телевидение ~ ctv
    Капитальный ремонт ~ cpr
    Контроль доступа ~ kod
    Кредитные организации ~ bnk
    Обслуживание АППЗ ~ oap
    Обслуживание ПЗУ ~ pzu
    Обслуживание видеонаблюдения ~ ovi
    Обслуживание приборов учета ~ opu
    Плательщик ~ plt
    Поставка ХВС ~ hvs
    Поставка бытового газа ~ pbg
    Поставка нескольких коммунальных ресурсов ~ cre
    Поставка тепловой энергии и ГВС ~ gvs
    Поставка электроэнергии ~ pel
    Продажа услуг и работ ЖКХ ~ sales
    Расчетно-кассовый центр ~ cс (ВТОРАЯ БУКВА - РУССКАЯ)
    Сигналы лифтов/сигнализации ~ sig
    Управление домами ~ udo
    Управление инфраструктурой (ЗАО "Отдел") ~ otd
    Управление муниципальным имуществом ~ umi
    Услуги аварийно-диспетчерской службы ~ ads
    Услуги охраны ~ uoh
    Эксплуатация домов ~ edo
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'BusinessType'
    }
    slug = StringField()
    title = StringField(required=True)

    NA = 'na'  # неизвестный вид деятельности
    OTD = 'otd'  # Управление инфраструктурой (ЗАО "Отдел")

    CC =  'cс'   # Расчетный центр  # WARN вторая буква кода - КИРИЛИЦА
    UDO = 'udo'  # Управление домами
    EDO = 'edo'  # Эксплуатация домов
    CPR = 'cpr'  # Капитальный ремонт
    VMR = 'vmr'  # Вывоз мусора
    CRE = 'cre'  # Поставка (нескольких) коммунальных ресурсов
    HVS = 'hvs'  # Поставка ХВС
    GVS = 'gvs'  # Поставка тепловой энергии и ГВС
    PEL = 'pel'  # Поставка электроэнергии
    PBG = 'pbg'  # Поставка бытового газа
    GOV = 'gov'  # Государственные и муниципальные органы
    UMI = 'umi'  # Управление муниципальным имуществом
    BNK = 'bnk'  # Кредитные организации
    PLT = 'plt'  # Плательщик
    SAL = 'sales'  # Продажа услуг и работ ЖКХ

    SUPPLIER: tuple = (CRE, HVS, GVS, PEL, PBG)  # РСО

    __cache__: dict = {}

    @property
    def parent_permissions(self):
        """Возвращает все возможные права."""
        from processing.models.permissions import ClientTab
        tabs = ClientTab.objects(is_active=True).only('slug')
        return {tab.slug: PermissionEnum.max() for tab in tabs}

    @classmethod
    def registry(cls, by_id: bool = False) -> dict:
        """Перечень видов деятельности"""
        types: list = cls.objects.as_pymongo().only('slug').all()

        if by_id:
            return {_type['_id']: _type['slug'] for _type in types}
        else:
            return {_type['slug']: _type['_id'] for _type in types}

    @classmethod
    def get_id(cls, slug: str) -> Optional[ObjectId]:
        """Идентификатор вида деятельности"""
        if slug == cls.NA:
            return None

        if slug not in cls.__cache__:
            cls.__cache__[slug] = cls.objects(slug=slug).scalar('id').first()

        return cls.__cache__[slug]

    @classmethod
    def get_id_s(cls, *slug_s: str) -> dict:
        """Загрузить идентификаторы видов деятельности"""
        queryset = cls.objects(slug__in=slug_s) if slug_s else cls.objects.all()

        return {_type['slug']: _type['_id']
            for _type in queryset.only('slug').as_pymongo()}

    @classmethod
    def get_ref_s(cls, *slug_s: str) -> list:
        """Загрузить виды деятельности"""
        return [_type for _type in cls.objects(slug__in=slug_s)
            if isinstance(_type, BusinessType)]

    @classmethod
    def udo_id(cls) -> ObjectId:
        """Управление домами (УК, ТСЖ, ТСН, ЖСК)"""
        return cls.get_id(cls.UDO)

    @classmethod
    def edo_id(cls) -> ObjectId:
        """Эксплуатация домов"""
        return cls.get_id(cls.EDO)

    @classmethod
    def cpr_id(cls) -> ObjectId:
        """Капитальный ремонт"""
        return cls.get_id(cls.CPR)

    @classmethod
    def cc_id(cls) -> ObjectId:
        """Расчетный (кассовый) центр"""
        return cls.get_id(cls.CC)

    @staticmethod
    def get_legal_form_slugs(*provider_id_s: ObjectId):
        """
        Получить формы организаций со всеми видами деятельности провайдеров
        """
        business_slugs: dict = {_type['_id']: _type['slug'] for _type in
        BusinessType.objects.only('slug').as_pymongo()}

        form_types: dict = {}

        query: dict = {
            'legal_form': {'$ne': None},
            'business_types.0': {'$exists': True},
        }
        if provider_id_s:
            query['_id'] = {'$in': provider_id_s}

        from processing.models.billing.provider.main import Provider
        for provider in Provider.objects(__raw__=query).only(
            'business_types', 'legal_form'
        ).as_pymongo():
            prov_types: set = {business_slugs.get(_id)
                for _id in provider['business_types']}
            form_types.setdefault(
                provider['legal_form'],
                set()
            ).update(prov_types)

        return form_types
