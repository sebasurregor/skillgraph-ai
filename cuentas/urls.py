from django.urls import path

from cuentas import views

app_name = "cuentas"

urlpatterns = [
    path("ingresar/", views.ingresar, name="ingresar"),
    path("ingresar/clave/", views.ingresar_clave, name="ingresar_clave"),
    path("registro/", views.registro, name="registro"),
    path("salir/", views.salir, name="salir"),
    path("inicio/", views.inicio, name="inicio"),
]
