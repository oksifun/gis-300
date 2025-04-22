from mongoengine import Document
from mongoengine.fields import StringField, BooleanField, DateTimeField, \
    ObjectIdField, UUIDField, ListField, EmbeddedDocumentField

from processing.models.billing.base import \
    BindedModelMixin, ProviderBinds, RelationsProviderBindsProcessingMixin

from processing.references.service_types import SystemServiceTypesTree

from app.gis.models.guid import GisTransportable


MAINTENANCE_ROOT_CODE = 'maintenance'

COMMUNAL_ROOT_CODE = 'communal_services'

ADDITIONAL_EXCEPTIONS = ['administrative']  # ЖУ без предка (не ДУ)


class ServiceType(RelationsProviderBindsProcessingMixin,
                  BindedModelMixin,
                  Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ServiceType'
    }

    code = StringField(verbose_name="Код признака платежа")
    title = StringField(required=True, min_length=1, verbose_name="Заголовок")
    # legacy - Ref('Provider')
    provider = ObjectIdField(
        requred=False,
        verbose_name="Организация-владелец "
                     "(для системных ПП это поле отсутствует)"
    )
    is_system = BooleanField(
        required=True,
        default=False,
        verbose_name="системный, бывший под ЗАО «Отдел»",
    )
    parents = ListField(ObjectIdField())

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    def __str__(self):
        """Строковое представление услуги"""
        return f"{self.code if self.code else self.id}" \
               f" {'-' if self.is_system else '~'} {self.title}"

    def save(self, *args, **kwargs):
        self.is_system = bool(self.code and not self.provider)

        if not self._binds and not self.is_system:
            self._binds = ProviderBinds(pr=self._get_providers_binds())

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):

        from processing.models.billing.tariff_plan import TariffPlan
        tariff_plan = TariffPlan.objects(tariffs__service_type=self.pk,).first()
        if tariff_plan:
            raise PermissionError('Can not remove used services')

        from processing.models.billing.accrual import Accrual
        accrual = Accrual.objects(services__service_type=self.pk).first()
        if accrual:
            raise PermissionError('Can not remove used services')
        return super().delete(*args, **kwargs)

    @property
    def resource(self) -> str or None:
        """Коммунальный ресурс"""
        if self.is_system or self.code:
            system_services: dict = SystemServiceTypesTree[-1]['services']
            service_data: dict = system_services.get(self.code)
            if service_data:
                return service_data.get('resource')

    @property
    def okei_code(self) -> str or None:
        """Код единицы измерения по ОКЕИ"""
        if self.is_system or self.code:
            system_services: dict = SystemServiceTypesTree[-1]['services']
            service_data: dict = system_services.get(self.code)
            if service_data is not None:
                return service_data.get('okei')

    @property
    def measure_unit(self) -> str or None:
        """Единица измерения расхода"""
        if self.okei_code:
            from app.meters.models.choices import \
                METER_MEASUREMENT_UNITS_CHOICES_AS_DICT as MEASURE_UNITS
            return MEASURE_UNITS.get(self.okei_code)

    @property
    def tariff_group(self) -> int:
        """Группа тарифов"""
        if not self.is_system or not self.code or self.is_housing(self.code):
            return 0  # ЖУ
        elif self.is_municipal(self.code):
            return 1  # КУ
        elif self.is_additional(self.code):
            return 2  # ДУ
        else:
            return 0  # ЖУ по умолчанию

    @classmethod
    def is_municipal(cls, service_code: str) -> bool:
        """Коммунальная услуга?"""
        return COMMUNAL_ROOT_CODE in cls.get_parent_codes(service_code)

    @classmethod
    def is_housing(cls, service_code: str) -> bool:
        """Жилищная услуга?"""
        return MAINTENANCE_ROOT_CODE in cls.get_parent_codes(service_code) \
            or service_code in ADDITIONAL_EXCEPTIONS

    @classmethod
    def is_additional(cls, service_code: str) -> bool:
        """Дополнительная услуга?"""
        # WARN у части ДУ нет кода, но у всех нет ни одного предка
        return not cls.get_parent_codes(service_code) \
            and service_code not in ADDITIONAL_EXCEPTIONS

    @classmethod
    def is_heating(cls, service_code: str) -> bool:
        """Отопление?"""
        return service_code == 'heat' or \
            'heat' in cls.get_parent_codes(service_code)

    @classmethod
    def is_waste_water(cls, service_code: str) -> bool:
        """Водоотведение?"""
        return 'waste_water' in cls.get_parent_codes(service_code)

    _cached_service_tree: dict = None

    @classmethod
    def get_services_tree(cls) -> dict:
        """
        Загрузить дерево услуг из БД

        :returns: {'electricity_regular_individual':
            {
                'title': 'Электроэнергия однотар. (индивидуальное потребление)',
                'parent_codes': ['electricity_individual'],
                'resource': 'electricity_regular',
                'calculate_queue': 1,
                'head_codes': [
                    'electricity_day_individual',
                    'electricity_night_individual',
                    'electricity_peak_individual',
                    'electricity_semi_peak_individual'
                ],
                'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
            }
        } ~ мимикрия под содержимое словаря услуг
        """
        NOT_SYSTEM_WITH_CODE = ['fund_repair_public']  # TODO сделать системными

        HEAD_CODES = {
            'waste_water_individual': [
                'hot_water_individual', 'water_individual'
            ],
            'waste_hot_water_individual': ['hot_water_individual'],
            'waste_cold_water_individual': ['water_individual'],
            'waste_cold_water_public': ['water_public'],
            'waste_hot_water_public': ['hot_water_public'],
            'electricity_regular_individual': [
                'electricity_day_individual', 'electricity_night_individual',
                'electricity_peak_individual',
                'electricity_semi_peak_individual'
            ],
        }

        RESOURCE_CODES = {
            'hot_water_individual': 'hot_water',
            'heat_individual': 'heat',
            'water_individual': 'cold_water',
            'gas_individual': 'gas',
            'electricity_regular_individual': 'electricity_regular',
            'electricity_day_individual': 'electricity_day',
            'electricity_night_individual': 'electricity_night',
            'electricity_peak_individual': 'electricity_peak',
            'electricity_semi_peak_individual': 'electricity_semi_peak',
        }

        OKEI_CODES = {  # processing.models.choice.meter.MeterMeasurementUnits
            'heat_individual': 'A056',  # Гигаджоуль (ГДж)
            'heat_public': 'A056',
            'heat_water_remains': 'A056',
            'heat_water_individual': 'A056',
            'heat_water_public': 'A056',
            'heated_water_individual': '113',  # Кубический метр (м3)
            'heated_water_public': '113',
            'waste_water_individual': '113',
            'waste_hot_water_individual': '113',
            'waste_cold_water_individual': '113',
            'waste_water_public': '113',
            'waste_cold_water_public': '113',
            'waste_hot_water_public': '113',
            'water_public': '113',
            'water_for_hot_individual': '113',
            'water_for_hot_public': '113',
            'gas_individual': '113',
            'gas_public': '113',
            'electricity_regular_individual': '245',  # Киловатт-час (кВт)
            'electricity_day_individual': '245',
            'electricity_night_individual': '245',
            'electricity_semi_peak_individual': '245',
            'electricity_regular_public': '245',
            'electricity_day_public': '245',
            'electricity_night_public': '245',
            'electricity_peak_public': '245',
            'electricity_semi_peak_public': '245',
            'tv': '661',  # Канал
            'radio': 'A030',  # Точка присоединения
            'garbage': 'A023',  # Кубический метр на человека
        }

        if cls._cached_service_tree is None:
            services_qs = cls.objects(
                __raw__={
                    'is_system': True,
                },
            ).as_pymongo()
            system_services: dict = {
                service['_id']: service
                for service in services_qs
            }

            cls._cached_service_tree = {service['code']: dict(
                title=service['title'],
                parent_codes=[system_services[parent_id]['code']  # ДОЛЖЕН быть!
                    for parent_id in service['parents']],
                head_codes=HEAD_CODES.get(service['code'], []),  # или []
                resource=RESOURCE_CODES.get(service['code']),  # или None
                # TODO calculate_queue?
                okei=OKEI_CODES.get(service['code'], '642'),  # или Ед.
            ) for service in system_services.values() if service.get('code')}

        return cls._cached_service_tree

    @classmethod
    def get_parent_codes(cls, service_type_code: str) -> set:
        """
        Коды всех предков услуги (исключая саму услугу)

        Порядок наследования НЕ соблюдается!
        """
        MULTI_PARENT_SERVICES = {
            # первый предок приведет к главной услуге, второй к hot_water
            'water_for_hot_public':
                ('water_supply', 'hot_water_public_carrier'),
            'water_for_hot_individual':
                ('water_supply', 'hot_water_individual_carrier'),
            'heated_water_public':
                ('heating_water_public', 'hot_water_public_carrier'),
            'heated_water_individual':
                ('heating_water_individual', 'hot_water_individual_carrier'),
            'heating_water_public':
                ('heat_water', 'hot_water_public'),
            'heating_water_individual':
                ('heat_water', 'hot_water_individual'),
        }  # все услуги с двумя предками

        parent_codes = set()
        service_type_tree = cls.get_services_tree()  # дерево услуг с кодами

        while service_type_code:  # получен код услуги?
            if service_type_code in MULTI_PARENT_SERVICES:  # более 1 предка?
                service_type_code, hot_water_code = \
                    MULTI_PARENT_SERVICES[service_type_code]
                # главная услуга второго предка - это всегда "Горячая вода"
                parent_codes.add(hot_water_code)  # код 2 предка
                parent_codes.update(
                    cls.get_parent_codes(hot_water_code)  # рекурсия
                )  # предки 2-го предка
            else:  # единственный предок!
                tree_service_type = service_type_tree.get(service_type_code)
                assert tree_service_type, f"Услуги «{service_type_code}»" \
                    " нет в дереве услуг (SystemServiceTypesTree)"  # Validation

                tree_parent_codes = tree_service_type['parent_codes']
                service_type_code = tree_parent_codes[0] \
                    if tree_parent_codes else None  # код первого предка

            if service_type_code:  # получен код предка?
                parent_codes.add(service_type_code)

        return parent_codes

    @classmethod
    def get_provider_tree(cls, provider_id,
                          system_types=None, provider_types=None):
        """
        УСТАРЕЛ. Пользоваться get_provider_services_tree
        Получает услуги, сгруппированные по системным кодам, в виде словаря.
        Можно передать список системных услуг и услуг провайдера, чтобы не
        делать запрос в базу.
        """
        s_types = {
            s.code: s.id
            for s in (
                system_types
                or cls.objects.filter(is_system=True).only('code')
            )
        }
        p_types = (
                provider_types
                or cls.objects.filter(provider=provider_id).only('parents')
        )

        def get_p_children(p_type_id):
            children = []
            for p_p_type in p_types:
                if p_p_type.parents and p_type_id in p_p_type.parents:
                    children.append(p_p_type.id)
                    children.extend(get_p_children(p_p_type.id))
            return children

        for p_type in p_types:
            p_type.children = get_p_children(p_type.id)
        s_types_tree = SystemServiceTypesTree[0]['services']

        def get_children(main_code):
            children = []
            for s_code, s_data in s_types_tree.items():
                if (
                        s_data.get('parent_codes')
                        and main_code in s_data['parent_codes']
                ):
                    children.append(s_types[s_code])
                    children.extend(get_children(s_code))
            return children

        result = {}
        for code, data in s_types_tree.items():
            result[code] = [s_types[code]]
            result[code].extend(get_children(code))
            for p_type in p_types:
                if p_type.parents and set(p_type.parents) & set(result[code]):
                    result[code].append(p_type.id)
                    result[code].extend(p_type.children)
        return result

    @classmethod
    def update_by_system_params(cls, service_types, date_on=None):
        """
        Апдейтит переданный список видов платежей - добавляет им свойства
        системных видов платежей
        Работает только со словарями
        """
        from copy import deepcopy
        from datetime import datetime

        # найдём дерево услуг по дате
        system_types = deepcopy(
            [
                t for t in SystemServiceTypesTree
                if t['date_from'] <= (date_on or datetime.now())
            ][-1]['services']
        )
        # получим _id системных видов платежей
        s_types = list(
            cls.objects(
                __raw__={
                    'is_system': True,
                    'code': {'$in': list(system_types.keys())},
                },
            ).only(
                'id',
                'code',
            ).as_pymongo(),
        )
        system_ids = {s_t['code']: s_t['_id'] for s_t in s_types}
        system_codes = {s_t['_id']: s_t['code'] for s_t in s_types}
        # подсунем ИДшники в словарь системных видов платежей
        for code, system_type in system_types.items():
            system_type['_id'] = system_ids.get(code)
            system_type['code'] = code
            system_type['parents'] = []
            if system_type['parent_codes']:
                for parent_code in system_type['parent_codes']:
                    system_type['parents'].append(system_ids.get(parent_code))
            system_type['head'] = []
            if system_type.get('head_codes'):
                for head_code in system_type['head_codes']:
                    system_type['head'].append(system_ids.get(head_code))
        # смержим переданный список с системными видами платежей
        loaded_codes = [s_t['code'] for s_t in service_types if s_t.get('code')]
        ix = 0
        while ix < len(service_types):
            service_type = service_types[ix]
            if (
                    service_type.get('code')
                    and service_type['code'] in system_types
            ):
                service_type = system_types[service_type['code']]
                service_types[ix] = service_type
            else:
                service_type['parent_codes'] = []
                for parent in service_type.get('parents', []):
                    service_type['parent_codes'].append(
                        system_codes.get(parent))
            for parent in service_type['parent_codes']:
                if parent not in loaded_codes and parent in system_types:
                    service_types.append(system_types[parent])
                    loaded_codes.append(parent)
            if service_type.get('head'):
                for head in service_type['head_codes']:
                    if head not in loaded_codes:
                        service_types.append(system_types[head])
                        loaded_codes.append(head)
            ix += 1

    @classmethod
    def get_service_children(cls, service_as_dict, source_services):
        """
        Принимает вид платежа в виде словаря, а также список, где искать,
        и отдаёт список его потомков в виде словарей
        """
        result = []
        for service in source_services:
            if service_as_dict['_id'] in service['parents']:
                result.append(service)
                children = cls.get_service_children(service, source_services)
                result.extend(children)
        return result

    @classmethod
    def get_service_children_ids(cls, service_as_dict, source_services):
        result = cls.get_service_children(service_as_dict, source_services)
        return [r['_id'] for r in result]

    @classmethod
    def get_services_of_provider(cls, provider, system_included: bool = False):
        """
        Запросить список услуг организации

        У 20 базовых услуг поля provider - нет, у системных услуг = null

        У 5 системных услуг (is_system=True) нет кода (code=null):
            Охранные услуги, Обслуживание диспетчерских сигналов, Слив стояка,
            утилизация твёрд. быт. отходов, уст.общедом.пр.учета
        """
        if not system_included:  # без системных (общих) услуг?
            query: dict = {'provider': provider}
        else:  # включая системные услуги!
            query: dict = {
                '$or': [
                    {'provider': provider},
                    {
                        '$and': [
                            {'is_system': True},
                            {'code': {'$ne': None}},
                        ]
                    },
                ],
            }
        # сначала системные (provider = null)
        return cls.objects(__raw__=query).order_by('-provider', 'title')


