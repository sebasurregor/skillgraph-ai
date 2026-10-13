"""Regla de validación común a todos los formularios del sistema.

Cuando hay campos obligatorios vacíos o inválidos se muestra el mensaje exigido,
se resaltan los campos inválidos y el foco va al primero de ellos.
"""
from django import forms

MSG_OBLIGATORIOS = "Favor ingresar información válida en los campos obligatorios"

_CLASE_POR_WIDGET = (
    (forms.Select, "select"),
    (forms.Textarea, "textarea"),
    ((forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple), ""),
)


def _clase_css(widget):
    for tipos, clase in _CLASE_POR_WIDGET:
        if isinstance(widget, tipos):
            return clase
    return "input"


class FormularioValidadoMixin:
    """Mezcla para `forms.Form` y `forms.ModelForm`."""

    # El navegador no bloquea el envío: la validación y el mensaje son los del sistema.
    use_required_attribute = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            clase = _clase_css(campo.widget)
            if clase:
                campo.widget.attrs.setdefault("class", clase)
            if campo.required:
                campo.widget.attrs["data-obligatorio"] = "1"

    def full_clean(self):
        super().full_clean()
        if self.is_bound:
            self.marcar_invalidos()

    def marcar_invalidos(self):
        """Resalta los campos con error y da el foco al primero.

        `full_clean` lo invoca solo; llámelo de nuevo si agrega errores después
        con `add_error` (por ejemplo, tras consultar un servicio).
        """
        primero = True
        for nombre, campo in self.fields.items():
            attrs = campo.widget.attrs
            attrs.pop("autofocus", None)
            if nombre not in self.errors:
                continue
            if "is-invalid" not in attrs.get("class", ""):
                attrs["class"] = (attrs.get("class", "") + " is-invalid").strip()
            attrs["aria-invalid"] = "true"
            if primero:
                attrs["autofocus"] = True
                primero = False

    @property
    def mensaje_error(self):
        """Mensaje único de la alerta; vacío si el formulario es válido."""
        return MSG_OBLIGATORIOS if self.is_bound and self.errors else ""


def un_solo_foco(*formularios):
    """En una página con varios formularios, deja el foco solo en el primer campo inválido."""
    encontrado = False
    for formulario in formularios:
        for campo in formulario.fields.values():
            attrs = campo.widget.attrs
            if "autofocus" not in attrs:
                continue
            if encontrado:
                del attrs["autofocus"]
            encontrado = True
