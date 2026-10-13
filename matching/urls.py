from django.urls import path

from matching import api

app_name = "matching"

urlpatterns = [
    path("candidatos-potenciales/", api.CandidatosPotencialesAPI.as_view(),
         name="candidatos_potenciales"),
    path("explicacion/<int:pk>/", api.ExplicacionAPI.as_view(), name="explicacion"),
]