class ServiceTypeGisName(Document, GisTransportable):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ServiceTypeGisName',
    }

    provider = ObjectIdField(required=True, verbose_name="Ид. организации")

    created = DateTimeField(required=True, verbose_name="Создано")
    closed = DateTimeField(default=None, verbose_name="Отменено")

    status = StringField(choices=('changed', 'recovered', 'deleted'))

    gis_title = StringField(required=True, verbose_name="Наименование элемента")
    okei_code = StringField(verbose_name="Код единицы измерения объема услуги")

    reference_name = StringField(
        required=True, verbose_name="Наименование справочника (шаблонное)")
    reference_number = StringField(
        required=True, verbose_name="Реестровый номер справочника")
    position_number = StringField(
        required=True, verbose_name="Позиция (код) элемента в справочнике")

    guid = UUIDField(verbose_name="Идентификатор ГИС ЖКХ элемента справочника")

    def __str__(self):
        """Строковое представление элемента справочника ГИС ЖКХ"""
        return self.gis_title

    def __repr__(self):
        """Расширенное строковое представление элемента справочника ГИС ЖКХ"""
        code_and_title = f"{self.reference_number}.{self.position_number}" \
            f" - {self.gis_title}"

        return f"{code_and_title} ~ {self.guid}" if self.guid \
            else code_and_title

    @property
    def name(self) -> str:
        """Наименование элемента справочника (nsiRef)"""
        return self.gis_title

    @property
    def correct_title(self) -> str:
        """
        Стандартизированное (ГИС ЖКХ) наименование услуги
        """
        municipal_service_names = {
            'heat_individual': 'Отопление',
            'heat_public': 'Отопление',  # заводят вместо heat_individual
            'hot_water_individual': 'Горячее водоснабжение',
            'heated_water_individual': 'Горячее водоснабжение',  # TODO аналог?
            'water_individual': 'Холодное водоснабжение',
            'waste_cold_water_individual': 'Водоотведение',
            'electricity_regular_individual': 'Электроснабжение',  # однотариф.
            'gas_individual': 'Газоснабжение',
        }  # стандартный набор коммунальных услуг ГИС ЖКХ
        multi_service_names = {
            'water_for_hot_individual': 'Холодная вода для ГВС',
            'water_for_hot_public': 'Холодная вода для ГВС на ОДН',
            'heating_water_individual': 'Тепловая энергия для ГВС'
        }  # TODO составные комм. услуги - добавляются отдельно!
        day_night_service_names = {
            'electricity_day_individual': 'Электроэнергия (день)',
            'electricity_night_individual': 'Электроэнергия (ночь)',
            'electricity_day_public': 'Электроэнергия на ОДН (день)',
            'electricity_night_public': 'Электроэнергия на ОДН (ночь)',
        }  # услуги с разделением на дневной/ночной тариф
        common_service_names = {  # МОП - места общего пользования
            **municipal_service_names,
            **day_night_service_names,
            # НЕ системные (без кода):  # '055' ~ м2, '113' ~ м3
            # Автостоянка  # 'A031' ~ машиноместо
            # Видеонаблюдение  # '081' ~ м2 общ. пл.
            # Добровольное страхование  # '383' ~ руб.
            # Запирающее устройство (ЗУ)  # '796' ~ шт.
            # Интернет  # 'A030' ~ точка (присоединения)
            # Оплата охранных услуг,  # '081'
            # Оплата услуг консьержа (сторожа или вахтера),  # '081'
            'tv': 'Антенна (кабельное телевидение)',  # 'A030'
            'radio': 'Услуга связи проводного радиовещания (радиоточка)',
            # 'garbage': 'Вывоз мусора',  # 'A023' ~ м3/чел.  # TODO ком. с 2022
            # 'administrative': 'Административно-хозяйственные расходы',  # АХР
        }  # { code: gis_title }

        return common_service_names.get(self.code,
            self.name.replace(' (индивидуальное потребление)', '')
                .replace('(общедомовые нужды)', 'на ОДН'))

    @property
    def reg_num(self) -> int:
        """Реестровый номер справочника (nsiRef)"""
        return int(self.reference_number)

    @property
    def code(self) -> str:
        """Код элемента справочника (nsiRef)"""
        return self.position_number

    @property
    def unit(self) -> str:
        """Код ОКЕИ или название единицы измерения (nsiRef)"""
        return self.okei_code

    @property
    def as_req(self) -> dict or None:
        """Представление ГИС ЖКХ ссылки на элемент справочника услуг"""
        return {
            'GUID': str(self.guid), 'Code': self.code,  # обязательные элементы
            'Name': self.name  # необязательное наименование элемента
        } if self.guid and self.code else None  # только с ид. ГИС ЖКХ и кодом

    @classmethod
    def service_nsi(cls) -> list:
        """
        Строковые номера частных справочников услуг
        """
        from app.gis.utils.nsi import SERVICE_NSI
        return [str(num) for num in SERVICE_NSI]

    @classmethod
    def ref_codes_of(cls, provider_id) -> dict:
        """
        Номера справочников с кодами элементов ГИС ЖКХ провайдера
        """
        titled_refs: dict = {}

        for nsi in cls.objects(__raw__={
            'provider': provider_id, 'closed': None,  # только актуальные
            'reference_number': {'$in': [
                # WARN кроме элементов справочника №2 ~ "КР на ОДН"
                *cls.service_nsi(),  # (частные) справочники услуг
                '50'  # (общий) справочник жилищных услуг
            ]},
        }).as_pymongo().order_by('reference_number'):
            title: str = nsi['gis_title']

            ref: tuple = (int(nsi['reference_number']), nsi['position_number'])
            dup: tuple = titled_refs.get(nsi['gis_title'])
            assert not dup, f"Наименование «{title}» имеют элементы" \
                f" {ref[0]}.{ref[1]} и {dup[0]}.{dup[1]} справочников" \
                f" провайдера {provider_id}"

            titled_refs[title] = ref

        return titled_refs  # { 'title': (RegistryNumber, 'ElementCode') }

    @classmethod
    def _references(cls, provider_id) -> list:
        """
        Номера и наименования имеющихся справочников услуг организации
        """
        aggregation_pipeline: list = [
            {'$match': {
                'provider': provider_id, 'closed': None,
                'reference_number': {'$in': cls.service_nsi()}
            }},
            {'$group': {
                '_id': "$reference_number",
                'reference_name': {'$first': '$reference_name'}
            }},
            {'$project': {
                'reference_number': '$_id',
                'reference_name': 1,
                '_id': 0,
            }}
        ]
        return list(cls.objects.aggregate(*aggregation_pipeline))

    @classmethod
    def references(cls, provider_id) -> dict:
        """
        Имеющиеся частные справочники услуг организации
        """
        return {int(nsi['reference_number']): nsi['reference_name']
            for nsi in cls.objects(__raw__={
                'provider': provider_id, 'closed': None,
                'reference_number': {'$in': cls.service_nsi()}
            }).as_pymongo()}  # ReferenceNumber: 'ReferenceName'

    def __remove_duplicates(self):
        """
        ВНИМАНИЕ! Элементы без кода ОКЕИ используются при выгрузке шаблонами
        """
        return ServiceTypeGisName.objects(__raw__={
            '_id': {'$ne': self.id},  # КРОМЕ себя!
            'provider': self.provider, 'gis_title': self.gis_title,
            'okei_code': {'$in': [self.okei_code, None]}  # тот же или без
        }).delete()

    def _remap_service_binds(self, old_title: str):

        return ServiceTypeGisBind.objects(
            provider=self.provider, gis_title=old_title
        ).update(gis_title=self.gis_title)

    def _update_service_binds(self):

        return ServiceTypeGisBind.objects(
            provider=self.provider, gis_title=self.gis_title
        ).update(closed=self.closed)

    def clean(self):

        if not self.guid:  # элемент справочника без ид. ГИС ЖКХ?
            if self.name != self.correct_title:  # некорректное наименование?
                self.gis_title = self.correct_title  # переименовываем элемент!

        if not self.id:  # новая запись?
            return  # нечего сверять!

        # 'field_name' in self._changed_fields
        old: dict = ServiceTypeGisName.objects(__raw__={
            '_id': self.id
        }).as_pymongo().only('gis_title', 'closed').first()  # прежняя запись

        if not old:  # прежняя запись не найдена?
            return  # не с чем сверять!

        if old['gis_title'] != self.gis_title:  # изменилось название?
            self._remap_service_binds(old['gis_title'])

        if old.get('closed') != self.closed:  # изменился статус?
            self._update_service_binds()


