from rest_framework import serializers

from vacantes.models import Habilidad


class RequisitoSerializer(serializers.Serializer):
    habilidad = serializers.PrimaryKeyRelatedField(queryset=Habilidad.objects.all())
    nivel_minimo = serializers.IntegerField(min_value=1, max_value=5, default=3)
    obligatoria = serializers.BooleanField(default=False)


class PrevisualizacionSerializer(serializers.Serializer):
    requisitos = RequisitoSerializer(many=True, allow_empty=True)
