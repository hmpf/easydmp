from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.auth.models import User


def truncate_email(email):
    userpart, domain = email.rsplit('@', 1)
    domain = str(len(domain))
    return '{}@{}'.format(userpart, domain)


class UserSerializer(serializers.HyperlinkedModelSerializer):
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


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
