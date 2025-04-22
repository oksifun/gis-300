from mongoengine import DoesNotExist

import settings
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.account import Account
from app.house.models.house import House
from processing.models.billing.provider.main import (
    Provider,
    BankProvider,
    ProviderPublicCode,
)
from app.news.models.news import News
from processing.models.billing.provider_public import ProviderPublicData
from processing.models.house_choices import HOUSE_TYPES_CHOICES_AS_DICT


class ProviderPublicDataGet:

    DATA_TYPE_DESCRIPTION = 'default'

    def __init__(self, code, query_args):
        self.query_args = query_args
        self.code_obj = ProviderPublicCode.objects.get(code=code)
        self.provider = Provider.objects.get(pk=self.code_obj.provider.pk)
        self.actor = {'binds': [self.provider.pk], 'actions': []}

    def get_data(self):
        try:
            data = ProviderPublicData.objects(
                data_type=self.DATA_TYPE_DESCRIPTION,
                provider=self.provider.pk,
            ).order_by('id').first()
        except DoesNotExist:
            return None
        return data.data

    def generate_file_url(self, file):
        if not file or not file.get('uuid'):
            return {}
        return {
            'filename': file.get('filename', ''),
            'url': '{}/api/v4/public/organization_files/?'
                   'org_code={}&data_code={}&uuid={}'.format(
                settings.URL,
                self.code_obj.code,
                self.DATA_TYPE_DESCRIPTION,
                file['uuid']
            )
        }


class OrganizationInfoPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'organization_info'

    DETAILS_KEYS = {
        'full_name': 'str_name',
        'short_name': 'str_name',
        'kpp': 'kpp',
        'okopf': 'okopf',
        'inn': 'inn',
        'ogrn': 'ogrn',
    }
    CONTACTS_KEYS = {
        'email': 'email',
        'website': 'url',
    }

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        self._extract_main_details(data['details'])
        self._extract_address_details(data['details'])
        self._extract_bank_details(data['details'])
        self._extract_contacts(data['contacts'])
        self._add_slugs(data)
        if data['logo']['image']:
            data['logo']['image'] = \
                self.generate_file_url(data['logo']['image'])
        if data['parallax']['image']:
            data['parallax']['image'] = \
                self.generate_file_url(data['parallax']['image'])
        for doc in data['certificates']:
            doc['image'] = self.generate_file_url(doc['image'])
        for doc in data['licenses']:
            doc['image'] = self.generate_file_url(doc['image'])
        return data

    def _add_slugs(self, data):
        data['slugs'] = {
            'about': {'read': True},
            'about_management': {'read': True},
            'about_requisites': {'read': True},
            'about_licenses': {'read': True},
            'about_contacts': {'read': True},
            'houses': {'read': True},
            'houses_list': {'read': True},
            'houses_info': {'read': True},
            'houses_history': {'read': True},
            'services': {'read': True},
            'documents': {'read': True},
            'responsibility': {'read': True},
            'meetings': {'read': True},
            'debtors': {'read': True},
            'information': {'read': True},
            'news': {'read': True},
            'events': {'read': True},
            'login': {'read': True},
            'payments': {'read': True},
        }

    def _extract_main_details(self, data):
        for k, v in self.DETAILS_KEYS.items():
            if data[k]:
                data[k] = getattr(self.provider, v)
            else:
                data.pop(k)

    def _extract_address_details(self, data):
        if data['correspondence_address']:
            location: str = self.provider.address.correspondence.location
            house_number: str = self.provider.address.correspondence.house_number
            address_str: str = location + ' ' + house_number if house_number else location

            data['correspondence_address'] = {
                'adress_str': address_str,
                'point': self.provider.address.correspondence.point.coordinates,
            }
        else:
            data.pop('correspondence_address')

        if data['postal_address']:
            location: str = self.provider.address.postal.location
            house_number: str = self.provider.address.postal.house_number
            address_str: str = location + ' ' + house_number if house_number else location

            data['postal_address'] = {
                'adress_str': address_str,
                'point': self.provider.address.postal.point.coordinates,
            }
        else:
            data.pop('postal_address')

        if data['real_address']:
            location: str = self.provider.address.real.location
            house_number: str = self.provider.address.real.house_number
            address_str: str = location + ' ' + house_number if house_number else location
            data['real_address'] = {
                'adress_str': address_str,
                'point': self.provider.address.real.point.coordinates,
            }
        else:
            data.pop('real_address')

    def _extract_bank_details(self, data):
        b_accounts = []
        for ba_id in data['bank_accounts']:
            for b_account in self.provider.bank_accounts:
                if b_account.bic.id == ba_id:
                    b_accounts.append(b_account)
                    break
        banks = list(BankProvider.objects.aggregate(*[
            {'$match': {
                '_id': {'$in': [a.bic.id for a in b_accounts]}
            }},
            {'$project': {
                'NameP': '$bic_body.NameP',
                'BIC': '$bic_body.BIC',
                'Account': '$bic_body.Account',
            }}
        ]))
        banks = {b['_id']: b for b in banks}
        result = []
        for b in b_accounts:
            result.append({
                'number': b.number,
                'name': banks[b.bic.id]['NameP'],
                'bic': banks[b.bic.id]['BIC'],
                'correspondent': banks[b.bic.id]['Account']
            })
        data['bank_accounts'] = result

    def _extract_contacts(self, data):
        # контакты
        for k, v in self.CONTACTS_KEYS.items():
            if data[k]:
                data[k] = getattr(self.provider, v)
            else:
                data.pop(k)
        if data.get('phones'):
            data['phones'] = []
            for phone in self.provider.phones:
                p_dict = phone.to_mongo().to_dict()
                if '_id' in p_dict:
                    p_dict.pop('_id')
                data['phones'].append(p_dict)
        else:
            data.pop('phones')
        return data


class StartPagePublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'start_page_content'


class NewsPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'news'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        if data['enabled']:
            limit = int(self.query_args.get('news_limit', 5))
            skip = int(self.query_args.get('news_skip', 0))
            news = News.objects.filter(
                author__provider=self.provider.pk,
                recipients_filter__recipients_types='for_tenants',
            ).order_by('-created_at').as_pymongo()[skip: limit + skip]
            result = {}
            for n in news:
                n['created_at'] = n['created_at'].strftime('%d.%m.%Y')
                files = []
                for f in n['files']:
                    files.append(self.generate_file_url(f))
                result[str(n['_id'])] = {
                    'subject': n['subject'],
                    'body': n['body'],
                    'created_at': n['created_at'],
                    'files': files,
                }
            return result
        else:
            return None


class ManagementPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'management'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        if data['enabled']:
            a_pipeline = [
                {'$match': {
                    'department.provider': self.provider.pk,
                    '_id': {'$in': data['workers']},
                    'is_deleted': {'$ne': True},
                }},
                {'$project': {
                    '_id': 0,
                    'str_name': 1,
                    'phones': 1,
                    'position_name': '$position.name',
                    'image': '$photo'
                }}
            ]
            workers = list(Account.objects.aggregate(*a_pipeline))
            for w in workers:
                w['phones'] = \
                    [p for p in w['phones'] if p.get('type') == 'work']
                for p in w['phones']:
                    if '_id' in p:
                        p.pop('_id')
                if w.get('image'):
                    w['image'] = self.generate_file_url(w['image'])
                else:
                    w['image'] = {}
            return {'management': workers}
        else:
            return None


class HousesPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'houses'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        if data['enabled']:
            houses_ids = get_binded_houses(self.provider.pk)
            houses = list(
                House.objects.filter(
                    pk__in=houses_ids,
                ).only(
                    'address',
                    'point.coordinates',
                    'fias_house_guid',
                    'area_overall',
                    'service_binds.provider',
                    'service_binds.business_type',
                    'build_date',
                    'floor_count',
                    'apartment_count',
                    'area_living',
                    'area_not_living',
                    'type',
                    'cadastral_number',
                ).order_by(
                    'address',
                ).as_pymongo()
            )
            for h in houses:
                b_types = []
                s_binds = h.pop('service_binds')
                for s_b in s_binds:
                    if s_b['provider'] == self.provider.pk:
                        b_types.append(str(s_b['business_type']))
                h['business_type'] = ', '.join(b_types)
                h['type'] = HOUSE_TYPES_CHOICES_AS_DICT.get(h.get('type'), '')
                h['_id'] = str(h['_id'])
            return {'houses': houses}
        else:
            return None


class LostHousesPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'lost_houses'


class HouseInfoPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'house_info'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        if data['enabled']:
            h_id = self.query_args.get('house_id')
            house = House.objects.get(
                id=h_id,
                bind__in=self.actor['binds'],
            ).fields(
                address=1, point__coordinates=1, fias_house_guid=1, street=1, number=1,
                structure=1, bulk=1, build_date=1, area_overall=1
            ).as_pymongo()
            if house['point']:
                house['point'] = house['point']['coordinates']
            return {'house': house}
        else:
            return None


class DocumentsPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'documents'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        result = {}
        for ix, n in enumerate(data['documents']):
            if '_id' in n:
                n.pop('_id')
            ff = []
            for f in n['files']:
                ff.append(self.generate_file_url(f))
            n['files'] = ff
            result[ix] = n
        data['documents'] = result
        return data


class ContraversionsPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'contraventions'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        for n in data['contraventions']:
            ff = []
            for d in n['documents']:
                ff.append(self.generate_file_url(d))
            n['documents'] = ff
            n['self_name'] = self.provider.str_name
        return data


class DebtorsPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'debtors'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        for n in data['documents']:
            n['file'] = self.generate_file_url(n['file'])
        return data


class UsefulInfoPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'useful_info'


class EventsPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'events'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        result = {}
        for ix, e in enumerate(data['events']):
            ff = []
            for i in e['files']:
                ff.append(self.generate_file_url(i))
            e['files'] = ff
            result[ix] = e
        data['events'] = result
        return data


class ServicesPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'services'


class MeetingsPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'meetings'

    def get_data(self):
        data = super().get_data()
        if not data:
            return None
        for n in data['meetings']:
            n['file'] = self.generate_file_url(n['file'])
        return data

