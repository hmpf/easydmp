from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers


from easydmp.auth.models import User


class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='user-detail',
        lookup_field='pk'
    )

    class Meta:
        model = User
        fields = [
            'url',
            'username',
            'email',
        ]


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
