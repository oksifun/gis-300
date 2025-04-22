from pprint import pprint

from app.gis.client.clients.agnostic_service_type_client import \
    AgnosticServiceTypeClient
from mongoengine_connections import register_mongoengine_connections
from bson import ObjectId

from processing.models.billing.service_type import ServiceType

register_mongoengine_connections()

# region AGNOSTIC SERVICE TYPE
# ast_client = AgnosticServiceTypeClient()
#
# service_types_list = [ObjectId('526234c0e0e34c474382231f'), ObjectId('526234c0e0e34c4743822320'), ObjectId('526234c0e0e34c4743822321'),]
# service_type_one = ObjectId('526234c0e0e34c4743822320')
#
# s_types = ast_client.get_many_by_ids(service_types_list).json()
# # s_type = ast_client.get_by_id(service_type_one).json()
# pprint(s_types)
# pprint(s_type)
# endregion AGNOSTIC SERVICE TYPE

trees = ServiceType.get_services_tree()
pprint(trees)
