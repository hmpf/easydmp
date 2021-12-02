from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _

from easydmp.lib.api.viewsets import AnonReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.auth.models import User


def truncate_email(email):
    userpart, domain = email.rsplit('@', 1)
    domain = str(len(domain))
    return '{}@{}'.format(userpart, domain)
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


class UserViewSet(AnonReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

#     def get_serializer_class(self):
#         if self.request.user.is_authenticated:
#             return UserSerializer
#         return ObfuscatedUserSerializer
