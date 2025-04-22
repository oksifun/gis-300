from datetime import datetime

from django.http import HttpResponseBadRequest

from rest_framework.response import Response
from rest_framework import status
from api.v4.viewsets import PublicViewSet
from app.acquiring.core.actions import get_private_payment_details
from app.acquiring.models.choices import TenantPayActionType
from app.auth.models.actors import Actor
from app.public.api.v4.consts import TELEPHONE_CODES, TASK_RUNNER_URL
from app.public.api.v4.serializers import PublicPayCallTaskCreateSerializer, \
    PublicPayCallTaskSerializer, PublicQrAccountSerializer, \
    PublicQrCreateAccountSerializer, PublicQrUpdateAccountSerializer, \
    PublicQrGetAccountSerializer
from app.public.models.public_dialing import PublicPayCall
from app.public.models.public_qr_pay import AddressAndSectorsEmbedded, \
    PublicPayQr, SessionPayEmbedded
from app.public.tasks.qr_call import qr_verification_call
from processing.models.billing.account import Tenant
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES_AS_DICT
import requests


def convert(sectors):
    """Добавляет название направлений на русском"""
    dec = ACCRUAL_SECTOR_TYPE_CHOICES_AS_DICT
    sectors = [{'text': dec[sector],
                'value': sector} for sector in sectors]
    return sectors


def _validate_phone(phone):
    if len(phone) != 11:
        return None
    if not phone.isdigit():
        return None
    if phone.startswith('7'):
        phone = '8' + phone[1:]
    if not phone.startswith('89'):
        return None
    return phone


class CallStarterViewSet(PublicViewSet):

    def create(self, request):
        """
        Запрос в ЛК на постановку задачи на дозвон.
        Возвращает id задачи.
        """
        serializer = PublicPayCallTaskCreateSerializer(data=request.data)
        guest_number = serializer.validated_data.get('guest_number')
        if not guest_number:
            return Response(data=dict(status='fail'),
                            status=status.HTTP_400_BAD_REQUEST)
        response = requests.post(TASK_RUNNER_URL,
                                 data={"guest_number": guest_number},
                                 verify=False)
        if response.status_code == 404:
            return Response(data=dict(status='server error'),
                            status=status.HTTP_404_NOT_FOUND)
        return Response(data=response.json())

    def partial_update(self, request, pk):
        """
        Запрос в ЛК на проверку успеха верификации.
        """
        verification_num = request.data.get('verification_num')
        path = f'{TASK_RUNNER_URL}{pk}/'
        response = requests.patch(path,
                                  data={"verification_num": verification_num},
                                  verify=False)
        return Response(data=response.json())


class PublicPayTaskViewSet(PublicViewSet):
    http_method_names = ['post', 'get', 'patch']

    def create(self, request):
        """
        Создает запись в PublicPayCall, дозвон попадает в очередь.
        """
        serializer = PublicPayCallTaskCreateSerializer(data=request.data)
        guest_number = serializer.validated_data.get('guest_number')
        # с фронта приходит первая цифра 7
        guest_number = _validate_phone(guest_number)
        if not guest_number:
            return HttpResponseBadRequest('Wrong phone number format')
        exists_call = PublicPayCall.objects(guest_number=guest_number)
        if exists_call:
            exists_call.delete()
        call_task = PublicPayCall(guest_number=guest_number)
        call_task.save()
        celery_task = qr_verification_call.delay(
            task_id=call_task.id,
            phone_number=guest_number,
        )
        PublicPayCall.objects(
            id=call_task.id,
        ).update_one(
            task_id=celery_task.id,
        )
        return Response(data=dict(call_task_id=str(call_task.id)))

    def partial_update(self, request, pk):
        """
        Сверяет пользовательский ввод с исходящим номером дозвона.
        Удаляет запись из коллекции в случае успеха.
        """
        serializer = PublicPayCallTaskSerializer(data=request.data)
        verification_num = serializer.validated_data.get('verification_num')
        if verification_num not in TELEPHONE_CODES:
            return Response(data=dict(status='fail'))
        call_task = PublicPayCall.objects(id=pk)
        call_task.delete()
        return Response(data=dict(status='success'))


