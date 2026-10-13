from django.urls import path

from postulaciones import views

app_name = "postulaciones"

urlpatterns = [
    path("", views.mis_postulaciones, name="mias"),
    path("postular/<int:vacante_id>/", views.postular, name="postular"),
    path("vacante/<int:vacante_id>/", views.de_vacante, name="de_vacante"),
    path("<int:pk>/estado/", views.cambiar_estado, name="cambiar_estado"),
    path("<int:pk>/hoja-de-vida/", views.hoja_de_vida, name="hoja_de_vida"),
]
