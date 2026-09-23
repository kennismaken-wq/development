import datetime

from django import forms

from klussen.forms import AlleenFotosForm
from klussen.models import Klus

from .models import Uurblok


class KwartierSelect(forms.Select):
    """Select met alleen hele kwartieren — een native <input type=time step>
    lost dit niet overal op: de tijdkiezer van met name Android laat gewoon
    elke minuut kiezen, ongeacht step. Dit garandeert het net als de
    tijdkiezer van Google Calendar, op elk toestel."""

    def format_value(self, value):
        # initial/instance-waarden komen als datetime.time binnen (niet als
        # de "HH:MM"-string die in choices staat); zonder deze omzetting
        # matcht format_value() van Select geen enkele optie en staat een
        # bestaand blok bij het bewerken leeg in plaats van op zijn tijd.
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        return super().format_value(value)


class KlusSelect(forms.Select):
    """Keuzelijst van klussen met de soort per optie erbij, zodat
    static/js/kluskiezer.js er een zoekbare lijst met de pillen
    Alle/Eenmalig/Onderhoud van kan maken. De <select> zelf blijft gewoon de
    waarde die gepost wordt (en zonder javascript gewoon zichtbaar), dit zet
    er alleen het data-attribuut op waar dat script op filtert.

    "altijd" op de lege keuze ("Kies een klus"): die moet onder elke pil
    zichtbaar blijven, ook onder Onderhoud."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        optie = super().create_option(name, value, label, selected, index, subindex, attrs)
        # value is een ModelChoiceIteratorValue met de klus erachter; alleen
        # bij de lege keuze is het een kale lege string.
        klus = getattr(value, "instance", None)
        optie["attrs"]["data-scope"] = klus.soort if klus is not None else "altijd"
        return optie


def _tijdkeuzes():
    keuzes = [("", "--:--")]
    for uur in range(24):
        for minuut in (0, 15, 30, 45):
            waarde = f"{uur:02d}:{minuut:02d}"
            keuzes.append((waarde, waarde))
    return keuzes


class UurblokForm(forms.ModelForm):
    """Het formulier dat een medewerker 's avonds op zijn telefoon invult."""

    class Meta:
        model = Uurblok
        fields = ["klus", "datum", "begintijd", "eindtijd", "toelichting"]
        widgets = {
            # De klasse hoort bij de zoekbare kiezer die static/js/kluskiezer.js
            # eroverheen bouwt (zie _uurblokformulier.html): daarmee verdwijnt
            # de kale keuzelijst pas als dat script echt geladen is.
            "klus": KlusSelect(attrs={"class": "klus-kiezer-select"}),
            # Het format moet erbij: een HTML-datumveld leest alleen
            # 2026-09-07, terwijl Django in het Nederlands 07-09-2026 zou
            # tonen. Zonder dit komt een bestaande datum leeg in beeld.
            "datum": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "begintijd": KwartierSelect(choices=_tijdkeuzes()),
            "eindtijd": KwartierSelect(choices=_tijdkeuzes()),
            "toelichting": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "klus": "Klus",
            "datum": "Dag",
            "begintijd": "Van",
            "eindtijd": "Tot",
            "toelichting": "Werkzaamheden",
        }
        # Duidelijke tekst voor de foutpopup (zie _uurblokformulier.html): de
        # standaard "Dit veld is verplicht." zegt in die popup niet genoeg
        # zonder erbij te lezen welk veld het is.
        error_messages = {
            "klus": {"required": "Deze activiteit is niet aan een klus gekoppeld."},
            "datum": {"required": "Vul een dag in."},
            "begintijd": {"required": "Vul een begintijd in."},
            "eindtijd": {"required": "Vul een eindtijd in."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["klus"].queryset = Klus.objects.filter(actief=True)
        self.fields["klus"].empty_label = "Kies een klus"
        self.fields["toelichting"].required = False

    def clean(self):
        gegevens = super().clean()
        begin, eind = gegevens.get("begintijd"), gegevens.get("eindtijd")
        if begin and eind and eind <= begin:
            self.add_error("eindtijd", "De eindtijd moet na de begintijd liggen.")
        return gegevens


class UurblokFotosForm(AlleenFotosForm):
    """Foto's die je meteen bij het invullen van de uren kunt meesturen —
    zelfde AlleenFotosForm als de fotodropbox (alleen foto's, geen
    documenten), maar optioneel: bestanden kiezen is geen verplichte stap en
    mag het opslaan van de uren nooit blokkeren (zie uren.views.uurblok_nieuw).
    De data-attributen sturen het bestandsknopje (static/js/bestandsveld.js)
    naar hetzelfde galerij-icoon als de "Galerij"-tegel in de zijbalk, in
    plaats van het generieke document-icoon van de "Bestanden kiezen"-knop."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bestanden"].required = False
        self.fields["bestanden"].widget.attrs.update(
            {"data-knoptekst": "Foto toevoegen", "data-knopicoon": "foto"}
        )