class PublicQrAccountViewSet(PublicViewSet):

    def list(self, request):
        """
        Возвращает список адресов жителя и направления к ним
        по номеру тел. или почте.
        Прихранивает тел. если его нет.
        Создает запись в TenantPayAction.
        """
        serializer = PublicQrAccountSerializer(data=request.query_params)
        phone = _validate_phone(serializer.validated_data.get('phone'))
        if not phone:
            return HttpResponseBadRequest('Wrong phone number format')
        email = serializer.validated_data.get('email')
        # словарь с данными по пользователю для фронта
        response_data = {'status': 'success',
                         'tenant_addresses': []}
        phone = self.remove_phone_prefix(phone)
        if email:
            tenant_accounts = Tenant.objects(__raw__={'email': email})
            if not tenant_accounts:
                response_data.update({'status': 'fail'})
                return Response(data=response_data)
            else:
                self.add_phone_to_tenant(tenant_accounts, phone)
        elif phone:
            tenant_accounts = Tenant.objects(__raw__=
                                             {'phones.str_number': phone})
            if not tenant_accounts:
                return Response(data=response_data)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        addresses_and_sectors = self.get_actors_data(
            self.get_actual_tenants(
                tenant_accounts=tenant_accounts,
                phone=phone)
        )
        if not addresses_and_sectors:
            response_data.update({'status': 'fail'})
        if len(tenant_accounts) == 0 and len(addresses_and_sectors) == 0:
            response_data.update({'status': 'denied'})
        response_data.update({'tenant_addresses': addresses_and_sectors})
        return Response(data=response_data)

    @staticmethod
    def get_actual_tenants(tenant_accounts, phone):
        # Проверка на актуальность
        actual_accounts = []
        for tenant in tenant_accounts:
            for tenant_phone in tenant['phones']:
                if tenant_phone['str_number'] == phone and \
                        tenant_phone['not_actual'] is not True:
                    actual_accounts.append(tenant.id)
        return actual_accounts

    @staticmethod
    def add_phone_to_tenant(tenant_accounts, phone):
        for account in tenant_accounts:
            phone_field = DenormalizedPhone.denormalize(phone)
            has_double = False
            for account_phone in account['phones']:
                if account_phone['str_number'] == phone_field['str_number']:
                    account_phone['not_actual'] = False
                    has_double = True
            if has_double is False:
                phone_field['added_by_tenant'] = True
                account.phones.append(phone_field)
            try:
                account.save()
            except Exception as e:
                print(e)

    @staticmethod
    def get_actors_data(account_ids):
        """
        Проверяет доступ провайдера к которому относится аккаунт.
        Возвращает жителей с адресами и направлениями на русском.
        """
        actors = Actor.objects(owner__id__in=account_ids,
                               has_access=True,
                               provider__client_access=True).only(
            'owner', 'sectors').as_pymongo()

        addresses_and_sectors = []
        for actor in actors:
            tenant_id = str(actor['owner']['_id'])
            address_str = actor['owner']['house']['address'] + ', кв ' + \
                          actor['owner']['area']['str_number']
            sectors = actor['sectors']
            # переведем в удобный для фронта вид
            sectors = convert(sectors)
            addresses_and_sectors.append(dict(tenant_id=tenant_id,
                                              address_str=address_str,
                                              sectors=sectors))
        return addresses_and_sectors

    @staticmethod
    def remove_phone_prefix(phone):
        if len(phone) >= 11:
            phone = phone[1:]
        return phone


