from django import forms


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
    # De toelichting geldt voor alles wat je in één keer selecteert. Wie per
    # foto iets kwijt wil, uploadt ze los.
    toelichting = forms.CharField(
        label="Toelichting",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
