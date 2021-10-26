from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.auth.models import User
from easydmp.lib.api.serializers import SelfHyperlinkedModelSerializer


class ObfuscatedUserSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'self',
        ]


class UserSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'self',
            'username',
            'email',
        ]


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.request.user.is_authenticated:
            return UserSerializer
        return ObfuscatedUserSerializer
