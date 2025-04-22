from bson import ObjectId
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from mongoengine import DoesNotExist

from api.v4.authentication import RequestAuth
from api.v4.forms.base import ConstantsBaseViewSet
from api.v4.permissions import SuperUserOnly
from api.v4.universal_crud import BaseCrudViewSet
from api.v4.viewsets import BaseLoggedViewSet
from app.house.models.house import House
from app.legal_entity.models.legal_entity_service import EntityAgreementService
from app.payment.api.v4.serializers import (
    VendorPaymentCreateByServicesSerializer, VendorPaymentCreateSerializer,
    VendorPaymentReceiptSerializer, VendorPaymentReceiptsSerializer,
    VendorPaymentReportDataSerializer, VendorPaymentReportParametersSerializer,
    VendorPaymentSerializer, VendorReceiptDocSerializer
)
from app.payment.core.vendor_pay import (
    create_payments_by_services_fees_houses, generate_vendor_payments
)
from app.payment.models.choices import (
    VENDOR_PAYMENT_DOC_STATUSES_CHOICES, VendorPaymentDocStatus
)
from app.payment.models.vendor_pay import VendorPayment
from app.payment.models.vendor_pay_doc import VendorPaymentDoc
from app.payment.models.vendor_receipt_doc import VendorReceiptDoc
from app.registries.models.parse_tasks import RegistryParseTask
from app.registries.tasks.parse_registry import (
    parse_registry, parse_sber_registry
)
from processing.data_producers.associated.services import (
    PENALTY_SERVICE_TYPE,
    get_service_names,
)
from processing.models.billing.account import Tenant
from processing.models.billing.payment import Payment, PaymentDoc
from processing.models.billing.sbol import SbolInRegistryTask


class PaymentRegistryReparseViewSet(BaseLoggedViewSet):
    permission_classes = (SuperUserOnly,)

    def partial_update(self, request, pk):
        try:
            self.reparse_payment_doc(ObjectId(pk))
        except DoesNotExist as e:
            return HttpResponseNotFound(e.args[0])
        return HttpResponse()

    @staticmethod
    def reparse_payment_doc(doc_id):
        doc = PaymentDoc.objects(pk=doc_id).get()
        task = RegistryParseTask.objects(
            file=doc.file.file,
        ).order_by(
            '-created',
        ).first()
        if task:
            parse_registry.delay(task.pk, existing_doc_id=doc_id)
            return
        task = SbolInRegistryTask.objects(
            reg_file__file_id=doc.file.file,
        ).order_by(
            '-created',
        ).first()
        if task:
            if task.state == 'ready':
                raise WrongStatusError(
                    "Task has already been assigned for reparsing")
            parse_sber_registry.delay(task.pk, existing_doc_id=doc_id)
            task.update(state='ready')
            return
        raise DoesNotExist('Task is not found')


class VendorPaymentViewSet(BaseCrudViewSet):
    serializer_classes = {
        'create': VendorPaymentCreateSerializer,
        'retrieve': VendorPaymentSerializer,
        'list': VendorPaymentSerializer,
        'partial_update': VendorPaymentSerializer,
    }
    slug = ('contractors_calculations', 'sales_receipts')

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return VendorPaymentDoc.objects(
            VendorPaymentDoc.get_binds_query(binds),
            state__ne=VendorPaymentDocStatus.TEMPORARY,
        ).order_by(
            '-date',
        )

    def create(self, request, *args, **kwargs):
        provider_id = RequestAuth(self.request).get_provider_id()
        request.data['owner'] = provider_id
        return super().create(request, *args, **kwargs)


