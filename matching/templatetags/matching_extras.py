"""Ayudas de presentación para pintar el match (anillo, barras y subgrafo)."""
from django import template

register = template.Library()

PERIMETRO_ANILLO = 163      # 2·π·26, el radio del anillo de las tarjetas


@register.filter
def color_ajuste(pct):
    if pct >= 75:
        return "var(--green)"
    return "var(--sky)" if pct >= 50 else "var(--line-strong)"


@register.filter
def trazo_anillo(pct):
    return round(pct / 100 * PERIMETRO_ANILLO)


@register.filter
def por_ciento(valor):
    """0.6 → 60"""
    return round(float(valor) * 100)


@register.filter
def dos_decimales(valor):
    """Siempre con punto decimal, como los pesos del grafo: 0.25"""
    return f"{float(valor):.2f}"


@register.inclusion_tag("matching/_subgrafo.html")
def subgrafo(match, sigla, sujeto="Usted"):
    """Subgrafo Candidato → habilidades → Vacante: verdes las cubiertas, rojas las faltantes."""
    items = [{"nombre": c["nombre"], "ok": True} for c in match.cubiertas] + \
            [{"nombre": f["nombre"], "ok": False} for f in match.faltantes]
    alto = max(150, len(items) * 34 + 30)
    for i, item in enumerate(items):
        item["y"] = 28 + i * 34
        item["y_rect"] = item["y"] - 13
        item["y_texto"] = item["y"] + 4
        nombre = item["nombre"]
        item["rotulo"] = nombre if len(nombre) <= 17 else nombre[:16] + "…"
    centro = alto / 2
    return {"items": items, "alto": alto, "cy": centro, "sigla": sigla, "sujeto": sujeto,
            "cy_arriba": centro - 1, "cy_abajo": centro + 11,
            "y_vacante": centro - 24, "y_sigla": centro - 3}


@register.filter
def clase_nivel(habilidad):
    """Color de una habilidad cubierta según qué tan lejos está del nivel exigido.

    Verde si lo alcanza; naranja si no, más claro cuanto más cerca está.
    """
    brecha = habilidad["nivel_min"] - habilidad["nivel"]
    return "tag-ok" if brecha <= 0 else f"tag-brecha brecha-{min(brecha, 4)}"
