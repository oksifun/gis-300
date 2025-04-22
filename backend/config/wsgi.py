import os

import settings

from django.core.wsgi import get_wsgi_application
from mongoengine_connections import register_mongoengine_connections

register_mongoengine_connections()
# application = get_wsgi_application()
# Для перехвата "глубинных" ошибок прилождения
application = get_wsgi_application()
