"""Servicios JSON de matching que consume la interfaz."""
from rest_framework.response import Response
from rest_framework.views import APIView

from cuentas.permisos import EsReclutador
from matching import services
from matching.serializers import PrevisualizacionSerializer


class CandidatosPotencialesAPI(APIView):
    """HU-RF-011: cuántos candidatos cumplirían los requisitos de una vacante."""

    permission_classes = [EsReclutador]

    def post(self, request):
        entrada = PrevisualizacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return Response(services.contar_candidatos_potenciales(
            entrada.validated_data["requisitos"]))