class ServiceTypeGisBind(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ServiceTypeGisBind',
        'indexes': ['provider'],
    }

    provider = ObjectIdField(required=True, verbose_name='Организация')
    created = DateTimeField(required=True, verbose_name='Создано')
    closed = DateTimeField(default=None, verbose_name='Отменено')
    service_type = ObjectIdField(verbose_name='ИД услуги')
    service_code = StringField(verbose_name='Код услуги')
    gis_title = StringField(required=True, verbose_name='Наименование в ГИС')

    @classmethod
    def mappings_of(cls, provider_id) -> dict:
        """
        Получить сопоставления услуг определенного провайдера

        :returns: 'title': (ServiceTypeId, 'code'),...
        """
        service_mappings: dict = {}

        for bind in cls.objects(__raw__={
            'provider': provider_id, 'closed': None,
        }).only(
            'gis_title', 'service_type', 'service_code'
        ).as_pymongo():  # все сопоставленные услуги
            title = bind['gis_title']  # есть всегда
            service_id = bind.get('service_type')  # : ObjectId
            assert service_id, \
                f"В сопоставлении «{title}» не указан идентификатор услуги"

            service_code: str = bind.get('service_code')  # может отсутствовать!
            if not service_code:  # код услуги отсутствует?
                service_type: dict = ServiceType.objects(
                    id=service_id
                ).only('code').as_pymongo().first()
                if not service_type:  # не найдена сопоставленная услуга?
                    cls.objects(id=bind['_id']).delete()  # WARN удаляем запись
                    continue  # сопоставление удалено

                service_code = service_type.get('code')  # может отсутствовать
                # cls.objects(provider=provider_id, service_type=service_id) \
                #     .update_one(service_code=service_code)  # TODO исправляем?

            service_mappings.setdefault(title, set()).add(  # уникальные
                (service_id, service_code)  # : tuple
            )  # добавляем кортеж в набор

        return service_mappings
