from django.contrib import admin
from django.urls import include, path

from skillgraph.views import portada

urlpatterns = [
    path("", portada, name="raiz"),
    path("cuentas/", include("cuentas.urls")),
    path("vacantes/", include("vacantes.urls")),
    path("perfil/", include("perfiles.urls")),
    path("recomendaciones/", include("matching.urls_web")),
    path("api/matching/", include("matching.urls")),
    path("admin/", admin.site.urls),
]
