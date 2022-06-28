from rest_framework import serializers

from easydmp.lib.api.serializers import SelfHyperlinkedModelSerializer
from easydmp.lib.api.serializers import SelfHyperlinkedSlugModelSerializer
from easydmp.rdadcs.models import RDADCSKey
from easydmp.rdadcs.models import RDADCSQuestionLink
from easydmp.rdadcs.models import RDADCSSectionLink


class RDADCSKeySerializer(SelfHyperlinkedSlugModelSerializer):
    input_type = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = RDADCSKey
        fields = ('slug', 'self', 'path', 'repeatable', 'optional', 'input_type')
        read_only_fields = fields


class RDADCSQuestionLinkSerializer(SelfHyperlinkedModelSerializer):
    class Meta:
        model = RDADCSQuestionLink
        fields = ('key', 'question')


class RDADCSSectionLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = RDADCSSectionLink
        fields = ('key', 'section')
