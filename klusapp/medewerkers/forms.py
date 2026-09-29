from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from django.utils.safestring import mark_safe

from . import profielfotos
from .models import RIJBEWIJS_GROEPEN, RIJBEWIJS_VOLGORDE, Medewerker


class ProfielfotoMixin:
    """Een geüploade pasfoto verkleind opslaan in plaats van het origineel.

    Zelfde behandeling als klusfoto's: rechtop, naar JPEG, EXIF eraf. Zonder
    dit belandt een foto van acht megabyte ongewijzigd op de server, inclusief
    de GPS-coördinaten van waar hij genomen is.
    """

    def clean_profielfoto(self):
        foto = self.cleaned_data.get("profielfoto")
        # Alleen een echte upload verwerken. Staat er al een foto, dan geeft
        # Django het bestaande bestand terug — dat heeft ook een .file, dus
        # daarop controleren betekent bij elke keer opslaan opnieuw verkleinen
        # en hernoemen.
        if not isinstance(foto, UploadedFile):
            return foto
        try:
            verkleind = profielfotos.verkleind(foto)
        except profielfotos.BestandNietLeesbaar as oorzaak:
            raise forms.ValidationError(str(oorzaak)) from oorzaak
        verkleind.name = "profielfoto.jpg"
        return verkleind

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


def beginkleur(formulier):
    """Een kleurkiezer kan niet leeg zijn; zonder beginwaarde toont de browser
    zwart. Wie nog nooit een kleur koos, heeft wél een kleur: die rekent de
    app uit voor zijn rondje (uren.kalender.medewerker_kleur_van). Die tonen
    we dan ook, en niet een vaste blauwe — anders staat er een andere kleur
    dan je ziet, en wordt je kleur bij de eerste keer opslaan ongemerkt
    blauw. Een nieuwe medewerker (nog geen pk) krijgt wel het vaste blauw."""
    from uren.kalender import medewerker_kleur_van

    if not formulier.initial.get("kleur"):
        persoon = formulier.instance
        formulier.initial["kleur"] = medewerker_kleur_van(persoon) if persoon.pk else "#5B8FA8"


class RijbewijzenWidget(forms.CheckboxSelectMultiple):
    """Vinkjes als pillen, per groep op een rij; zie
    medewerkers/templates/medewerkers/widgets/rijbewijzen.html."""

    template_name = "medewerkers/widgets/rijbewijzen.html"


class RijbewijzenMixin(forms.Form):
    """Rijbewijscategorieën: aanvinken wat je hebt, meerdere tegelijk."""

    rijbewijzen = forms.MultipleChoiceField(
        label="Categorieën",
        required=False,
        choices=[(groep, [(code, code) for code in codes]) for groep, codes in RIJBEWIJS_GROEPEN],
        widget=RijbewijzenWidget,
    )

    def clean_rijbewijzen(self):
        # altijd in de volgorde van het rijbewijs, hoe je ze ook aanvinkt
        gekozen = set(self.cleaned_data["rijbewijzen"])
        return [code for code in RIJBEWIJS_VOLGORDE if code in gekozen]