class VendorReceiptDocViewSet(BaseCrudViewSet):
    serializer_class = VendorReceiptDocSerializer
    allowed_methods = ('GET',)
    slug = 'sales_receipts'

    def get_queryset(self, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return VendorReceiptDoc.objects(
            VendorReceiptDoc.get_binds_query(binds),
        ).order_by(
            '-date',
        )


class VendorPaymentReceiptsViewSet(BaseLoggedViewSet):
    slug = 'sales_receipts'

    def retrieve(self, request, pk):
        serializer = VendorPaymentReceiptsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        offset = serializer.validated_data['offset']
        limit = serializer.validated_data['limit']
        doc = VendorReceiptDoc.objects(pk=pk).get()
        receipts = VendorPayment.objects(
            doc__id=doc.remitter_doc,
            is_deleted__ne=True,
        ).only(
            'id',
            'value',
            'payment',
            'has_receipt',
            'services',
        ).as_pymongo()[offset: offset + limit]
        receipts = list(receipts)
        payments = self._get_payments(receipts)
        accounts = self._get_accounts(payments.values())
        for receipt in receipts:
            receipt['id'] = receipt['_id']
            payment = payments.get(receipt['payment'])
            if not payment:
                continue
            account = payment['account']['_id']
            receipt['account_name'] = accounts[account]['str_name']
            receipt['account_address'] = '{}, {}'.format(
                accounts[account]['area']['house']['address'],
                accounts[account]['area']['str_number'],
            )
            receipt['sector'] = payment['sector_code']
            receipt['date'] = payment['doc']['date']
            receipt['penalty_included'] = 0
            for service in receipt['services']:
                if service['service'] == PENALTY_SERVICE_TYPE:
                    receipt['penalty_included'] += service['value']
        return JsonResponse(
            data={
                'results': VendorPaymentReceiptSerializer(
                    receipts,
                    many=True,
                ).data,
            },
        )

    def _get_accounts(self, payments):
        accounts_ids = {p['account']['_id'] for p in payments}
        accounts = Tenant.objects(
            pk__in=accounts_ids,
        ).only(
            'id',
            'str_name',
            'area.str_number',
            'area.house.address',
        ).as_pymongo()
        return {a['_id']: a for a in accounts}

    def _get_payments(self, receipts):
        payment_ids = {r['payment'] for r in receipts}
        payments = Payment.objects(
            pk__in=list(payment_ids),
            account__ne=None,
        ).only(
            'id',
            'account.id',
            'sector_code',
            'doc.date',
        ).as_pymongo()
        return {p['_id']: p for p in payments}


class VendorPaymentReportViewSet(BaseLoggedViewSet):
    slug = 'contractors_calculations'

    def create(self, request, *args, **kwargs):
        serializer = VendorPaymentCreateByServicesSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        provider_id = RequestAuth(self.request).get_provider_id()
        doc = serializer.create(serializer.validated_data, provider_id)
        create_payments_by_services_fees_houses(
            doc,
            serializer.validated_data.get('services'),
        )
        return JsonResponse(data=VendorPaymentSerializer(doc).data)

    def list(self, request):
        serializer = VendorPaymentReportParametersSerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)
        provider_id = RequestAuth(self.request).get_provider_id()
        date = serializer.validated_data['date']
        data = EntityAgreementService.objects(
            provider=provider_id
        ).aggregate(
            {
                '$group': {
                    '_id': {
                        'contract': '$contract',
                        'service': '$service',
                        'service_type': '$service_select_type',
                    },
                    'entity_id': {
                        '$first': '$entity',
                    },
                },
            },
            {
                '$lookup': {
                    'from': 'ServiceType',
                    'localField': '_id.service',
                    'foreignField': '_id',
                    'as': 'service',
                },
            },
            {
                '$unwind': {
                    'path': '$service',
                    'preserveNullAndEmptyArrays': True,
                },
            },
            {
                '$lookup': {
                    'localField': 'entity_id',
                    'foreignField': '_id',
                    'from': 'LegalEntity',
                    'as': 'entity',
                },
            },
            {
                '$unwind': '$entity',
            },
            {
                '$project': {
                    '_id': 1,
                    'entity_id': 1,
                    'entity_name': '$entity.current_details.current_name',
                    'entity_inn': '$entity.current_details.current_inn',
                    'service': 1,
                }
            },
            {
                '$lookup': {
                    'localField': '_id.contract',
                    'foreignField': '_id',
                    'from': 'LegalEntityContract2',
                    'as': 'contract',
                },
            },
            {
                '$unwind': '$contract',
            },
            {
                '$project': {
                    '_id': 1,
                    'entity_id': 1,
                    'entity_name': 1,
                    'entity_inn': 1,
                    'contract_name': '$contract.name',
                    'contract_number': '$contract.number',
                    'service': 1,
                }
            },
            {
                '$group': {
                    '_id': '$_id.contract',
                    'entity_id': {
                        '$first': '$entity_id',
                    },
                    'entity_name': {
                        '$first': '$entity_name',
                    },
                    'entity_inn': {
                        '$first': '$entity_inn',
                    },
                    'contract_name': {
                        '$first': '$contract_name'
                    },
                    'contract_number': {
                        '$first': '$contract_number',
                    },
                    'services': {
                        '$push': {
                            'service': '$service',
                            'type': '$_id.service_type',
                        },
                    },
                },
            },
        )
        results = {}
        found_services = set()
        addresses = {}
        for contract_data in data:
            vendor = results.setdefault(
                contract_data['entity_id'],
                {
                    'id': contract_data['entity_id'],
                    'name': contract_data['entity_name'],
                    'inn': contract_data['entity_inn'],
                    'agreements': [],
                },
            )
            agreement = {
                'id': contract_data['_id'],
                'name': contract_data['contract_name'],
                'number': contract_data['contract_number'],
                'bank_accounts': [],
            }
            vendor['agreements'].append(agreement)
            report = generate_vendor_payments(
                provider_id,
                date,
                contract_data['_id'],
            )
            bank_services = {}
            service_fees = {}
            fee_houses = {}
            for key, value in report.items():
                bank_account = bank_services.get(key[0])
                if not bank_account:
                    bank_account = {
                        'number': key[0],
                        'services': [],
                    }
                    agreement['bank_accounts'].append(bank_account)
                    bank_services[key[0]] = bank_account
                service = service_fees.get((key[0], key[1]))
                found_services.add(key[1])
                if not service:
                    service = {
                        'id': key[1],
                        'name': '',
                        'fees': [],
                    }
                    bank_account['services'].append(service)
                    service_fees[(key[0], key[1])] = service
                fee = fee_houses.get((key[0], key[1], key[2]))
                if not fee:
                    fee = {
                        'fee': key[2],
                        'name': f'Комиссия {key[2]}%',
                        'houses': [],
                    }
                    service['fees'].append(fee)
                    fee_houses[(key[0], key[1], key[2])] = fee
                address = addresses.get(key[3])
                if not address:
                    house = House.objects(
                        pk=key[3],
                    ).only(
                        'address',
                    ).as_pymongo().get()
                    address = house['address']
                    addresses[key[3]] = address
                fee['houses'].append(
                    {
                        'id': key[3],
                        'address': address,
                        'balance_in': 0,
                        'paid': value,
                        'transfered': 0,
                        'for_transfer': value,
                    }
                )
        service_names = get_service_names(
            provider_id,
            found_services,
            old_style=True,
        )
        keys = ('balance_in', 'paid', 'transfered', 'for_transfer')
        for vendor in results.values():
            for contract in vendor['agreements']:
                for bank_account in contract['bank_accounts']:
                    for service in bank_account['services']:
                        service['name'] = service_names[service['id']]['title']
                        for fee in service['fees']:
                            for key in keys:
                                fee[key] = sum(i[key] for i in fee['houses'])
                        for key in keys:
                            service[key] = \
                                sum(i[key] for i in service['fees'])
                    for key in keys:
                        bank_account[key] = \
                            sum(i[key] for i in bank_account['services'])
                for key in keys:
                    contract[key] = \
                        sum(i[key] for i in contract['bank_accounts'])
            for key in keys:
                vendor[key] = sum(i[key] for i in vendor['agreements'])
        return JsonResponse(
            data={
                'results': VendorPaymentReportDataSerializer(
                    list(results.values()),
                    many=True,
                ).data,
            },
        )


class VendorPaymentsConstantsViewSet(ConstantsBaseViewSet):

    CONSTANTS_CHOICES = (
        (VENDOR_PAYMENT_DOC_STATUSES_CHOICES, VendorPaymentDocStatus),
    )


class WrongStatusError(Exception):
    pass
