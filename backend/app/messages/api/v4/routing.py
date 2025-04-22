from django.conf.urls import url

from app.messages.api.v4.consumers import MessengerConsumer

messenger_websocket_urls = (
    url(r"^api/v4/ws/updates/$", MessengerConsumer),
)