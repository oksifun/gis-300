import datetime

from mongoengine import Q, DoesNotExist

from app.payment.models.denormalization.embedded_docs import \
    DenormalizedVendorPaymentDoc
from app.payment.models.vendor_pay import VendorPayment, \
    VendorPaymentServiceEmbedded
from app.payment.models.vendor_pay_doc import VendorPaymentDoc
from app.offsets.models.offset import Offset, OffsetOperationAccount
from processing.models.billing.payment import PaymentDoc, Payment


def create_payments_by_services_fees_houses(doc, services_houses,
                                            auto_save_doc=True):
    if services_houses is None:
        houses_services = {
            (None, None): None,
        }
    else:
        houses_services = _get_houses_dict(services_houses)
    for fee_house, services in houses_services.items():
        fee = fee_house[0]
        house = fee_house[1]
        payments = _get_payments(
            doc,
            fee,
            house,
            services,
        )
        if not payments:
            continue
        doc.value += sum(p.value for p in payments)
        if auto_save_doc:
            VendorPayment.objects.insert(payments)
            doc.save()


def _get_payments(doc, fee, house_id, services):
    queryset = _get_payments_queryset(
        doc.owner,
        doc.source_date,
        doc.bank_account,
        fee,
        house_id,
    )
    payments = []
    for payment in queryset:
        services_dict = {}
        advance = payment['value']
        value = 0
        for offset in payment['offsets']:
            if 'AdvanceRepayment' in offset['_type']:
                if 'Advance' not in offset['_type']:
                    continue
                if (
                        offset['op_credit']
                        != OffsetOperationAccount.ADVANCE_PAYMENT
                        and offset['op_debit']
                        != OffsetOperationAccount.ADVANCE_PAYMENT
                ):
                    continue
            for service in offset['services']:
                if not service.get('vendor'):
                    continue
                if (
                        service['vendor']['contract'] == doc.contract
                        and (
                            services is None
                            or service['service_type'] in services
                        )
                ):
                    services_dict.setdefault(service['service_type'], 0)
                    services_dict[service['service_type']] += service['value']
                    value += service['value']
                advance -= service['value']
        payments.append(
            VendorPayment(
                doc=DenormalizedVendorPaymentDoc.from_ref(doc),
                payment=payment['_id'],
                # offset=offset['_id'],
                value=value,
                services=[
                    VendorPaymentServiceEmbedded(
                        service=k,
                        value=v,
                    )
                    for k, v in services_dict.items()
                ],
            ),
        )
    return payments


def _get_payments_queryset(owner, date, bank_account, fee, house_id):
    query = Q(
        doc__provider=owner,
        doc__date=date,
    )
    if house_id:
        query &= Q(account__area__house__id=house_id)
    queryset = Payment.objects(query)
    doc_match = {
        'doc.bank_number': bank_account,
    }
    if fee is not None:
        if fee == 0:
            doc_match['doc.bank_fee'] = {'$in': [0, None]}
        else:
            doc_match['doc.bank_fee'] = fee
    pipeline = [
        {
            '$lookup': {
                'from': 'PaymentDoc',
                'localField': 'doc._id',
                'foreignField': '_id',
                'as': 'doc',
            },
        },
        {
            '$unwind': '$doc',
        },
        {
            '$match': doc_match,
        },
        {
            '$project': {
                '_id': 1,
                'value': 1,
            },
        },
        {
            '$lookup': {
                'from': 'Offsets',
                'foreignField': 'refer._id',
                'localField': '_id',
                'as': 'offsets',
            },
        },
    ]
    return queryset.aggregate(*pipeline)


