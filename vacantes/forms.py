from decimal import Decimal

from django import forms

from skillgraph.formularios import FormularioValidadoMixin
from vacantes import services
from vacantes.models import Habilidad, Vacante

NIVELES = [(n, str(n)) for n in range(1, 6)]


class VacanteForm(FormularioValidadoMixin, forms.ModelForm):
    """Datos generales de la vacante. Un borrador solo exige el título."""

    class Meta:
        model = Vacante
        fields = ["titulo", "empresa", "cargo", "area", "ciudad", "modalidad", "jornada",
                  "salario", "descripcion"]
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Auxiliar de bodega"}),
            "cargo": forms.TextInput(attrs={"placeholder": "Auxiliar logístico"}),
            "ciudad": forms.TextInput(attrs={"placeholder": "Medellín"}),
            "salario": forms.NumberInput(attrs={"placeholder": "1600000", "min": 0,
                                                "step": 50000}),
            "descripcion": forms.Textarea(attrs={
                "rows": 3, "placeholder": "Qué hará la persona, horario y condiciones."}),
        }

    def __init__(self, *args, publicar=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].empty_label = "Seleccione…"
        for nombre, campo in self.fields.items():
            campo.required = nombre == "titulo" or (
                publicar and nombre in services.CAMPOS_PARA_PUBLICAR)
            if campo.required:
                campo.widget.attrs["data-obligatorio"] = "1"
            else:
                campo.widget.attrs.pop("data-obligatorio", None)


class RequisitoForm(FormularioValidadoMixin, forms.Form):
    """Una habilidad ponderada de la vacante."""

    habilidad = forms.ModelChoiceField(queryset=Habilidad.objects.all(),
                                       empty_label="Seleccione…")
    peso = forms.DecimalField(
        min_value=Decimal("0.01"), max_value=Decimal("1.00"), decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "max": "1",
                                        "placeholder": "0.25"}))
    nivel_minimo = forms.TypedChoiceField(label="Nivel mínimo", choices=NIVELES, coerce=int,
                                          initial=3)
    obligatoria = forms.BooleanField(required=False)


class BaseRequisitoFormSet(forms.BaseFormSet):
    def __init__(self, *args, publicar=True, **kwargs):
        self.publicar = publicar
        super().__init__(*args, **kwargs)

    def requisitos(self):
        """Filas válidas y no eliminadas, como datos planos para los servicios."""
        return [
            {k: f.cleaned_data[k] for k in ("habilidad", "peso", "nivel_minimo", "obligatoria")}
            for f in self.forms
            if f.cleaned_data.get("habilidad") and not f.cleaned_data.get("DELETE")
        ]

    def clean(self):
        if any(self.errors):
            return
        filas = self.requisitos()
        nombres = [r["habilidad"].nombre for r in filas]
        repetidas = sorted({n for n in nombres if nombres.count(n) > 1})
        if repetidas:
            self._resaltar("habilidad")
            raise forms.ValidationError(
                "Cada habilidad solo puede aparecer una vez: " + ", ".join(repetidas) + ".")
        if self.publicar:
            errores = services.errores_de_requisitos(filas)
            if errores:
                self._resaltar("peso")
                raise forms.ValidationError(errores)

    def _resaltar(self, campo):
        for form in self.forms:
            attrs = form.fields[campo].widget.attrs
            attrs["class"] = (attrs.get("class", "") + " is-invalid").strip()
            attrs["aria-invalid"] = "true"
            attrs["autofocus"] = True

    @property
    def mensajes(self):
        return list(self.non_form_errors())


RequisitoFormSet = forms.formset_factory(RequisitoForm, formset=BaseRequisitoFormSet,
                                         extra=0, can_delete=True)
