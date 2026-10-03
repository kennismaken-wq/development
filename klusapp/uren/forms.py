import datetime

from django import forms
from django.conf import settings
from django.db.models import Case, Q, When
from django.utils import timezone

from klussen.forms import AlleenFotosForm, KlusSelect
from klussen.models import Klus

from .models import Inzet, Uurblok

# Grenzen voor een uurblok (B6, afgesproken met Floris 03-10-2026).
MAX_DAGEN_TERUG = 365
MAX_DAGEN_VOORUIT = 7
MAX_UREN_PER_BLOK = 16


def _minuten(tijd):
    return tijd.hour * 60 + tijd.minute


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


# Vroeger begint niemand: hoveniers starten tussen vijf en acht. Zonder deze
# grens begint de tijdkiezer van de telefoon op 00:00 en scrol je eerst twintig
# kwartieren voorbij voordat je bij een werktijd bent (gesprek Maarten,
# 01-10-2026).
WERKDAG_BEGIN = datetime.time(5, 0)


def _tijdkeuzes(vanaf=WERKDAG_BEGIN, ook=()):
    """De kwartieren vanaf `vanaf`, plus de tijden in `ook` die daarvoor
    vallen — een bestaand blok van 04:30 moet bij bewerken gewoon op 04:30
    blijven staan in plaats van leeg."""
    tijden = {
        datetime.time(uur, minuut)
        for uur in range(24)
        for minuut in (0, 15, 30, 45)
        if datetime.time(uur, minuut) >= vanaf
    }
    tijden.update(t for t in ook if isinstance(t, datetime.time))
    return [("", "--:--")] + [(t.strftime("%H:%M"),) * 2 for t in sorted(tijden)]