def _get_houses_dict(services_houses):
    houses_services = {}

    def _add_service_to_dict(house_key, service_id):
        services = houses_services.setdefault(house_key, [])
        services.append(service_id)

    for service_data in services_houses:
        if service_data.get('fees') is None:
            _add_service_to_dict((None, None), service_data['id'])
            continue
        for fee_data in service_data['fees']:
            if fee_data.get('houses') is None:
                _add_service_to_dict(
                    (fee_data['fee'], None),
                    service_data['id'],
                )
                continue
            for house in fee_data['houses']:
                _add_service_to_dict(
                    (fee_data['fee'], house),
                    service_data['id'],
                )
    return houses_services


def generate_vendor_payments(provider_id, date_on, contract_id):
    offsets = _get_offsets_queryset(provider_id, date_on, contract_id)
    payment_docs = {}
    docs = {}
    payments = []
    report = {}
    for offset in offsets:
        if 'AdvanceRepayment' in offset['_type']:
            if 'Refund' in offset['_type']:
                continue
            if 'Repayment' in offset['_type']:
                continue
        if 'Advance' in offset['_type']:
            if (
                offset['op_credit'] != OffsetOperationAccount.ADVANCE_PAYMENT
                and offset['op_debit'] != OffsetOperationAccount.ADVANCE_PAYMENT
            ):
                continue
        doc_id = offset['refer']['doc'].get('_id')
        if not doc_id:
            try:
                payment = Payment.objects(
                    pk=offset['refer']['_id'],
                ).only(
                    'doc.id',
                ).as_pymongo().get()
            except DoesNotExist:
                continue
            doc_id = payment['doc']['_id']
        payment_doc = payment_docs.get(doc_id)
        if not payment_doc:
            payment_doc = _get_payment_doc(doc_id)
            payment_docs[doc_id] = payment_doc
        if not payment_doc or not payment_doc.get('bank_number'):
            continue
        doc, pay = _choose_vendor_payment_doc(
            docs,
            payment_doc,
            offset,
            provider_id,
            contract_id,
            date_on,
        )
        payments.append(pay)
        for service in pay.services:
            key = (
                payment_doc['bank_number'],
                service.service,
                payment_doc.get('bank_fee') or 0,
                offset['refer']['account']['area']['house']['_id'],
            )
            report.setdefault(key, 0)
            report[key] += service.value
    # if payments:
    #     VendorPayment.objects.insert(payments)
    return report


def _choose_vendor_payment_doc(docs, payment_doc, offset,
                               provider_id, contract_id, date):
    key = (date, contract_id, payment_doc['bank_number'])
    doc = docs.get(key)
    value = 0
    services = []
    for service in offset['services']:
        if not service.get('vendor'):
            continue
        if service['vendor'].get('contract') != contract_id:
            continue
        value += service['value']
        services.append(
            VendorPaymentServiceEmbedded(
                service=service['service_type'],
                value=service['value'],
            ),
        )
    if not doc:
        doc = VendorPaymentDoc(
            owner=provider_id,
            contract=contract_id,
            bank_account=payment_doc['bank_number'],
            source_date=date,
            value=0,
            state='temp',
            date=datetime.datetime.now(),
        )
        doc.save()
    doc.value += value
    pay = VendorPayment(
        doc=DenormalizedVendorPaymentDoc.from_ref(doc),
        payment=offset['refer']['_id'],
        offset=offset['_id'],
        value=value,
        house=offset['refer']['account']['area']['house']['_id'],
        services=services,
    )
    return doc, pay


def _get_offsets_queryset(provider_id, date_on, contract_id):
    return Offset.objects(
        refer__doc__provider=provider_id,
        refer__doc__date=date_on,
        services__vendor__contract=contract_id,
        offset_kind__in=['Repayment', 'Advance'],
    ).only(
        'id',
        'services',
        'refer.id',
        'refer.doc.id',
        'refer.doc.date',
        'refer.account.area.house.id',
        'accrual.date',
        'offset_kind',
        'op_debit',
        'op_credit',
    ).as_pymongo()


def _get_payment_doc(doc_id):
    return PaymentDoc.objects(
        id=doc_id,
    ).only(
        'id',
        'bank_number',
        'bank_fee',
    ).as_pymongo().first()
