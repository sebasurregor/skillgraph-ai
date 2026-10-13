from django import forms
from django.core.validators import RegexValidator

from perfiles import services
from skillgraph.formularios import FormularioValidadoMixin
from vacantes.models import Habilidad

NIVELES = range(1, 6)
# Campo del CV → campo del formulario.
CAMPO_DE = {"nombre": "nombre_completo", "correo": "correo", "telefono": "telefono",
            "experiencia": "experiencia", "educacion": "educacion",
            "habilidades": "habilidades"}
AYUDA_SIN_EXTRAER = "No pudimos leer este dato en su hoja de vida. Escríbalo aquí."


class CargaCVForm(FormularioValidadoMixin, forms.Form):
    archivo = forms.FileField(
        label="Hoja de vida",
        widget=forms.ClearableFileInput(attrs={
            "accept": ".pdf,.docx,application/pdf,"
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
        error_messages={"required": "Seleccione su hoja de vida en PDF o Word (.docx).",
                        "empty": "El archivo está vacío. Seleccione otro."},
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        try:
            services.validar_archivo_cv(archivo)
        except services.ArchivoRechazado as exc:
            raise forms.ValidationError(str(exc))
        return archivo


class PerfilForm(FormularioValidadoMixin, forms.Form):
    """Confirmación del perfil: precargado con lo extraído del CV o llenado a mano."""

    nombre_completo = forms.CharField(label="Nombre completo", max_length=150)
    correo = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(
        label="Teléfono",
        validators=[RegexValidator(
            r"^\d{7,10}$",
            "El teléfono debe tener entre 7 y 10 dígitos, sin espacios ni guiones.")],
        widget=forms.TextInput(attrs={"inputmode": "numeric"}))
    experiencia = forms.CharField(
        label="Experiencia", required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Si es su primer empleo puede dejarlo en blanco.")
    educacion = forms.CharField(label="Educación", required=False,
                                widget=forms.Textarea(attrs={"rows": 3}))
    habilidades = forms.ModelMultipleChoiceField(
        label="Habilidades", queryset=Habilidad.objects.all(),
        error_messages={"required": "Marque al menos una habilidad para calcular su ajuste."})

    def __init__(self, *args, faltantes=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.sin_extraer = {CAMPO_DE[c] for c in faltantes if c in CAMPO_DE}
        if not self.is_bound:
            for nombre in self.sin_extraer - {"habilidades"}:
                campo = self.fields[nombre]
                campo.widget.attrs["class"] += " sin-extraer"
                campo.help_text = AYUDA_SIN_EXTRAER

    def clean(self):
        datos = super().clean()
        datos["niveles"] = {
            h.nombre: self._nivel(self.data.get(f"nivel_{h.pk}"))
            for h in datos.get("habilidades", [])}
        return datos

    @staticmethod
    def _nivel(valor):
        try:
            return max(1, min(5, int(valor)))
        except (TypeError, ValueError):
            return 3

    # ---- Datos para pintar el selector de habilidades --------------------------

    def _marcadas(self):
        """{pk de habilidad: nivel} según lo enviado o lo precargado."""
        if self.is_bound:
            return {int(pk): self._nivel(self.data.get(f"nivel_{pk}"))
                    for pk in self.data.getlist("habilidades") if pk.isdigit()}
        niveles = self.initial.get("niveles", {})
        return {h.pk: niveles[h.nombre] for h in Habilidad.objects.filter(nombre__in=niveles)}

    def grupos_habilidades(self):
        """[(título, [{habilidad, marcada, nivel}], abierto)]: primero las ya marcadas."""
        marcadas = self._marcadas()
        grupos = []
        propias = [{"habilidad": h, "marcada": True, "nivel": marcadas[h.pk]}
                   for h in Habilidad.objects.filter(pk__in=marcadas)]
        if propias:
            grupos.append(("Sus habilidades", propias, True))
        for titulo, habilidades in services.catalogo_agrupado():
            resto = [{"habilidad": h, "marcada": False, "nivel": 3}
                     for h in habilidades if h.pk not in marcadas]
            if resto:
                grupos.append((titulo, resto, False))
        return grupos

    @property
    def habilidades_sin_extraer(self):
        return not self.is_bound and "habilidades" in self.sin_extraer


class PreferenciasForm(FormularioValidadoMixin, forms.Form):
    """Preferencias laborales (HU-RF-004). Todo es opcional; el rango debe ser coherente."""

    cargos = forms.MultipleChoiceField(
        label="Cargos que le interesan", required=False, widget=forms.CheckboxSelectMultiple)
    ubicaciones = forms.MultipleChoiceField(
        label="Dónde quiere trabajar", required=False, widget=forms.CheckboxSelectMultiple)
    tipos_contrato = forms.MultipleChoiceField(
        label="Tipos de contrato", required=False, widget=forms.CheckboxSelectMultiple)
    salario_min = forms.IntegerField(
        label="Salario mensual esperado: desde", required=False, min_value=0,
        widget=forms.NumberInput(attrs={"placeholder": "1500000", "step": 50000, "min": 0}))
    salario_max = forms.IntegerField(
        label="Hasta", required=False, min_value=0,
        widget=forms.NumberInput(attrs={"placeholder": "2500000", "step": 50000, "min": 0}))
    por_aprender = forms.ModelMultipleChoiceField(
        label="Habilidades que le gustaría aprender", required=False,
        queryset=Habilidad.objects.all())

    def __init__(self, *args, opciones, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("cargos", "ubicaciones", "tipos_contrato"):
            self.fields[campo].choices = [(o, o) for o in opciones[campo]]

    def clean(self):
        datos = super().clean()
        minimo, maximo = datos.get("salario_min"), datos.get("salario_max")
        if minimo and maximo and minimo > maximo:
            self.add_error("salario_max",
                           "El salario máximo no puede ser menor que el mínimo.")
        return datos

    def grupos_por_aprender(self):
        """[(título, [{habilidad, marcada}])] para pintar la lista por áreas."""
        if self.is_bound:
            marcadas = {int(pk) for pk in self.data.getlist("por_aprender") if pk.isdigit()}
        else:
            marcadas = {h.pk for h in self.initial.get("por_aprender", [])}
        return [(titulo, [{"habilidad": h, "marcada": h.pk in marcadas} for h in habilidades])
                for titulo, habilidades in services.catalogo_agrupado()]
