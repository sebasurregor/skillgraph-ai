"""Servicios JSON de matching que consume la interfaz."""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from cuentas.permisos import EsCandidato, EsReclutador
from matching import services
from matching.serializers import PrevisualizacionSerializer
from perfiles import services as perfiles


class CandidatosPotencialesAPI(APIView):
    """HU-RF-011: cuántos candidatos cumplirían los requisitos de una vacante."""

    permission_classes = [EsReclutador]

    def post(self, request):
        entrada = PrevisualizacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return Response(services.contar_candidatos_potenciales(
            entrada.validated_data["requisitos"]))


class ExplicacionAPI(APIView):
    """HU-RF-005: desglose del match del candidato en sesión con una vacante publicada."""

    permission_classes = [EsCandidato]

    def get(self, request, pk):
        vacante = get_object_or_404(services.vacantes_publicadas(), pk=pk)
        match, aviso = services.match_de(perfiles.perfil_de(request.user), vacante)
        return Response({"vacante": {"id": vacante.pk, "titulo": vacante.titulo,
                                     "empresa": vacante.empresa},
                         "pesos": services.pesos(), "aviso": aviso, **match.como_dict()})
