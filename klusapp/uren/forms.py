from django import forms

from klussen.forms import AlleenFotosForm
from klussen.models import Klus

from .models import Uurblok


class UurblokForm(forms.ModelForm):
    """Het formulier dat een medewerker 's avonds op zijn telefoon invult."""

    class Meta:
        model = Uurblok
        fields = ["klus", "datum", "begintijd", "eindtijd", "toelichting"]
        widgets = {
            # Het format moet erbij: een HTML-datumveld leest alleen
            # 2026-09-07, terwijl Django in het Nederlands 07-09-2026 zou
            # tonen. Zonder dit komt een bestaande datum leeg in beeld.
            "datum": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            # step=900: de telefoonkiezer springt dan in stappen van vijftien
            # minuten in plaats van per minuut.
            "begintijd": forms.TimeInput(attrs={"type": "time", "step": 900}, format="%H:%M"),
            "eindtijd": forms.TimeInput(attrs={"type": "time", "step": 900}, format="%H:%M"),
            "toelichting": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "klus": "Klus",
            "datum": "Dag",
            "begintijd": "Van",
            "eindtijd": "Tot",
            "toelichting": "Werkzaamheden",
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
