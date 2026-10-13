from django.urls import path

from matching import views

app_name = "recomendaciones"

urlpatterns = [
    path("", views.recomendaciones, name="lista"),
]
