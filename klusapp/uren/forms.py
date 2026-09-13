from django import forms

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
            # step=300: de telefoonkiezer springt dan in stappen van vijf
            # minuten in plaats van per minuut.
            "begintijd": forms.TimeInput(attrs={"type": "time", "step": 300}, format="%H:%M"),
            "eindtijd": forms.TimeInput(attrs={"type": "time", "step": 300}, format="%H:%M"),
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
