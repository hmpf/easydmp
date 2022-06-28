from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


__all__ = [
    'SelfHyperlinkedRelatedField',
    'SelfHyperlinkedSlugRelatedField',
    'SelfModelSerializer',
    'SelfHyperlinkedModelSerializer',
    'SelfHyperlinkedSlugModelSerializer',
    'URLSerializer',
]


class HyperlinkedIDSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    self = serializers.URLField()


class HyperlinkedSlugSerializer(serializers.Serializer):
    slug = serializers.CharField()
    self = serializers.URLField()


@extend_schema_field(HyperlinkedIDSerializer())
class SelfHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        return {
            'id': instance.pk,
            'self': ret,
        }


@extend_schema_field(HyperlinkedSlugSerializer())
class SelfHyperlinkedSlugRelatedField(serializers.HyperlinkedRelatedField):

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        return {
            'slug': instance.pk,
            'self': ret,
        }

class SelfModelSerializer(serializers.ModelSerializer):
    url_field_name = 'self'


class SelfHyperlinkedModelSerializer(serializers.HyperlinkedModelSerializer):
    serializer_related_field = SelfHyperlinkedRelatedField
    url_field_name = 'self'


class SelfHyperlinkedSlugModelSerializer(serializers.HyperlinkedModelSerializer):
    serializer_related_field = SelfHyperlinkedSlugRelatedField
    url_field_name = 'self'


class URLSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=255, required=True)
