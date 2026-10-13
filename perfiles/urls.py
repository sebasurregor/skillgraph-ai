from django.urls import path

from perfiles import views

app_name = "perfiles"

urlpatterns = [
    path("", views.mi_perfil, name="mi_perfil"),
    path("hoja-de-vida/", views.cargar_cv, name="cargar_cv"),
    path("preferencias/", views.preferencias, name="preferencias"),
    path("confirmar/", views.confirmar, name="confirmar_manual"),
    path("confirmar/<int:pk>/", views.confirmar, name="confirmar_cv"),
]
