from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _

from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers
from rest_framework import status

from rest_framework_jwt.compat import set_cookie_with_token
from rest_framework_jwt.serializers import ImpersonateAuthTokenSerializer
from rest_framework_jwt.settings import api_settings as jwt_api_settings

from easydmp.auth.models import User
from easydmp.auth.api.permissions import HasSuperpowers
from easydmp.eventlog.utils import log_event
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


class ImpersonateJSONWebTokenView(GenericAPIView):
    permission_classes = [HasSuperpowers]
    serializer_class = ImpersonateAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data.get('token')
        response = Response({'token': token}, status=status.HTTP_201_CREATED)

        if jwt_api_settings.JWT_IMPERSONATION_COOKIE:
            set_cookie_with_token(
                response,
                jwt_api_settings.JWT_IMPERSONATION_COOKIE,
                token)

        impersonator = self.request.user
        impersonatee = serializer.validated_data.get('user')
        template = '{timestamp} {actor} impersonated {target}'
        log_event(impersonator, 'impersonate', target=impersonatee, template=template)

        return response
