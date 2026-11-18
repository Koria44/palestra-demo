"""
Formularios del Modulo Coordinador Deportivo (Seccion 4.2):
- FormularioDisciplina: alta y edicion de disciplinas deportivas con validacion de cupo y horario.
- FormularioEntrenador: alta y edicion de entrenadores, asignacion multiple a disciplinas y modo de activacion de cuenta.
- FormularioEstudiante: alta y edicion de estudiantes con validacion de RUT chileno (modulo 11) y cifrado en reposo.
- FormularioInscripcion: inscripcion de estudiante en disciplina validando cupo disponible, estado activo y duplicados.
"""
from typing import Any
from django import forms
from apps.cuentas.campos import calcular_indice_ciego_rut
from apps.cuentas.formularios import CLASES_INPUT_PALESTRA
from apps.cuentas.models import Usuario
from apps.cuentas.validadores import validar_rut_chileno
from .models import Disciplina, Inscripcion, PerfilEntrenador, PerfilEstudiante


CLASES_SELECT_PALESTRA = (
    "form-select w-full rounded border border-palestra-borde bg-white px-3 py-2 "
    "text-palestra-texto focus:border-palestra-primario-500 focus:outline-none"
)


class FormularioDisciplina(forms.ModelForm):
    """Formulario para crear y editar disciplinas deportivas."""

    class Meta:
        model = Disciplina
        fields = [
            "nombre",
            "descripcion",
            "cupo_maximo",
            "dia",
            "hora_inicio",
            "hora_termino",
            "lugar",
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Ej.: Fútbol Varones y Damas"}
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": CLASES_INPUT_PALESTRA,
                    "rows": 3,
                    "placeholder": "Descripción técnica y objetivos de la disciplina",
                }
            ),
            "cupo_maximo": forms.NumberInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "min": 1, "max": 200}
            ),
            "dia": forms.Select(attrs={"class": CLASES_SELECT_PALESTRA}),
            "hora_inicio": forms.TimeInput(
                format="%H:%M",
                attrs={"class": CLASES_INPUT_PALESTRA, "type": "time"},
            ),
            "hora_termino": forms.TimeInput(
                format="%H:%M",
                attrs={"class": CLASES_INPUT_PALESTRA, "type": "time"},
            ),
            "lugar": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Ej.: Gimnasio Polideportivo A"}
            ),
            "activo": forms.CheckboxInput(attrs={"class": "w-4 h-4"}),
        }


