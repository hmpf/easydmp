from easydmp.lib.api.viewsets import AnonReadOnlyModelViewSet

from easydmp.rdadcs.models import RDADCSKey
from easydmp.rdadcs.models import RDADCSQuestionLink
from easydmp.rdadcs.models import RDADCSSectionLink
from . import serializers


class RDADCSKeyViewSet(AnonReadOnlyModelViewSet):
    serializer_class = serializers.RDADCSKeySerializer
    pagination_class = None
    queryset = RDADCSKey.objects.all()


class RDADCSQuestionLinkViewSet(AnonReadOnlyModelViewSet):
    serializer_class = serializers.RDADCSQuestionLinkSerializer
    queryset = RDADCSQuestionLink.objects.all()


class RDADCSSectionLinkViewSet(AnonReadOnlyModelViewSet):
    serializer_class = serializers.RDADCSSectionLinkSerializer
    queryset = RDADCSSectionLink.objects.all()