class MedewerkerForm(RijbewijzenMixin, ProfielfotoMixin, forms.ModelForm):
    """Een medewerker aanmaken of bijwerken. Alleen de eigenaar komt hier.

    Bewust weinig velden: alles wat met rechten en systeembeheer te maken
    heeft blijft in het Django-beheerscherm. Hier staat wat Maarten over
    zijn mensen moet kunnen vastleggen.
    """

    class Meta:
        model = Medewerker
        fields = [
            "profielfoto",
            "first_name", "last_name", "username", "functie", "rol",
            "telefoon", "email", "adres", "postcode", "woonplaats",
            "noodcontact_naam", "noodcontact_relatie", "noodcontact_telefoon",
            "rijbewijzen",
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
            "profielfoto": "Profielfoto",
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
            "kleur": "Kleur",
            "in_dienst_sinds": "In dienst sinds",
        }
        # Geen uitleg bij de velden: ze spreken voor zich (ook "Relatie" — het
        # voorbeeld "partner, moeder" is op 29-09-2026 weggehaald).
        help_texts = {veld: "" for veld in fields}

    # Kopjes boven de velden, zodat het geen lange rij invulvakken wordt.
    GROEPEN = [
        # De kleur (van je rondje en je blokjes op het weekoverzicht) staat
        # bij je naam; een eigen kopje "In de app" voor één veld was te veel.
        ("", ["first_name", "last_name", "username", "functie", "rol", "kleur"]),
        ("Contact", ["telefoon", "email", "adres", "postcode", "woonplaats"]),
        ("Bij nood bellen", ["noodcontact_naam", "noodcontact_relatie", "noodcontact_telefoon"]),
        ("Rijbewijs", ["rijbewijzen"]),
        ("In dienst", ["in_dienst_sinds"]),
    ]

    # Velden die de template zelf plaatst en die dus niet in de restgroep
    # moeten belanden — anders staan ze er twee keer, met dezelfde id. De
    # foto staat als penknopje in de kop (medewerkers/_gegevens.html).
    BUITEN_GROEPEN = frozenset({"profielfoto"})

    def groepen(self):
        """(kopje, velden) voor de template. Velden die dit formulier niet
        heeft — zoals het wachtwoord bij een nieuwe medewerker — komen er
        onderaan achteraan."""
        gebruikt = set(self.BUITEN_GROEPEN)
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

        beginkleur(self)


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


class EigenGegevensForm(RijbewijzenMixin, ProfielfotoMixin, forms.ModelForm):
    """Wat je van jezelf mag wijzigen op /mijn-profiel/.

    Niet je rol, gebruikersnaam, functie of datum in dienst: dat zijn
    gegevens van de werkgever over jou, niet van jou over jezelf. Wat je hier
    wél verandert is waar jij als enige de juiste waarde van kent — je
    nummer, je adres, wie ze bellen als er iets gebeurt.
    """

    class Meta:
        model = Medewerker
        fields = [
            "profielfoto",
            "first_name", "last_name",
            "telefoon", "email", "adres", "postcode", "woonplaats",
            "noodcontact_naam", "noodcontact_relatie", "noodcontact_telefoon",
            "rijbewijzen", "kleur",
        ]
        widgets = MedewerkerForm.Meta.widgets
        labels = MedewerkerForm.Meta.labels
        help_texts = {veld: "" for veld in fields}

    # De foto plaatst de template zelf, als penknopje in de kop.
    BUITEN_GROEPEN = frozenset({"profielfoto"})

    GROEPEN = [
        ("", ["first_name", "last_name", "kleur"]),
        ("Contact", ["telefoon", "email", "adres", "postcode", "woonplaats"]),
        ("Bij nood bellen", ["noodcontact_naam", "noodcontact_relatie", "noodcontact_telefoon"]),
        ("Rijbewijs", ["rijbewijzen"]),
    ]

    groepen = MedewerkerForm.groepen

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        beginkleur(self)


class EigenWachtwoordForm(forms.Form):
    """Je eigen wachtwoord wijzigen. Het oude erbij, want wie even bij een
    ingelogd toestel staat mag het niet zomaar kunnen overnemen."""

    huidig = forms.CharField(label="Huidig wachtwoord", widget=forms.PasswordInput, strip=False)
    nieuw = forms.CharField(
        label="Nieuw wachtwoord",
        widget=forms.PasswordInput,
        strip=False,
        help_text=WACHTWOORD_EISEN,
    )

    def __init__(self, gebruiker, *args, **kwargs):
        self.gebruiker = gebruiker
        super().__init__(*args, **kwargs)

    def clean_huidig(self):
        huidig = self.cleaned_data["huidig"]
        if not self.gebruiker.check_password(huidig):
            raise forms.ValidationError("Dat is niet je huidige wachtwoord.")
        return huidig

    def clean_nieuw(self):
        nieuw = self.cleaned_data["nieuw"]
        validate_password(nieuw, self.gebruiker)
        return nieuw

    def opslaan(self):
        self.gebruiker.set_password(self.cleaned_data["nieuw"])
        self.gebruiker.save()
