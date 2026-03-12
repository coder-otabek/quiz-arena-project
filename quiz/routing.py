from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/game/(?P<game_pin>\d+)/host/$',
            consumers.GameConsumer.as_asgi(),
            kwargs={'role': 'host'}),
    re_path(r'ws/game/(?P<game_pin>\d+)/player/(?P<player_id>\d+)/$',
            consumers.GameConsumer.as_asgi(),
            kwargs={'role': 'player'}),
]
