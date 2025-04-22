from bson import ObjectId

from app.admin.core.data_restore.base import DataRestore
from app.telephony.models.call_log_history import Calls


class ProviderTelephonyDataRestore(DataRestore):
    _PIPELINE = [
        (Calls, 'provider'),
    ]


def restore_telephony(provider_id, batch_size=None,
                      host='10.1.1.221', logger=None):
    restorer = ProviderTelephonyDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(provider_id))