class PublicQrActionViewSet(PublicViewSet):

    def list(self, request):
        """
        Возвращает список адресов жителя и направления к ним по pay_action_id
        """
        serializer = PublicQrGetAccountSerializer(data=request.query_params)
        pay_action_id = serializer.validated_data.get('pay_action_id')
        tenant_addresses = self.get_addresses_and_sectors(pay_action_id)
        response_data = {'pay_action_id': pay_action_id,
                         'tenant_addresses': tenant_addresses}
        return Response(data=response_data)

    def create(self, request, pk=None):
        """
        Создает запись в TenantPayAction.
        Получает реквизиты для платежа по id жильца.
        """
        serializer = PublicQrCreateAccountSerializer(data=request.data)
        tenant_addresses = serializer.validated_data.get(
            'tenant_addresses')
        tenant_id = serializer.validated_data.get('tenant_id')
        sector = serializer.validated_data.get('sector')
        return_url = request.headers.get('Referer')
        pay_action_id, unpaid_exists = self.create_pay_log(
            tenant_addresses, tenant_id, sector)

        result = self.create_payment(tenant_id, sector, pay_action_id,
                                     unpaid_exists, return_url)
        return Response(data=result) if result else Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk):
        """
        Добавляет оплату ранее созданную в коллекцию TenantPayAction.
        Получает реквизиты для платежа по id жильца.
        """
        serializer = PublicQrUpdateAccountSerializer(data=request.data)
        tenant_id = serializer.validated_data.get('tenant_id')
        sector = serializer.validated_data.get('sector')
        pay_action_id = pk
        return_url = request.headers.get('Referer')
        unpaid_exists = self.update_pay_log(tenant_id, pay_action_id, sector)
        result = self.create_payment(tenant_id, sector, pay_action_id,
                                     unpaid_exists, return_url)
        return Response(data=result) if result else Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUES)

    @staticmethod
    def get_addresses_and_sectors(pay_action_id):
        """
        Получает данные из TenantPayAction.
        Отфильтровывает оплаченные адреса и направления.
        Возвращает жителей с адресами и направлениями на русском.
        """
        pay_action = PublicPayQr.objects(
            id=pay_action_id
        ).only(
            'addresses_and_sectors',
            'sessions_pay',
        ).as_pymongo().first()
        payments = pay_action['sessions_pay']
        addresses = pay_action['addresses_and_sectors']
        addresses_and_sectors = []
        for address in addresses:
            account_id = address['account_id']
            sectors = address['sectors']
            paid_sectors = [
                payment['sector'] for payment in payments
                if payment['account_id'] == account_id
            ]
            if paid_sectors:
                sectors = [sector for sector in sectors
                           if sector not in paid_sectors]
            if not sectors:
                continue
            # переведем в удобный для фронта вид
            sectors = convert(sectors)
            addresses_and_sectors.append(
                dict(
                    tenant_id=str(account_id),
                    address_str=address['full_address'],
                    sectors=sectors
                )
            )
        return addresses_and_sectors

    @staticmethod
    def create_pay_log(data, tenant_id, sector):
        create = datetime.now()
        pay_action = PublicPayQr(pay_service='qr_public_pay', create=create)
        amount_of_possible_spending = 0
        for point in data:
            sectors = [sector['value'] for sector in point['sectors']]
            amount_of_possible_spending += len(sectors)
            nested = AddressAndSectorsEmbedded(
                account_id=point['tenant_id'],
                full_address=point['address_str'],
                sectors=sectors
            )
            pay_action.addresses_and_sectors.append(nested)
        nested = SessionPayEmbedded(
            account_id=tenant_id,
            sector=sector,
            create=create
        )
        pay_action.sessions_pay.append(nested)
        pay_action.amount_of_possible_spending = amount_of_possible_spending
        try:
            pay_action.save()
        except Exception as e:
            print(e)
        unpaid_exists = amount_of_possible_spending != 1
        return str(pay_action.id), unpaid_exists

    @staticmethod
    def update_pay_log(tenant_id, pay_action_id, sector):
        pay_action = PublicPayQr.objects(id=pay_action_id).first()
        nested = SessionPayEmbedded(
            account_id=tenant_id,
            sector=sector,
            create=datetime.now()
        )
        pay_action.sessions_pay.append(nested)
        try:
            pay_action.save()
        except Exception as e:
            print(e)
        available_pays = len(pay_action.sessions_pay)
        unpaid_exists = available_pays != pay_action.amount_of_possible_spending
        return unpaid_exists

    @staticmethod
    def create_payment(tenant_id, sector, pay_action_id,
                       unpaid_exists, return_url):
        tenant = Tenant.objects(id=tenant_id).first()
        if not tenant:
            return
        if unpaid_exists:
            public_qr_url = '#/qr/payment/continuation/?id={}'.format(
                pay_action_id
            )
        else:
            public_qr_url = '#/qr/payment/continuation/'
        result = get_private_payment_details(
            pay_source=TenantPayActionType.PUBLIC_QR,
            tenant=tenant,
            return_url=return_url,
            pay_kind=sector,
            public_qr_url=public_qr_url,
            debt_as_default=True,
        )
        return result
