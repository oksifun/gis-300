import os
import django

from channels.routing import (
    ProtocolTypeRouter,
    URLRouter,
)
from mongoengine_connections import register_mongoengine_connections
# Перед нижними импортами обязательно нужно подключиться к базе.
register_mongoengine_connections()
from app.socket.api.v4.routing import channels_urls
from app.socket.api.v4.utils.authentication import SessionAuthMiddleware


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
register_mongoengine_connections()

application = ProtocolTypeRouter({
    "websocket": SessionAuthMiddleware(
        URLRouter(channels_urls),
    )
})
