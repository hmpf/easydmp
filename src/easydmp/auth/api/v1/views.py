from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers

from easydmp.lib.api.viewsets import AnonReadOnlyModelViewSet
from easydmp.auth.models import User


class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='user-detail',
        lookup_field='pk'
    )

    class Meta:
        model = User
        fields = [
            'id',
            'url',
        ]


@extend_schema_view(
    list=extend_schema(deprecated=True),
    retrieve=extend_schema(deprecated=True),
)
class UserViewSet(AnonReadOnlyModelViewSet):
    "Deprecated. Use the endpoint in V2 instead: /api/v2/users/"
    queryset = User.objects.none()
    serializer_class = UserSerializer
