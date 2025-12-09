from django.db import models
from django.utils import timezone


class ListOfSubscriber(models.Model):
    id = models.CharField(primary_key=True, unique=True, max_length=100)
    code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    lastName = models.CharField(max_length=100, null=True, blank=True)
    firstName = models.CharField(max_length=100, null=True, blank=True)
    smartcards = models.JSONField(null=True, blank=True)
    hcId = models.CharField(max_length=100, null=True, blank=True)
    hcName = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    created = models.DateField(null=True, blank=True)
    modified = models.DateField(null=True, blank=True)

    def __str__(self):
        """Representación string del suscriptor."""
        name_parts = [self.firstName, self.lastName]
        name = ' '.join(filter(None, name_parts))
        if name:
            return f"{name} ({self.code or self.id})"
        return f"Suscriptor {self.code or self.id}"