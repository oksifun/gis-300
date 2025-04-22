from rest_framework import serializers
from rest_framework_mongoengine.serializers import drfm_fields
from mongoengine import DoesNotExist
from rest_framework.fields import CharField

from api.v4.serializers import CustomDocumentSerializer
from app.auth.core.exceptions import PasswordError, UsernameError
from app.auth.models.actors import Actor
from app.auth.models.api_user import PartnerAppsApiUser
from app.auth.models.token import AuthTokenPartnerApps


class ActorSerializer(CustomDocumentSerializer):
    class Meta:
        model = Actor
        fields = ('id', 'owner')


class RegisterPartnerApiUserSerializer(CustomDocumentSerializer):

    class Meta:
        model = PartnerAppsApiUser
        fields = ('username', 'role', )

    def create(self, validated_data):
        user = self.Meta.model(**validated_data)
        password = user.set_password()
        user.save()
        return password


class AuthTokenPartnerApiUserSerializer(CustomDocumentSerializer):
    login = CharField(required=True, source='user.username')
    password = CharField(required=True, source='user.password')

    class Meta:
        model = AuthTokenPartnerApps
        user_model = PartnerAppsApiUser
        fields = ('login', 'password', )

    def related_user(self, username: str) -> PartnerAppsApiUser:
        try:
            return self.Meta.user_model.objects.get(
                username=username,
                is_authenticated=True,
            )
        except DoesNotExist:
            raise UsernameError('Wrong username or not authorized')

    def create(self, validated_data: dict) -> AuthTokenPartnerApps:
        username = validated_data['user']['username']
        password = validated_data['user']['password']
        user: PartnerAppsApiUser = self.related_user(username)
        if not Actor.compare_password_with_hash(password, user.password):
            raise PasswordError('Wrong password')
        access_token = AuthTokenPartnerApps(user=user)
        access_token.save()
        return access_token


class FirstStepActivationSerializer(serializers.Serializer):
    account = drfm_fields.ObjectIdField(required=True)
    code = serializers.CharField(required=True)


class SecondStepActivationSerializer(serializers.Serializer):
    account = drfm_fields.ObjectIdField(required=True)
    area_number = serializers.CharField(required=True)


class DriveThroughTokenSerializer(serializers.Serializer):

    key = serializers.CharField(required=True)
