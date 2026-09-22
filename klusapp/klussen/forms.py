from django import forms
from django.utils import timezone

from .models import Klus


class KlusForm(forms.ModelForm):
    """Klus aanmaken en bijwerken. Alleen de eigenaar komt hier.

    Bewust weinig velden: SPEC §3 zet het uitgebreide klantbestand
    (contracttype, factuurperiode) in fase 2. Meer dan dit hoeft nu niet.
    """

    class Meta:
        model = Klus
        fields = ["naam", "soort", "startdatum", "opdrachtgever", "adres", "plaats", "beschrijving", "kleur", "actief"]
        widgets = {
            # format="%Y-%m-%d" is verplicht bij type="date": zonder dat rendert
            # Django een bestaande datum in het Nederlandse formaat en toont de
            # browser een leeg veld.
            "startdatum": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            # autocapitalize="words": een telefoontoetsenbord zet standaard
            # alleen de eerste letter van het veld groot ("Dijkweg 12" wordt
            # dan "Dijkweg 12", maar "fam. vermeer" blijft "Fam. vermeer").
            # Dit zijn allemaal namen en adressen, dus elk woord een hoofdletter.
            "naam": forms.TextInput(attrs={"autocapitalize": "words"}),
            "opdrachtgever": forms.TextInput(attrs={"autocapitalize": "words"}),
            # autocomplete uit: de browser zou hier het thuisadres van de
            # medewerker voorstellen, terwijl dit het adres van de klant is.
            "adres": forms.TextInput(attrs={"autocapitalize": "words", "autocomplete": "off"}),
            "plaats": forms.TextInput(attrs={"autocapitalize": "words", "autocomplete": "off"}),
            "beschrijving": forms.Textarea(attrs={"rows": 4}),
            "kleur": forms.TextInput(attrs={"type": "color"}),
        }
        labels = {
            "naam": "Naam",
            "soort": "Soort",
            "startdatum": "Startdatum",
            "opdrachtgever": "Opdrachtgever",
            "adres": "Adres",
            "plaats": "Plaats",
            "beschrijving": "Beschrijving",
            "kleur": "Kleur in het planbord",
            "actief": "Actief",
        }
        help_texts = {veld: "" for veld in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            # Nieuwe klus: de kleur wordt automatisch toegewezen (zie
            # klussen.views.klus_nieuw / klussen.kleuren.volgende_kleur), dus
            # hier geen kleurkiezer tonen.
            self.fields["kleur"].widget = forms.HiddenInput()
            self.fields["kleur"].required = False
        elif not self.initial.get("kleur"):
            # Een kleurkiezer kan niet leeg zijn; zonder beginwaarde toont de
            # browser zwart en lijkt er een kleur gekozen die er niet is.
            self.initial["kleur"] = "#95BF1D"

    def clean(self):
        gegevens = super().clean()
        # Een onderhoudsklant is een terugkerende afspraak zonder einddatum en
        # zonder begin (SPEC §1); een startdatum zou daar niets betekenen.
        if gegevens.get("soort") == Klus.Soort.ONDERHOUD:
            gegevens["startdatum"] = None
        elif not gegevens.get("startdatum"):
            self.add_error("startdatum", "Vul de startdatum van de aanlegklus in.")
        return gegevens


class MeerdereBestandenInvoer(forms.ClearableFileInput):
    """Django's standaardveld neemt één bestand aan. Vanaf een telefoon
    selecteer je zelden één foto, dus hier mogen het er meer zijn."""

    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            return files.getlist(name)
        enkel = files.get(name)
        return [enkel] if enkel else []


class MeerdereBestandenVeld(forms.FileField):
    # Wat de telefoon mag aanbieden als je het veld opent. Zonder accept zet
    # iOS er ook "video opnemen" bij, en een filmpje van een paar honderd MB
    # belandt dan als "document" in het klusdossier — niet te tonen, en precies
    # het opslagprobleem uit SPEC §6. Met deze lijst blijft het foto's maken,
    # foto's uit de rol, en de documenten die in een dossier horen.
    TOEGESTAAN = "image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MeerdereBestandenInvoer(attrs={"multiple": True, "accept": self.TOEGESTAAN}),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        controleer = super().clean
        if not isinstance(data, (list, tuple)):
            data = [data] if data else []
        if not data and self.required:
            raise forms.ValidationError(self.error_messages["required"], code="required")
        return [controleer(los, initial) for los in data]


class BijlageForm(forms.Form):
    """Het uploadveld. Werkt op drie plekken: bij een klus, bij een uurblok en
    in de fotodropbox — het verschil zit in de view, niet hier."""

    bestanden = MeerdereBestandenVeld(label="Bestanden")
    # Standaard vandaag, maar aanpasbaar: een foto wordt vaak pas 's avonds
    # of een dag later geupload, en moet dan bij de werkdag blijven horen
    # waar hij op slaat, niet bij de uploaddag. Niet verplicht: de widget
    # vult 'm altijd vooraf in zodra iemand het scherm opent, maar wie dit
    # veld zonder waarde post (geen browser, of een oud script) krijgt in de
    # view alsnog vandaag als datum in plaats van een foutmelding.
    datum = forms.DateField(
        label="Datum",
        required=False,
        initial=timezone.localdate,
        # format="%Y-%m-%d" is verplicht: zonder expliciet formaat rendert
        # Django de beginwaarde in het Nederlandse datumformaat (bv.
        # "13-09-2026"), en een HTML5 <input type="date"> accepteert alleen
        # ISO (YYYY-MM-DD) — bij een mismatch verwerpt de browser de waarde
        # stilletjes en toont hij een leeg veld in plaats van vandaag.
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    # De toelichting geldt voor alles wat je in één keer selecteert. Wie per
    # foto iets kwijt wil, uploadt ze los.
    toelichting = forms.CharField(
        label="Toelichting",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class AlleenFotosForm(BijlageForm):
    """Zelfde uploadveld als BijlageForm, maar voor de fotodropbox: een
    document zonder klus eronder heeft sinds de foto tab geen documentenlijst
    meer toont nergens een plek om terug te vinden (zie klussen/views.py:fotos
    en bijlage_toevoegen). Het bestandenveld biedt daarom alleen foto's aan;
    de server wijst een document hier alsnog af, mocht iemand het via de
    bestandenkiezer toch selecteren.

    Optioneel keuzeveld "klus": blijft leeg, dan landt de foto in de
    fotodropbox zoals altijd. Kies je er een bij, dan gaat de bijlage
    meteen naar dat klusdossier — zelfde route als _doel_van() in
    klussen/views.py al kent voor het klusdossier zelf, alleen nu ook
    zichtbaar vanuit de dropbox."""

    klus = forms.ModelChoiceField(
        label="Klus",
        queryset=Klus.objects.all(),  # Meta.ordering = ["-actief", "naam"]
        required=False,
        empty_label="Algemeen",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bestanden"].widget.attrs["accept"] = "image/*"
        # Zelfde bestandsknopje als UurblokFotosForm hieronder: "Foto's
        # kiezen" met het galerij-icoon in plaats van de generieke
        # documentknop, want hier kan toch nooit iets anders dan een foto in.
        self.fields["bestanden"].widget.attrs.update(
            {"data-knoptekst": "Foto's kiezen", "data-knopicoon": "foto"}
        )
        # Zelfde "(afgerond)"-label als de klus-filter op /fotos/, zodat een
        # afgeronde klus in deze lijst herkenbaar blijft van een lopende.
        self.fields["klus"].label_from_instance = (
            lambda klus: f"{klus.naam} (afgerond)" if not klus.actief else klus.naam
        )


class NieuweKlusBijlagenForm(BijlageForm):
    """Zelfde uploadveld als BijlageForm, maar dan naast het aanmaakformulier
    van een klus: bestanden kiezen is daar geen verplichte stap — een klus
    zonder foto's of documenten moet gewoon aan te maken zijn."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bestanden"].required = False
