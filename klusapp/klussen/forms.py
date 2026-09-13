from django import forms
from django.utils import timezone


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
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MeerdereBestandenInvoer(attrs={"multiple": True}))
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
