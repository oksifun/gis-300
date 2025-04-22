from bson import ObjectId

from processing.models.billing.business_type import BusinessType
from processing.models.billing.provider.main import Provider

from processing.models.choices import GisDaySelection

from app.house.models.house import House, HouseEmbededServiceBind
from app.area.models.area import Area

from app.gis.utils.common import is_between, get_time, last_month_day


def get_provider_house_ids(*house_id_s: ObjectId) -> dict:
    """
    Имеющие отношение к домам и выгружаемые в ГИС ЖКХ организации
    """
    assert house_id_s, "Для поиска организаций требуется перечень домов"
    provider_house_ids: dict = {}

    gis_online_providers: list = \
        Provider.objects(gis_online_changes=True).distinct('id')

    for house in House.objects(__raw__={
        '_id': {'$in': house_id_s}, 'is_deleted': {'$ne': True},
    }).only('service_binds').exclude('service_binds.sectors'):
        assert isinstance(house, House)
        for bind in house.service_binds or []:
            assert isinstance(bind, HouseEmbededServiceBind)  # WARN is_actual
            if bind.provider not in gis_online_providers:
                continue  # только с подключенным онлайн-обменом
            if not bind.is_active or not bind.is_actual() or \
                    bind.business_type != BusinessType.udo_id():
                continue
            provider_houses: list = \
                provider_house_ids.setdefault(bind.provider, [])
            provider_houses.append(house.id)  # не повторяются

    return provider_house_ids  # ProviderId: [ HouseId,... ]


def get_provider_metering_house_ids(*provider_s: ObjectId,
        at_end_day: bool = False, is_collective: bool = False) -> dict:
    """
    Имеющие подлежащие выгрузке показания дома организаций

    :param at_end_day: True - в день окончания, False - начала приема показаний
    :param is_collective: разрешена выгрузка показаний ОДПУ?
    """
    today: int = get_time().day  # номер сегодняшнего дня

    days: list = [
        today,  # сегодняшний день месяца
        GisDaySelection.NEXT_MONTH + today,  # следующего месяца
    ]
    if today == last_month_day():
        days.append(GisDaySelection.DAY_LAST)  # последний день месяца
        days.append(GisDaySelection.NEXT_LAST)  # следующего месяца

    if not provider_s:  # находим выгружающие изменения в ГИС ЖКХ организации
        provider_s = Provider.objects(gis_online_changes=True).distinct('id')

    provider_house_ids: dict = {}  # ProviderId: [ HouseId,... ]

    for house in House.objects(__raw__={
        'service_binds.provider': {'$in': provider_s},  # индекс
        'gis_metering' + ('_end' if at_end_day else '_start'): {'$in': days},
        'is_deleted': {'$ne': True},
    }).only(
        'service_binds', 'gis_collective'
    ).exclude('service_binds.sectors'):
        assert isinstance(house, House)
        for bind in house.service_binds or []:
            assert isinstance(bind, HouseEmbededServiceBind)  # WARN is_actual
            if is_collective and not house.gis_collective:
                continue  # только выгружающие показания ОДПУ
            elif bind.provider not in provider_s:
                continue  # только выгружающие изменения
            elif not bind.is_active or not bind.is_actual() or \
                    bind.business_type != BusinessType.udo_id():
                continue
            provider_house_ids.setdefault(bind.provider, []).append(house.id)

    return provider_house_ids


def get_binded_houses(provider_id: ObjectId, by_fias: bool = False) -> dict:
    """
    Данные связанных (управляемых) домов организации

    :returns: { HouseId или 'FIAS': House }
    """
    # WARN у новых домов нет идентификатора ФИАС, только (временный) ГИС ЖКХ
    return {house.get('gis_fias') or house.get('fias_house_guid')
        if by_fias else house['_id']: house  # по идентификатору дома или ФИАС
    for house in House.objects(__raw__={
        'service_binds.provider': provider_id, 'is_deleted': {'$ne': True},
    }).as_pymongo() if any(
        bind['provider'] == provider_id  # данной организации?
        and bind['is_active']  # активная привязка дома?
        and is_between(  # действующая в данный момент?
            # WARN дата начала и дата конца могут отсутствовать
            earlie=bind.get('date_start'), later=bind.get('date_end')
        ) for bind in house.get('service_binds') or []
    )}


def get_areas_of(house_id: ObjectId) -> list:
    """Идентификаторы актуальных помещений дома"""
    return Area.objects(__raw__={
        'house._id': house_id,  # индекс
        'is_deleted': {'$ne': True},
    }).distinct('id')


def get_housed_areas(area_ids: list) -> dict:
    """Распределенные по домам идентификаторы помещений"""
    areas = Area.objects(id__in=area_ids).only('house').as_pymongo()

    grouped_ids: dict = {}  # помещения в домах

    for area in areas:  # распределяем помещения по домам
        assert isinstance(area, dict)
        grouped_ids.setdefault(area['house']['_id'], []).append(area['_id'])

    return grouped_ids


def get_fixed_number(number: str) -> str:
    """Замена 10Н на 10-Н в соответствии с Росреестром"""
    REPLACEABLE = 'Н'  # заменяемые буквы номеров помещений оной строкой

    from re import sub
    return sub(r"(\d+?)-?([" + REPLACEABLE + "])", r'\1-\2', number.strip())


