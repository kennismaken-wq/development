"""Wachtwoordeisen met Nederlandse meldingen.

Django's eigen MinimumLengthValidator gaf in Django 6.1 een Engelse melding
("This password is too short…") tussen de Nederlandse, omdat de vertaling van
die zin ontbreekt (stresstest 03-10-2026, B21). Zelfde eis, eigen tekst.
"""

from django.contrib.auth.password_validation import MinimumLengthValidator
from django.core.exceptions import ValidationError


class MinimaleLengte(MinimumLengthValidator):
    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                f"Dit wachtwoord is te kort. Kies minstens {self.min_length} tekens.",
                code="password_too_short",
                params={"min_length": self.min_length},
            )

    def get_help_text(self):
        return f"Je wachtwoord moet minstens {self.min_length} tekens hebben."
