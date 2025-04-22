import logging

from mongoengine.connection import (
    disconnect, register_connection, connect, get_connection
)
from pymongo import ReadPreference

import settings


logger = logging.getLogger('c300')

DATABASES = getattr(settings, 'DATABASES')


def register_mongoengine_connections(secondary_prefered=False, **kwargs):
    logger.warning(
        'Start register_mongoengine_connections(). %s',
        DATABASES["default"]["host"],
    )
    if secondary_prefered:
        main_read_preference = ReadPreference.SECONDARY
    else:
        main_read_preference = ReadPreference.PRIMARY_PREFERRED
    if "replicaset" in DATABASES["default"]:
        register_connection(
            'legacy-db',
            name=DATABASES["default"]["db"],
            host=DATABASES["default"]["host"],
            read_preference=main_read_preference,
            replicaSet=DATABASES["default"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'legacy-db',
            name=DATABASES["default"]["db"],
            host=DATABASES["default"]["host"]
        )

    if "replicaset" in DATABASES["cache"]:
        register_connection(
            'cache-db',
            name=DATABASES["cache"]["db"],
            host=DATABASES["cache"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["cache"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'cache-db',
            name=DATABASES["cache"]["db"],
            host=DATABASES["cache"]["host"],
            **kwargs,
        )

    if "replicaset" in DATABASES["auth"]:
        register_connection(
            'auth-db',
            name=DATABASES["auth"]["db"],
            host=DATABASES["auth"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["auth"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'auth-db',
            name=DATABASES["auth"]["db"],
            host=DATABASES["auth"]["host"],
            **kwargs,
        )

    if "replicaset" in DATABASES["processing"]:
        register_connection(
            'queue-db',
            name=DATABASES["processing"]["db"],
            host=DATABASES["processing"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["processing"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'queue-db',
            name=DATABASES["processing"]["db"],
            host=DATABASES["processing"]["host"],
            **kwargs,
        )
    if "replicaset" in DATABASES["logs"]:
        register_connection(
            'logs-db',
            name=DATABASES["logs"]["db"],
            host=DATABASES["logs"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["logs"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'logs-db',
            name=DATABASES["logs"]["db"],
            host=DATABASES["logs"]["host"],
            **kwargs,
        )

    if "replicaset" in DATABASES["files"]:
        register_connection(
            'files-db',
            name=DATABASES["files"]["db"],
            host=DATABASES["files"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["files"]["replicaset"],
            connectTimeoutMS=20,
            serverSelectionTimeoutMS=20,
            **kwargs,
        )
    else:
        register_connection(
            'files-db',
            name=DATABASES["files"]["db"],
            host=DATABASES["files"]["host"],
            connectTimeoutMS=20,
            **kwargs,
        )

    if "replicaset" in DATABASES["fias"]:
        register_connection(
            'fias-db',
            name=DATABASES["fias"]["db"],
            host=DATABASES["fias"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["fias"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'fias-db',
            name=DATABASES["fias"]["db"],
            host=DATABASES["fias"]["host"],
            **kwargs,
        )

    if "replicaset" in DATABASES["gis_data"]:
        register_connection(
            'gis-db',
            name=DATABASES["gis_data"]["db"],
            host=DATABASES["gis_data"]["host"],
            read_preference=ReadPreference.PRIMARY_PREFERRED,
            replicaSet=DATABASES["gis_data"]["replicaset"],
            **kwargs,
        )
    else:
        register_connection(
            'gis-db',
            name=DATABASES["gis_data"]["db"],
            host=DATABASES["gis_data"]["host"],
            **kwargs,
        )


def register_testing_mongoengine_connections():
    register_connection(
        'legacy-db',
        name=DATABASES["test_legacy"]["db"],
        host=DATABASES["test_legacy"]["host"]
    )

    register_connection(
        'auth-db',
        name=DATABASES["test_auth"]["db"],
        host=DATABASES["test_auth"]["host"]
    )

    register_connection(
        'queue-db',
        name=DATABASES["test_processing"]["db"],
        host=DATABASES["test_processing"]["host"]
    )

    register_connection(
        'files-db',
        name=DATABASES["test_files"]["db"],
        host=DATABASES["test_files"]["host"]
    )

    register_connection(
        'fias-db',
        name=DATABASES["test_fias"]["db"],
        host=DATABASES["test_fias"]["host"]
    )

    register_connection(
        'gis-db',
        name=DATABASES["test_gis_data"]["db"],
        host=DATABASES["test_gis_data"]["host"]
    )

    register_connection(
        'cache-db',
        name=DATABASES["test_cache"]["db"],
        host=DATABASES["test_cache"]["host"]
    )
    register_connection(
        'logs-db',
        name=DATABASES["test_logs"]["db"],
        host=DATABASES["test_logs"]["host"]
    )

    return {
        'legacy-db': get_connection('legacy-db'),
        'queue-db': get_connection('queue-db'),
        'files-db': get_connection('files-db'),
        'cache-db': get_connection('cache-db'),
        'gis-db': get_connection('gis-db'),
        'logs-db': get_connection('logs-db'),
    }


def destroy_testing_mongoengine_connections():
    disconnect('legacy-db')
    disconnect('queue-db')
    disconnect('files-db')
    disconnect('fias-db')
    disconnect('gis-db')
    disconnect('cache-db')
    disconnect('logs-db')


def drop_testing_databases():
    connect(DATABASES["test_legacy"]["db"])\
        .drop_database(DATABASES["test_legacy"]["db"])

    connect(DATABASES["test_processing"]["db"]) \
        .drop_database(DATABASES["test_processing"]["db"])

    connect(DATABASES["test_files"]["db"]) \
        .drop_database(DATABASES["test_files"]["db"])

    connect(DATABASES["test_fias"]["db"]) \
        .drop_database(DATABASES["test_fias"]["db"])

    connect(DATABASES["test_gis_data"]["db"]) \
        .drop_database(DATABASES["test_gis_data"]["db"])

    connect(DATABASES["test_cache"]["db"]) \
        .drop_database(DATABASES["test_cache"]["db"])

    connect(DATABASES["test_logs"]["db"]) \
        .drop_database(DATABASES["test_logs"]["db"])
