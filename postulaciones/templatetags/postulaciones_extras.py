from django import template

from postulaciones import services

register = template.Library()

_CLAVE = "vacantes_postuladas"


@register.inclusion_tag("postulaciones/_boton_postular.html", takes_context=True)
def boton_postular(context, vacante):
    """Botón «Postularme» de una tarjeta; deshabilitado si ya se postuló."""
    request = context["request"]
    if _CLAVE not in context.render_context:      # una sola consulta por página
        context.render_context[_CLAVE] = services.vacantes_postuladas(request.user)
    return {"vacante": vacante, "postulada": vacante.pk in context.render_context[_CLAVE],
            "siguiente": request.get_full_path(), "csrf_token": context.get("csrf_token")}


@register.filter
def clase_estado(estado):
    return {"preseleccionada": "tag-ok", "descartada": "tag-miss"}.get(estado, "tag-neutro")
