from datetime import datetime

import mongoengine

from app.auth.models.actors import Actor


class DriveThroughToken(mongoengine.Document):
    """Токен сквозной авторизации

    Хранится в Auth-DB, содержит информацию о юзере,
    создавшем токен + текстовый ключ, отдаваемый пользователем на фронт

    В старом интерфейсе реализован функционал создания токена для
    пользователя, в новом интерфейсе токен же нужен для определения,
    какой пользователь был редиректнут к нам со старого бэка.
    """

    meta = {
        'db_alias': 'auth-db',
        'collection': 'drive_through_token',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '$key',
            'user',
        ],
    }

    key = mongoengine.StringField(
        unique=True
    )
    user = mongoengine.ReferenceField(
        Actor,
        on_delete=mongoengine.CASCADE,
        verbose_name="Пользователь"
    )
    created_at = mongoengine.DateTimeField(default=datetime.now())