def remove_hyphens(number: str) -> str:
    """Удаление дефисов из строки number"""
    from re import sub
    return sub(r"-", "", number.strip())


def add_hyphen_before_last_N(number: str) -> str:
    """Добавляет дефис перед последней буквой 'Н' в номере"""
    from re import sub
    # Заменяем последнее вхождение 'Н' на '-Н'
    return sub(r"Н(?!.*Н)", r"-Н", number.strip())


def get_agent_providers(agent_id: ObjectId) -> list:
    """
    Управляемые (обслуживаемые) организации
    """
    agent_providers: list = []

    for house in House.objects(__raw__={
        'service_binds.provider': agent_id,  # индекс
    }).only('service_binds').as_pymongo():
        provider_id = None
        agent_active_bind: bool = False

        for bind in house.get('service_binds') or []:
            if not bind.get('is_active') or not bind.get('sectors'):
                continue  # архивная или "пустая" привязка
            elif not bind.get('date_start') or bind.get('date_end'):
                continue  # неактуальная привязка TODO сверять с текущей датой

            if bind['provider'] in agent_providers:  # уже встречался?
                continue

            if bind['business_type'] == BusinessType.udo_id():  # управление?
                assert provider_id is None, \
                    f"Несколько управляющих домом {house['_id']} организаций"
                provider_id = bind['provider']
            elif bind['business_type'] == BusinessType.cc_id():  # обслуживание?
                if bind['provider'] == agent_id:
                    agent_active_bind = True

            if agent_active_bind and provider_id is not None:
                break  # дом управляется обслуживаемой организацией

        if agent_active_bind and provider_id is not None:
            agent_providers.append(provider_id)

    return agent_providers  # ProviderId,...


def get_house_providers(agent_id: ObjectId) -> dict:
    """
    Получить (обслуживаемые) управляющие домами организации
    """
    assert agent_id, \
        "Идентификатор обслуживающей управляющие организации не определен"

    house_providers: dict = {}  # HouseId: ProviderId

    for house in House.objects(__raw__={
        'service_binds.provider': agent_id,  # индекс
    }).only('service_binds').as_pymongo():
        house_id: ObjectId = house['_id']
        cc_active_bind: bool = False
        udo_provider_id = None
        # TODO edo_provider_id = None

        for bind in house['service_binds']:  # из условия запроса
            if not bind.get('is_active') or not bind.get('sectors'):
                continue  # архивная или привязка без направлений платежа
            elif is_between(  # WARN отсутствующая дата не проверяется
                earlie=bind.get('date_start'), later=bind.get('date_end')
            ):
                continue  # неактуальная привязка
            elif bind['business_type'] == BusinessType.udo_id():  # управление?
                # TODO если РЦ - "Управление домом", то УО - "Эксплуатация дома"
                #  if bind['provider'] == agent_id and edo_provider_id is not None:
                #     udo_provider_id = edo_provider_id
                #     continue  # к следующей привязке

                # WARN домом может управлять только одна организация
                assert udo_provider_id is None, \
                    f"Домом {house_id} кроме {udo_provider_id}" \
                    f" управляет {bind['provider']}"
                udo_provider_id = bind['provider']  # : ObjectId - обязательное
            elif bind['business_type'] == BusinessType.cc_id():  # обслуживание?
                if bind['provider'] == agent_id:
                    cc_active_bind = True  # РЦ найден
            # TODO elif bind['business_type'] == BusinessType.edo_id():  # эксплуатация
            #     if udo_provider_id is not None:
            #         edo_provider_id = bind['provider']
            #     elif udo_provider_id == agent_id:
            #         udo_provider_id = bind['provider']

        if cc_active_bind and udo_provider_id is not None:
            house_providers[house_id] = udo_provider_id

    return house_providers


def get_provider_house(provider_id: ObjectId, house_id: ObjectId = None,
        abort_failed: bool = True) -> ObjectId:
    """Установить дом провайдера"""
    from app.house.models.house import House
    houses: dict = {house['_id']: f"{house['address']} ~ " + (
        house.get('gis_fias') or house.get('fias_house_guid')
        or 'БЕЗ идентификатора ФИАС'
    ) for house in House.objects(__raw__={
        '_id': {'$in': list(get_binded_houses(provider_id))}  # : dict
    }).only(
        'address', 'fias_house_guid', 'gis_fias'
    ).as_pymongo()}
    if not houses:
        print("УПРАВЛЯЕМЫЕ ОРГАНИЗАЦИЕЙ ДОМА НЕ НАЙДЕНЫ!")
        house_id = None
    elif len(houses) == 1:  # единственный обслуживаемый дом?
        house_id = next(iter(houses))
        print(f"ЕДИНСТВЕННЫЙ ДОМ {house_id} - {houses[house_id]}")
    elif house_id not in houses:  # дом не обслуживается организацией!
        print('\n'.join(f"{_id} - {addr}" for _id, addr in houses.items()))
        house_id = None
    else:
        print(f"ВЫБРАНЫЙ ДОМ {house_id} - {houses[house_id]}")

    if not house_id and abort_failed:
        exit(1)

    return house_id
