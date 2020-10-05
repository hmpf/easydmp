from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers
from rest_framework_jwt.compat import get_username_field
from rest_framework_jwt.serializers import VerificationBaseSerializer
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import JSONWebTokenAPIView

from easydmp.auth.models import User


jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER


def truncate_email(email):
    userpart, domain = email.rsplit('@', 1)
    domain = str(len(domain))
    return '{}@{}'.format(userpart, domain)


class AuthorizeJSONWebTokenSerializer(VerificationBaseSerializer):
    AUTHORIZED = ('admin', 'bird')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field] = serializers.CharField()

    def authorized_usernames(self):
        usernames = list(getattr(self, 'AUTHORIZED', []))
        superusers = User.objects.filter(is_superuser=True).values_list('username', flat=True)
        usernames.extend(superusers)
        return usernames

    @property
    def username_field(self):
        return get_username_field()

    def validate(self, attrs):
        token = attrs.get('token')
        username = attrs.get(self.username_field)

        if token and username:
            payload = self._check_payload(token=token)
            user = self._check_user(payload=payload)

            if user:
                if not user.is_active:
                    msg = _('User account is disabled.')
                    raise serializers.ValidationError(msg)

                # Nobody can impersonate magical users
                if username in self.authorized_usernames():
                    msg = _('Username not permitted.')
                    raise serializers.ValidationError(msg)

                # Only magical users may impersonate
                if not user.username in self.authorized_usernames():
                    msg = _('User is not permitted to authorize.')
                    raise serializers.ValidationError(msg)

                User = get_user_model()
                try:
                    impersonated_user = User.objects.get(**{self.username_field: username})
                    if not impersonated_user.is_active:
                        msg = _('User account to impersonate is disabled.')
                        raise serializers.ValidationError(msg)

                    payload = jwt_payload_handler(impersonated_user)

                    return {
                        'token': jwt_encode_handler(payload),
                        'user': impersonated_user,
                    }

                except User.DoesNotExist:
                    msg = _('User does not exist.')
                    raise serializers.ValidationError(msg)

            else:
                msg = _('Unable to log in with provided credentials.')
                raise serializers.ValidationError(msg)
        else:
            msg = _('Must include "{username_field}" and "token".')
            msg = msg.format(username_field=self.username_field)
            raise serializers.ValidationError(msg)



class ObfuscatedUserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='user-detail',
        lookup_field='pk'
    )
    truncated_email = serializers.SerializerMethodField()
    obfuscated_username = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'url',
            'username',
            'obfuscated_username',
            'truncated_email',
        ]

    def get_obfuscated_username(self, obj):
        if not '@' in obj.username:
            return obj.username
        return truncate_email(obj.username)

    def get_truncated_email(self, obj):
        if '@' not in obj.email:
            return ''
        return truncate_email(obj.email)


class UserSerializer(ObfuscatedUserSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'url',
            'username',
            'obfuscated_username',
            'email',
            'truncated_email',
        ]


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

#     def get_serializer_class(self):
#         if self.request.user.is_authenticated:
#             return UserSerializer
#         return ObfuscatedUserSerializer


class AuthorizeJSONWebTokenView(JSONWebTokenAPIView):
    serializer_class = AuthorizeJSONWebTokenSerializer


authorize_jwt_token = AuthorizeJSONWebTokenView.as_view()
