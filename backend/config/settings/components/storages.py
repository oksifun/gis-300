# -*- coding: utf-8 -*-
import os

from config.settings.components import BASE_DIR, config


DEFAULT_FILE_STORAGE = 'app.storage.storages.C300Storage'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = config('DJANGO_MEDIA_URL', default='')

PROXY_STORAGE = {
    'PROXY_STORAGE_CLASSES': {
        'c300storage': 'app.storage.storages.C300Storage',
    }
}

SELECTEL_STORAGES = {
    'default': {
        'USERNAME': config('AWS_ACCESS_KEY_ID'),
        'PASSWORD': config('AWS_SECRET_ACCESS_KEY'),
        'CONTAINER': config('AWS_S3_BUCKET'),
    },
}
