from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.safestring import mark_safe

from .models import Medewerker

# Wat Django afkeurt, in gewone taal. Deze vier punten horen bij de
# validators in config/settings.py (AUTH_PASSWORD_VALIDATORS); verandert daar
# iets, verander het hier ook. Ze staan bij het invulveld zelf, want een eis
# die je pas leest nadat je hem overtreedt is geen hulp.
WACHTWOORD_EISEN = mark_safe(
    "<ul class='eisen'>"
    "<li>Minstens 8 tekens</li>"
    "<li>Niet alleen cijfers</li>"
    "<li>Geen veelgebruikt wachtwoord, zoals <em>welkom123</em> of <em>wachtwoord</em></li>"
    "<li>Niet te veel lijken op de naam of gebruikersnaam</li>"
    "</ul>"
)


class MedewerkerForm(forms.ModelForm):
    """Een medewerker aanmaken of bijwerken. Alleen de eigenaar komt hier.

    Bewust weinig velden: alles wat met rechten en systeembeheer te maken
    heeft blijft in het Django-beheerscherm. Hier staat wat Maarten over
    zijn mensen moet kunnen vastleggen.
    """

    class Meta:
        model = Medewerker
        fields = [
            "first_name", "last_name", "username", "functie", "rol",
            "telefoon", "email", "adres", "postcode", "woonplaats",
            "noodcontact_naam", "noodcontact_relatie", "noodcontact_telefoon",
            "rijbewijs", "aanhanger",
            "kleur", "in_dienst_sinds",
        ]
        widgets = {
            # format="%Y-%m-%d" is verplicht bij type="date": zonder dat rendert
            # Django een bestaande datum in het Nederlandse formaat en toont de
            # browser een leeg veld.
            "in_dienst_sinds": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "kleur": forms.TextInput(attrs={"type": "color"}),
            # inputmode/type zorgen dat een telefoon meteen het juiste
            # toetsenbord opent
            "telefoon": forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "mobile tel"}),
            "noodcontact_telefoon": forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}),
            "email": forms.EmailInput(attrs={"inputmode": "email", "autocomplete": "email"}),
            "postcode": forms.TextInput(attrs={"autocomplete": "postal-code"}),
        }
        labels = {
            "first_name": "Voornaam",
            "last_name": "Achternaam",
            "username": "Gebruikersnaam",
            "functie": "Functie",
            "rol": "Rol",
            "telefoon": "Mobiel nummer",
            "email": "E-mailadres",
            "adres": "Straat en huisnummer",
            "postcode": "Postcode",
            "woonplaats": "Woonplaats",
            "noodcontact_naam": "Naam",
            "noodcontact_relatie": "Relatie",
            "noodcontact_telefoon": "Telefoon",
            "rijbewijs": "Rijbewijs",
            "aanhanger": "Mag met een zware aanhanger (BE)",
            "kleur": "Kleur in het planbord",
            "in_dienst_sinds": "In dienst sinds",
        }
        # Alleen bij de relatie helpt een voorbeeld; de rest spreekt voor zich.
        help_texts = {veld: "" for veld in fields if veld != "noodcontact_relatie"}

    # Kopjes boven de velden, zodat het geen lange rij invulvakken wordt.
    GROEPEN = [
        ("", ["first_name", "last_name", "username", "functie", "rol"]),
        ("Contact", ["telefoon", "email", "adres", "postcode", "woonplaats"]),
        ("Bij nood bellen", ["noodcontact_naam", "noodcontact_relatie", "noodcontact_telefoon"]),
        ("Rijbewijs", ["rijbewijs", "aanhanger"]),
        ("In de app", ["kleur", "in_dienst_sinds"]),
    ]

    def groepen(self):
        """(kopje, velden) voor de template. Velden die dit formulier niet
        heeft — zoals het wachtwoord bij een nieuwe medewerker — komen er
        onderaan achteraan."""
        gebruikt = set()
        for kop, namen in self.GROEPEN:
            velden = [self[naam] for naam in namen if naam in self.fields]
            gebruikt.update(naam for naam in namen if naam in self.fields)
            if velden:
                yield kop, velden
        rest = [veld for veld in self if veld.name not in gebruikt]
        if rest:
            yield "Wachtwoord", rest

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True

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
        help_text=WACHTWOORD_EISEN,
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
        help_text=WACHTWOORD_EISEN,
    )

    def clean_wachtwoord(self):
        wachtwoord = self.cleaned_data["wachtwoord"]
        validate_password(wachtwoord)
        return wachtwoord