class UurblokForm(forms.ModelForm):
    """Het formulier dat een medewerker 's avonds op zijn telefoon invult."""

    class Meta:
        model = Uurblok
        fields = ["klus", "datum", "begintijd", "eindtijd", "toelichting", "extra_werk"]
        widgets = {
            # De klasse hoort bij de zoekbare kiezer die static/js/kluskiezer.js
            # eroverheen bouwt (zie _uurblokformulier.html): daarmee verdwijnt
            # de kale keuzelijst pas als dat script echt geladen is. Hier één
            # rij pillen (soort); de staat-rij die dezelfde widget meelevert
            # zou niets doen, want de queryset hieronder filtert al op actief.
            "klus": KlusSelect(attrs={"class": "klus-kiezer-select"}),
            # Het format moet erbij: een HTML-datumveld leest alleen
            # 2026-09-07, terwijl Django in het Nederlands 07-09-2026 zou
            # tonen. Zonder dit komt een bestaande datum leeg in beeld.
            "datum": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "begintijd": KwartierSelect(choices=_tijdkeuzes()),
            "eindtijd": KwartierSelect(choices=_tijdkeuzes()),
            # data-dicteer: microfoonknop erin, zie static/js/dicteren.js.
            "toelichting": forms.Textarea(attrs={"rows": 3, "data-dicteer": ""}),
            "extra_werk": forms.Textarea(attrs={"rows": 2, "data-dicteer": ""}),
        }
        labels = {
            "klus": "Klus",
            "datum": "Dag",
            "begintijd": "Van",
            "eindtijd": "Tot",
            "toelichting": "Werkzaamheden",
            "extra_werk": "Extra werk",
        }
        # Duidelijke tekst voor de foutpopup (zie _uurblokformulier.html): de
        # standaard "Dit veld is verplicht." zegt in die popup niet genoeg
        # zonder erbij te lezen welk veld het is.
        error_messages = {
            "klus": {"required": "Kies een klus."},
            "datum": {"required": "Vul een dag in."},
            "begintijd": {"required": "Vul een begintijd in."},
            "eindtijd": {"required": "Vul een eindtijd in."},
        }

    def __init__(self, *args, medewerker=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Van wie de uren zijn, voor de overlapcontrole hieronder. Bij
        # bewerken staat dat al op het blok; bij een nieuw blok geeft de view
        # het mee (de medewerker zit niet in het formulier zelf).
        self.medewerker = medewerker or (self.instance.medewerker if self.instance.pk else None)
        # Alleen lopende klussen om uit te kiezen, maar bij een bestaand blok
        # ook zijn eigen klus: die wordt vaak afgerond terwijl de laatste uren
        # nog gecorrigeerd moeten worden, en dan kon het blok niet meer
        # worden opgeslagen (stresstest 03-10-2026, B10).
        lopend = Q(actief=True)
        if self.instance.pk:
            lopend |= Q(pk=self.instance.klus_id)
        self.fields["klus"].queryset = self._op_volgorde(Klus.objects.filter(lopend))
        self.fields["klus"].error_messages["invalid_choice"] = (
            "Deze klus is intussen afgerond. Kies een andere klus, of vraag de eigenaar."
        )
        self.fields["klus"].empty_label = "Kies een klus"
        self.fields["toelichting"].required = False
        # Tijden van vóór WERKDAG_BEGIN alleen als ze er al staan (bestaand
        # blok, of een vak dat in de kalender is aangetikt).
        bestaand = [
            self.initial.get(veld) or getattr(self.instance, veld, None)
            for veld in ("begintijd", "eindtijd")
        ]
        for veld in ("begintijd", "eindtijd"):
            self.fields[veld].widget.choices = _tijdkeuzes(ook=bestaand)

    def _op_volgorde(self, klussen):
        """Bovenaan de klussen waar je die dag op de werkplanning stond, dan
        je laatst gebruikte, dan de rest op naam. Eerst stonden alle ~45
        lopende klussen op alfabet en moest je elke avond zoeken (U5, Floris
        03-10-2026). Niets wordt vooraf gekozen; de kiezer toont er een
        labeltje bij (KlusSelect, data-hint)."""
        if not self.medewerker:
            return klussen
        dag = self.initial.get("datum") or (self.instance.datum if self.instance.pk else None)
        ingepland = set()
        if dag:
            ingepland = set(
                Inzet.objects.filter(medewerker=self.medewerker, datum=dag).values_list("klus_id", flat=True)
            )
        laatst = Uurblok.objects.filter(medewerker=self.medewerker).order_by("-datum", "-eindtijd")
        recent = [pk for pk in dict.fromkeys(laatst.values_list("klus_id", flat=True)[:40]) if pk not in ingepland][:5]
        self.fields["klus"].widget.hints = {
            **{pk: "Laatst gebruikt" for pk in recent},
            **{pk: "Ingepland" for pk in ingepland},
        }
        return klussen.annotate(
            volgorde=Case(When(pk__in=ingepland, then=0), When(pk__in=recent, then=1), default=2)
        ).order_by("volgorde", "-actief", "naam")

    def clean(self):
        gegevens = super().clean()
        datum = gegevens.get("datum")
        begin, eind = gegevens.get("begintijd"), gegevens.get("eindtijd")
        # Een tikfout in het jaar (2062, 0202) is op een telefoon zo gemaakt,
        # en zo'n blok verdween dan uit de agenda maar telde wel mee in de
        # export (stresstest 03-10-2026, B6). Alleen bij een nieuwe of
        # gewijzigde datum: een oud blok mag je gewoon nog aanpassen.
        if datum and datum != self.instance.datum and settings.UREN_DATUMGRENS:
            vandaag = timezone.localdate()
            if datum < vandaag - datetime.timedelta(days=MAX_DAGEN_TERUG):
                self.add_error("datum", f"Klopt de datum? {datum:%d-%m-%Y} is meer dan een jaar geleden.")
            elif datum > vandaag + datetime.timedelta(days=MAX_DAGEN_VOORUIT):
                self.add_error("datum", f"Klopt de datum? {datum:%d-%m-%Y} ligt meer dan een week vooruit.")
        if begin and eind and eind <= begin:
            self.add_error("eindtijd", "De eindtijd moet na de begintijd liggen.")
        elif begin and eind and _minuten(eind) - _minuten(begin) > MAX_UREN_PER_BLOK * 60:
            self.add_error("eindtijd", f"Eén blok mag hooguit {MAX_UREN_PER_BLOK} uur zijn. Klopt de eindtijd?")
        elif datum and begin and eind and self.medewerker:
            # Twee blokken die elkaar overlappen tellen allebei mee in het
            # weektotaal, het planbord en de export voor de boekhouder: 08–12
            # en 10–14 werd 8 uur terwijl er 6 gewerkt zijn. Aansluiten
            # (12:00 tot, 12:00 van) mag wel.
            botsing = (
                Uurblok.objects.filter(
                    medewerker=self.medewerker, datum=datum, begintijd__lt=eind, eindtijd__gt=begin
                )
                .exclude(pk=self.instance.pk)
                .select_related("klus")
                .order_by("begintijd")
                .first()
            )
            if botsing:
                self.add_error(
                    "begintijd",
                    f"Je hebt op deze dag al uren van {botsing.begintijd:%H:%M} tot "
                    f"{botsing.eindtijd:%H:%M} ({botsing.klus}). Kies een tijd die "
                    "daar niet overheen valt.",
                )
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
