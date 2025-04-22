from app.area.models.area import Area
from app.catalogue.models.catalogue import Catalogue
from app.crm.models.crm import CRM, CRMEvent
from app.house.models.house import House
from app.meters.models.meter import HouseMeter, AreaMeter
from app.offsets.models.offset import Offset
from app.offsets.models.reversal import Reversal
from app.personnel.models.personnel import Worker
from app.requests.models.request import Request
from app.tickets.models.support import SupportTicket
from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment
from processing.models.billing.provider.main import Provider
from processing.models.billing.responsibility import Responsibility
from processing.models.billing.units import OkeiUnit

DENORMALIZING_SCHEMA = {
    House: [
        Area,
        HouseMeter,
        Tenant,
        AreaMeter,
    ],
    Tenant: [
        Responsibility,
        Accrual,
        Payment,
        Offset,
        Reversal,
    ],
    Area: [
        Accrual,
        Tenant,
        Payment,
        AreaMeter
    ],
    CRM: [
        CRMEvent,
    ],
    Provider: [
        CRM,
        CRMEvent,
    ],
    OkeiUnit: [
        Catalogue,
    ],
    Worker: [
        Request,
        SupportTicket,
    ],
}
