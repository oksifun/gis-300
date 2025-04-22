from typing import Union

from app.auth.models.actors import Actor
from app.auth.models.drivethrough_token import DriveThroughToken
from app.personnel.models.personnel import Worker


class DriveThroughTokenSelector:
    """Селектор для взаимодействия с токеном авторизации

    Предоставляет функционал для получения токена по юзеру
    (если для данного юзера токен уже существует), или же по ключу
    """

    def __init__(self, user: Actor):

        self.user = user

    @classmethod
    def from_user(cls, user: Actor) -> Union[DriveThroughToken, None]:
        """Возвращает объект токена, созданного для данного юзера
        В случае если токена на юзера не зарегистрированно, возвращается
        None

        Args:
            user<Actor>: Объект пользователя, для которого ищем токен

        Returns:
            token | None: Объект токена или None

        """
        if isinstance(user, Worker):
            user = Actor.objects.filter(
                username=user.number
            ).first()
        active_tokens = DriveThroughToken.objects.filter(
            user=user.pk
        )
        return active_tokens.first()

    def get_by_key(self, key: str) -> DriveThroughToken:
        token = DriveThroughToken.objects.get(
            key=key,
            user=self.user
        )
        return token
