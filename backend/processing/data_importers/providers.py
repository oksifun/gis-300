from bson import ObjectId

from processing.models.billing.embeddeds.address import Address
from processing.models.billing.embeddeds.location import Location
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.provider.main import Provider
from processing.models.choices import LegalFormType
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from utils.crm_utils import get_or_create_relation_between_two_providers


_RESTRICTED_STATUSES = (
    'client',
    'debtor',
    'ban',
    'alien',
)
_FIELDS = (
    ('legal_form', 0),
    ('name', 1),
    # ('inn', 2),
    ('kpp', 3),
    # ('ogrn', 4),
    ('url', 5),
    # ('email', 8),
)
_BUSINESS_TYPES = {
    'Услуги аварийно-диспетчерской службы': '5427dc2bf3b7d44b1ae89b00',
    'Аварийное обслуживание': '5427dc2bf3b7d44b1ae89b01',
    'Эксплуатация домов': '5427dc2bf3b7d44b1ae89b02',
    'Поставка тепловой энергии и ГВС': '5427dc2bf3b7d44b1ae89b03',
    'Поставка ХВС': '5427dc2bf3b7d44b1ae89b04',
    'Контроль доступа': '5427dc2bf3b7d44b1ae89b05',
    'Обслуживание АППЗ': '5427dc2bf3b7d44b1ae89b06',
    'Обслуживание приборов учета': '5427dc2bf3b7d44b1ae89b07',
    'Управление инфраструктурой (ЗАО "Отдел")': '5427dc2bf3b7d44b1ae89b08',
    'Обслуживание видеонаблюдения': '5427dc2bf3b7d44b1ae89b09',
    'Поставка бытового газа': '5427dc2bf3b7d44b1ae89b0a',
    'Поставка электроэнергии': '5427dc2bf3b7d44b1ae89b0b',
    'Обслуживание ПЗУ': '5427dc2bf3b7d44b1ae89b0c',
    'Сигналы лифтов/сигнализации': '5427dc2bf3b7d44b1ae89b0d',
    'Управление домами': '5427dc2bf3b7d44b1ae89b0e',
    'Услуги охраны': '5427dc2bf3b7d44b1ae89b0f',
    'Водоотведение и канализирование': '5427dc2bf3b7d44b1ae89b10',
    'Вывоз мусора': '5427dc2bf3b7d44b1ae89b11',
    'Управление муниципальным имуществом': '5427dc2bf3b7d44b1ae89b12',
    'Кабельное телевидение': '5427dc2bf3b7d44b1ae89b13',
    'Кредитные организации': '546b25f5444d4b79fed4d3bf',
    'Государственные и муниципальные органы': '5475e9c79519f723e9c20448',
    'Застройщик': '547d9797904b83f4d2a346ec',
    'Демо-доступ': '548ef5748663fa8ff77d2faf',
    'Капитальный ремонт': '54de048ffa25145a45777849',
    'Расчетно-кассовый центр': '54de04c2fa25145a4577784a',
    'Продажа услуг и работ ЖКХ': '559168c1092dcfd6446b7f66',
    'Поставка нескольких коммунальных ресурсов': '5c07ee39f11289be7944353f',
    'Плательщик': '5ce7d97d57bd560001e42491',
}


def update_providers_data(logger, file_path, test_mode=False):
    with open(file_path) as f:
        lines = [x.replace('\n', '').split(';') for x in f.readlines()[1:]]
    logger(f'Всего строк {len(lines)}')
    updated = 0
    for ix, row in enumerate(lines):
        if len(row) < 3:
            logger(f'Пропущена строка {ix}')
            continue
        inn = row[2].strip()
        ogrn = row[4].strip()
        providers = list(Provider.objects(inn=inn, ogrn=ogrn).all())
        created = False
        if len(providers) == 0:
            logger(f'Организация не найдена {inn}')
            providers = [
                _create_dummy_provider(inn, ogrn, test_mode),
            ]
            created = True
        elif len(providers) > 1:
            logger(f'Найдено {len(providers)} организаций {inn}')
        for provider in providers:
            if not (test_mode and created):
                relations = get_or_create_relation_between_two_providers(
                    ZAO_OTDEL_PROVIDER_OBJECT_ID,
                    provider.id,
                )
                if relations.status in _RESTRICTED_STATUSES:
                    logger(
                        f'Организация {inn} пропущена как {relations.status}',
                    )
                    continue
            try:
                if _update_provider_data(provider, row, test_mode):
                    updated += 1
            except Exception as e:
                logger(f'Ошибка {inn}: {e}')
    logger(f'Обновлено организаций: {updated}')


def _create_dummy_provider(inn, ogrn, test_mode):
    provider = Provider(
        inn=inn,
        ogrn=ogrn,
        name='Новая',
        legal_form=LegalFormType.none,
    )
    if not test_mode:
        provider.save()
    return provider


def _update_provider_data(provider, data_row, test_mode):
    changed = False
    for key, ix in _FIELDS:
        val = data_row[ix].strip()
        if val and val != getattr(provider, key):
            setattr(provider, key, val)
            changed = True
    if _update_provider_phone_numbers(provider, data_row):
        changed = True
    if _update_provider_email(provider, data_row):
        changed = True
    if _update_provider_address(provider, data_row):
        changed = True
    if _update_provider_business_types(provider, data_row):
        changed = True
    if changed and not test_mode:
        provider.save()
    return changed


def _update_provider_business_types(provider, data_row):
    business_type = _BUSINESS_TYPES.get(data_row[9].strip())
    if business_type and ObjectId(business_type) not in provider.business_types:
        provider.business_types.append(ObjectId(business_type))
        return True
    return False


def _update_provider_email(provider, data_row):
    email = data_row[8].strip()
    if email and not provider.email:
        return False
    provider.email = email
    return True


def _update_provider_phone_numbers(provider, data_row):
    if not data_row[7].strip():
        return False
    phone = DenormalizedPhone(
        code=data_row[6].strip(),
        number=data_row[7].strip(),
    )
    if str(phone) not in [str(p) for p in provider.phones]:
        provider.phones.append(phone)
        return True
    return False


def _update_provider_address(provider, data_row):
    fias_street = data_row[11].strip()
    if not fias_street:
        return False
    if not provider.address:
        provider.address = Address()
    if not provider.address.real:
        provider.address.real = Location()
    if not provider.address.postal:
        provider.address.postal = Location()
    if not provider.address.correspondence:
        provider.address.correspondence = Location()
    fias_house = data_row[12].strip()
    if fias_street != provider.address.real.fias_street_guid:
        provider.address.real.fias_street_guid = fias_street
        provider.address.real.fias_house_guid = fias_house
        if not provider.address.postal.fias_street_guid:
            provider.address.postal.fias_street_guid = fias_street
            provider.address.postal.fias_house_guid = fias_house
        if not provider.address.correspondence.fias_street_guid:
            provider.address.correspondence.fias_street_guid = fias_street
            provider.address.correspondence.fias_house_guid = fias_house
        return True
    elif fias_house != provider.address.real.fias_house_guid:
        provider.address.real.fias_house_guid = fias_house
        return True
    return False
