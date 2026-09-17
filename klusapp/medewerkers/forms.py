from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Medewerker


class MedewerkerForm(forms.ModelForm):
    """Een medewerker aanmaken of bijwerken. Alleen de eigenaar komt hier.

    Bewust weinig velden: alles wat met rechten en systeembeheer te maken
    heeft blijft in het Django-beheerscherm. Hier staat wat Maarten over
    zijn mensen moet kunnen vastleggen.
    """

    class Meta:
        model = Medewerker
        fields = ["first_name", "last_name", "username", "functie", "telefoon", "rol", "kleur", "in_dienst_sinds"]
        widgets = {
            # format="%Y-%m-%d" is verplicht bij type="date": zonder dat rendert
            # Django een bestaande datum in het Nederlandse formaat en toont de
            # browser een leeg veld.
            "in_dienst_sinds": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "kleur": forms.TextInput(attrs={"type": "color"}),
        }
        labels = {
            "first_name": "Voornaam",
            "last_name": "Achternaam",
            "username": "Gebruikersnaam",
            "functie": "Functie",
            "telefoon": "Telefoon",
            "rol": "Rol",
            "kleur": "Kleur in het planbord",
            "in_dienst_sinds": "In dienst sinds",
        }
        help_texts = {veld: "" for veld in fields}

    def __init__(self, *args, door=None, **kwargs):
        """`door` is degene die het formulier invult; die bepaalt welke rollen
        hij mag uitdelen."""
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True

        # Een eigenaar mag geen systeembeheerder maken — dat zou hem toegang
        # geven tot het Django-beheerscherm langs de achterdeur, via een
        # account dat hij zelf aanmaakt.
        if not (door and door.is_systeembeheerder):
            self.fields["rol"].choices = [
                (waarde, naam)
                for waarde, naam in Medewerker.Rol.choices
                if waarde != Medewerker.Rol.BEHEERDER
            ]

        # Een kleurkiezer kan niet leeg zijn; zonder beginwaarde toont de
        # browser zwart en lijkt er een kleur gekozen die er niet is.
        if not self.initial.get("kleur"):
            self.initial["kleur"] = "#5B8FA8"


class NieuweMedewerkerForm(MedewerkerForm):
    """Hetzelfde formulier, met een eerste wachtwoord erbij.

    Dat wachtwoord is tijdelijk: je geeft het door en de medewerker zet er
    daarna zelf een ander voor in de plaats.
    """

    wachtwoord = forms.CharField(
        label="Tijdelijk wachtwoord",
        widget=forms.PasswordInput(render_value=True),
        strip=False,
    )

    def clean_wachtwoord(self):
        wachtwoord = self.cleaned_data["wachtwoord"]
        validate_password(wachtwoord)
        return wachtwoord

    def save(self, commit=True):
        medewerker = super().save(commit=False)
        medewerker.set_password(self.cleaned_data["wachtwoord"])
        if commit:
            medewerker.save()
        return medewerker


class WachtwoordForm(forms.Form):
    """Een nieuw wachtwoord zetten voor iemand anders. De eigenaar hoeft het
    oude niet te weten — die kent het immers niet."""

    wachtwoord = forms.CharField(
        label="Nieuw wachtwoord",
        widget=forms.PasswordInput(render_value=True),
        strip=False,
    )

    def clean_wachtwoord(self):
        wachtwoord = self.cleaned_data["wachtwoord"]
        validate_password(wachtwoord)
        return wachtwoord