class FormularioEntrenador(forms.ModelForm):
    """
    Formulario para crear o editar un PerfilEntrenador junto con su cuenta Usuario
    y su asignacion a una o varias disciplinas deportivas.
    """

    MODE_ENLACE = "enlace_activacion"
    MODE_TEMPORAL = "contrasena_temporal"

    OPCIONES_MODO_CUENTA = [
        (
            MODE_ENLACE,
            "Enviar enlace de activación de un solo uso por correo (Recomendado: el Coordinador no conoce la contraseña)",
        ),
        (
            MODE_TEMPORAL,
            "Generar contraseña temporal segura (16 caracteres, se muestra una sola vez y exige cambio en el primer ingreso)",
        ),
    ]

    correo = forms.EmailField(
        label="Correo institucional",
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "entrenador@institucion.cl"}
        ),
    )
    disciplinas_asignadas = forms.ModelMultipleChoiceField(
        label="Disciplinas deportivas asignadas",
        queryset=Disciplina.objects.filter(activo=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    modo_creacion_cuenta = forms.ChoiceField(
        label="Método de habilitación de acceso",
        choices=OPCIONES_MODO_CUENTA,
        initial=MODE_ENLACE,
        required=False,
        widget=forms.RadioSelect(),
    )

    class Meta:
        model = PerfilEntrenador
        fields = ["rut", "nombres", "apellidos", "especialidad", "telefono", "activo"]
        widgets = {
            "rut": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Ej.: 14.567.890-0"}
            ),
            "nombres": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Nombres del entrenador"}
            ),
            "apellidos": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Apellidos del entrenador"}
            ),
            "especialidad": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Ej.: Atletismo y Acondicionamiento"}
            ),
            "telefono": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "+56 9 1234 5678 (opcional)"}
            ),
            "activo": forms.CheckboxInput(attrs={"class": "w-4 h-4"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance._state.adding and self.instance.usuario_id:
            self.fields["correo"].initial = self.instance.usuario.email
            self.fields["rut"].initial = self.instance.rut_formateado
            self.fields["disciplinas_asignadas"].initial = self.instance.disciplinas.all()

    def clean_rut(self) -> str:
        rut_limpio = validar_rut_chileno(self.cleaned_data.get("rut", ""))
        indice = calcular_indice_ciego_rut(rut_limpio)
        qs = PerfilEntrenador.objects.filter(rut_indice_ciego=indice)
        if self.instance and not self.instance._state.adding:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un entrenador registrado con este RUT.")
        return rut_limpio

    def clean_correo(self) -> str:
        correo = self.cleaned_data.get("correo", "").strip().lower()
        qs = Usuario.objects.filter(email__iexact=correo)
        if self.instance and not self.instance._state.adding and self.instance.usuario_id:
            qs = qs.exclude(pk=self.instance.usuario_id)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe una cuenta de usuario registrada con este correo institucional."
            )
        return correo


class FormularioEstudiante(forms.ModelForm):
    """
    Formulario para crear o editar un PerfilEstudiante junto con su cuenta Usuario,
    cifrando RUT y telefono en reposo.
    """

    MODE_ENLACE = "enlace_activacion"
    MODE_TEMPORAL = "contrasena_temporal"

    OPCIONES_MODO_CUENTA = FormularioEntrenador.OPCIONES_MODO_CUENTA

    correo = forms.EmailField(
        label="Correo institucional",
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "estudiante@institucion.cl"}
        ),
    )
    modo_creacion_cuenta = forms.ChoiceField(
        label="Método de habilitación de acceso",
        choices=OPCIONES_MODO_CUENTA,
        initial=MODE_ENLACE,
        required=False,
        widget=forms.RadioSelect(),
    )

    class Meta:
        model = PerfilEstudiante
        fields = [
            "rut",
            "nombres",
            "apellidos",
            "curso_o_carrera",
            "telefono",
            "activo",
        ]
        widgets = {
            "rut": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Ej.: 18.123.456-3"}
            ),
            "nombres": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Nombres del estudiante"}
            ),
            "apellidos": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Apellidos del estudiante"}
            ),
            "curso_o_carrera": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "Ej.: Ingeniería en Informática"}
            ),
            "telefono": forms.TextInput(
                attrs={"class": CLASES_INPUT_PALESTRA, "placeholder": "+56 9 8765 4321 (opcional)"}
            ),
            "activo": forms.CheckboxInput(attrs={"class": "w-4 h-4"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance._state.adding and self.instance.usuario_id:
            self.fields["correo"].initial = self.instance.usuario.email
            self.fields["rut"].initial = self.instance.rut_formateado

    def clean_rut(self) -> str:
        rut_limpio = validar_rut_chileno(self.cleaned_data.get("rut", ""))
        indice = calcular_indice_ciego_rut(rut_limpio)
        qs = PerfilEstudiante.objects.filter(rut_indice_ciego=indice)
        if self.instance and not self.instance._state.adding:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un estudiante registrado con este RUT.")
        return rut_limpio

    def clean_correo(self) -> str:
        correo = self.cleaned_data.get("correo", "").strip().lower()
        qs = Usuario.objects.filter(email__iexact=correo)
        if self.instance and not self.instance._state.adding and self.instance.usuario_id:
            qs = qs.exclude(pk=self.instance.usuario_id)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe una cuenta de usuario registrada con este correo institucional."
            )
        return correo


class FormularioInscripcion(forms.ModelForm):
    """
    Formulario para inscribir a un estudiante activo en una disciplina activa,
    verificando disponibilidad de cupos y ausencia de inscripcion activa duplicada.
    """

    class Meta:
        model = Inscripcion
        fields = ["estudiante", "disciplina"]
        widgets = {
            "estudiante": forms.Select(attrs={"class": CLASES_SELECT_PALESTRA}),
            "disciplina": forms.Select(attrs={"class": CLASES_SELECT_PALESTRA}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = PerfilEstudiante.objects.filter(
            activo=True
        ).order_by("apellidos", "nombres")
        self.fields["disciplina"].queryset = Disciplina.objects.filter(
            activo=True
        ).order_by("nombre")

    def clean(self) -> dict[str, Any]:
        datos = super().clean()
        estudiante: PerfilEstudiante | None = datos.get("estudiante")
        disciplina: Disciplina | None = datos.get("disciplina")

        if estudiante and not estudiante.activo:
            raise forms.ValidationError(
                "No es posible inscribir a un estudiante que se encuentra inactivo."
            )
        if disciplina and not disciplina.activo:
            raise forms.ValidationError(
                "No es posible inscribir en una disciplina que se encuentra inactiva."
            )

        if estudiante and disciplina:
            ya_inscrito = Inscripcion.objects.filter(
                estudiante=estudiante,
                disciplina=disciplina,
                estado=Inscripcion.ESTADO_ACTIVA,
            ).exists()
            if ya_inscrito:
                raise forms.ValidationError(
                    "El estudiante seleccionado ya posee una inscripción activa en esta disciplina."
                )

            if disciplina.cupos_disponibles <= 0:
                raise forms.ValidationError(
                    f"La disciplina «{disciplina.nombre}» ha alcanzado su cupo máximo ({disciplina.cupo_maximo} estudiantes)."
                )
        return datos
