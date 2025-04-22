from secrets import token_urlsafe

from app.auth.api.selectors.drivethrough_token_selector import DriveThroughTokenSelector
from app.auth.models.actors import Actor
from app.auth.models.drivethrough_token import DriveThroughToken
from app.personnel.models.personnel import Worker


class DriveThroughTokenService:
    """Сервис для взаимодействия с токеном сквозной авторизации
    """

    def __init__(self, token: DriveThroughToken):

        self.token = token

    @classmethod
    def create(cls, user: Actor) -> DriveThroughToken:
        """Создает инстанс токена сквозной авторизации для данного юзера
        В случае если токен на пользователя уже зарегистрирован, предыдущий токен
        удаляется из базы

        Args:
            user<Actor>: Объект пользователя, для которого создаем токен

        Returns:
            token<DriveThroughToken>: Объект токена, созданного на пользователя

        """
        token = DriveThroughTokenSelector.from_user(user)

        if token is not None:
            token.delete()

        if isinstance(user, Worker):
            user = Actor.objects.filter(
                username=user.number
            ).first()
        new_token = DriveThroughToken(
            user=user,
            key=token_urlsafe(32)
        )
        new_token.save()

        return new_token
