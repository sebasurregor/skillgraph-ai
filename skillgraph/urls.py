from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="cuentas:inicio"), name="raiz"),
    path("cuentas/", include("cuentas.urls")),
    path("vacantes/", include("vacantes.urls")),
    path("api/matching/", include("matching.urls")),
    path("admin/", admin.site.urls),
]
