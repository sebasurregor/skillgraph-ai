from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator

from cuentas import services
from cuentas.models import Usuario
from skillgraph.formularios import FormularioValidadoMixin

CIUDADES = ["Medellín", "Bogotá", "Cali", "Barranquilla", "Bucaramanga", "Pereira", "Otra"]

ROLES = [
    (Usuario.Rol.CANDIDATO, "Busco empleo"),
    (Usuario.Rol.RECLUTADOR, "Publico vacantes"),
]


class CorreoForm(FormularioValidadoMixin, forms.Form):
    correo = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"placeholder": "nombre@correo.com",
                                       "autocomplete": "email"}),
        error_messages={"invalid": "Ese correo no tiene un formato válido. "
                                   "Revise que incluya @ y un dominio."},
    )

    def clean_correo(self):
        return services.normalizar_correo(self.cleaned_data["correo"])


class ClaveForm(FormularioValidadoMixin, forms.Form):
    clave = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••",
                                          "autocomplete": "current-password"}),
    )


class RegistroForm(FormularioValidadoMixin, forms.Form):
    rol = forms.ChoiceField(label="¿Para qué va a usar SkillGraph AI?", choices=ROLES,
                            initial=Usuario.Rol.CANDIDATO, widget=forms.RadioSelect)
    nombres = forms.CharField(label="Nombres", max_length=150,
                              widget=forms.TextInput(attrs={"placeholder": "Ana María"}))
    apellidos = forms.CharField(label="Apellidos", max_length=150,
                                widget=forms.TextInput(attrs={"placeholder": "Ríos Bedoya"}))
    correo = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(
        label="Teléfono",
        validators=[RegexValidator(
            r"^\d{7,10}$",
            "El teléfono debe tener entre 7 y 10 dígitos, sin espacios ni guiones.")],
        widget=forms.TextInput(attrs={"placeholder": "3001234567", "inputmode": "numeric"}),
    )
    ciudad = forms.ChoiceField(
        label="Ciudad", choices=[("", "Seleccione…")] + [(c, c) for c in CIUDADES])
    empresa = forms.CharField(
        label="Empresa", max_length=120, required=False,
        help_text="Obligatoria si va a publicar vacantes.")
    clave = forms.CharField(
        label="Contraseña", strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Mínimo 8 caracteres",
                                          "autocomplete": "new-password"}))
    clave2 = forms.CharField(
        label="Confirmar contraseña", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    acepta_datos = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales para fines de intermediación "
              "laboral, conforme a la Ley 1581 de 2012.")

    def clean_correo(self):
        correo = services.normalizar_correo(self.cleaned_data["correo"])
        if services.existe_cuenta(correo):
            raise forms.ValidationError("Ya existe una cuenta con ese correo. Inicie sesión.")
        return correo

    def clean_clave(self):
        clave = self.cleaned_data["clave"]
        validate_password(clave)
        return clave

    def clean(self):
        datos = super().clean()
        if datos.get("rol") == Usuario.Rol.RECLUTADOR and not (datos.get("empresa") or "").strip():
            self.add_error("empresa", "Indique la empresa para la que publica vacantes.")
        if datos.get("clave") and datos.get("clave2") and datos["clave"] != datos["clave2"]:
            self.add_error("clave2", "Las contraseñas no coinciden.")
        return datos
