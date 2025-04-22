import datetime
import logging.config

from loggingconfig import DICT_CONFIG
from mongoengine_connections import register_mongoengine_connections
from scripts.auth.provider_workers_permissions_to_actors import \
    get_worker_actor_duplicates, get_tenant_actor_duplicates, \
    get_provider_actor_duplicates, clean_tenant_actor_duplicates
from scripts.auth.tenant_pass import clean_password_warnings

if __name__ == '__main__':
    register_mongoengine_connections()
    logging.config.dictConfig(DICT_CONFIG)

    def logger(message=None, progress=None):
        print(message)


    print(datetime.datetime.now(), 'clean_password_warnings')
    clean_password_warnings(True)
    print(datetime.datetime.now(), 'get_worker_actor_duplicates')
    get_worker_actor_duplicates()
    print(datetime.datetime.now(), 'get_tenant_actor_duplicates')
    tenant_duplicates = get_tenant_actor_duplicates()
    print(datetime.datetime.now(), 'get_provider_actor_duplicates')
    get_provider_actor_duplicates()
    input('приступить к чистке?')
    clean_tenant_actor_duplicates(True, tenant_duplicates)
    print(datetime.datetime.now(), 'Finish')
