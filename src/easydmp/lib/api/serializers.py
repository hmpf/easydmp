from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


__all__ = [
    'SelfHyperlinkedRelatedField',
    'SelfModelSerializer',
    'SelfHyperlinkedModelSerializer',
    'URLSerializer',
]


class HyperlinkedIDSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    self = serializers.URLField()


@extend_schema_field(HyperlinkedIDSerializer())
class SelfHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        return {
            'id': instance.pk,
            'self': ret,
        }


class SelfModelSerializer(serializers.ModelSerializer):
    url_field_name = 'self'


class SelfHyperlinkedModelSerializer(serializers.HyperlinkedModelSerializer):
    serializer_related_field = SelfHyperlinkedRelatedField
    url_field_name = 'self'


class URLSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=255, required=True)
