from django.urls import path

from vacantes import views

app_name = "vacantes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.editar, name="nueva"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/publicar/", views.publicar, name="publicar"),
    path("<int:pk>/despublicar/", views.despublicar, name="despublicar"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar"),
]
