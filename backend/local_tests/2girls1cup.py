from bson import ObjectId

from app.gis.models.attachment import Attachment
from app.gis.models.gis_appeal import GisAppeal
from app.gis.models.guid import GUID
from app.gis.tasks.appeals import export_appeal_answer, update_one_appeal, \
    assign_appeal_performer, mark_appeal_executed, \
    mark_appeal_answer_not_required

from mongoengine_connections import register_mongoengine_connections

register_mongoengine_connections()
provider_id = ObjectId('526234b3e0e34c4743821fbd')
house_id = ObjectId('576bfd470ce661001f316d16')
appeal_id = ObjectId('67b844c8dbe92678c4961ad3')
file_ids = []
answer_text = 'Текст ответа на обращение не требуется'



assign_appeal_performer(provider_id,house_id,appeal_id)
export_appeal_answer(provider_id, house_id, answer_text, file_ids, appeal_id)
mark_appeal_executed(provider_id, house_id, appeal_id)
update_one_appeal(provider_id, house_id, appeal_id)
mark_appeal_answer_not_required(provider_id, house_id, answer_text,appeal_id)