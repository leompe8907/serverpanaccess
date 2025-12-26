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

class ListOfSmartcards(models.Model):
    sn = models.CharField(max_length=100, unique=True, null=True, blank=True)
    subscriberCode = models.CharField(max_length=100, null=True, blank=True)
    lastName = models.CharField(max_length=100, blank=True, null=True)
    firstName = models.CharField(max_length=100, blank=True, null=True)
    pin = models.CharField(max_length=100, null=True, blank=True)
    pairedBox = models.CharField(max_length=100, null=True, blank=True)
    products = models.JSONField(null=True, blank=True)
    casIds = models.CharField(max_length=100, null=True, blank=True)
    packages = models.JSONField(null=True, blank=True)
    packageNames = models.JSONField(null=True, blank=True)
    configId = models.CharField(max_length=100, null=True, blank=True)
    configProtected = models.BooleanField(default=False, null=True, blank=True)
    alias = models.CharField(max_length=100, null=True, blank=True)
    regionId = models.IntegerField(null=True, blank=True)
    regionName = models.CharField(max_length=100, null=True, blank=True)
    masterSn = models.CharField(max_length=100, null=True, blank=True)
    hcId = models.CharField(max_length=100, null=True, blank=True)
    lastActivation = models.DateTimeField(null=True, blank=True)
    lastContact = models.DateTimeField(null=True, blank=True)
    lastServiceListDownload = models.DateTimeField(null=True, blank=True)
    lastActivationIP = models.CharField(max_length=100, null=True, blank=True)
    firmwareVersion = models.CharField(max_length=100, null=True, blank=True)
    camlibVersion = models.CharField(max_length=100, null=True, blank=True)
    lastApiKeyId = models.CharField(max_length=100, null=True, blank=True)
    blacklisted = models.BooleanField(default=False, null=True, blank=True)
    disabled = models.BooleanField(default=False, null=True, blank=True)
    defect = models.BooleanField(default=False, null=True, blank=True)
    stbModel = models.CharField(max_length=100, null=True, blank=True)
    stbVendor = models.CharField(max_length=100, null=True, blank=True)
    stbChipset = models.CharField(max_length=100, null=True, blank=True)
    mac = models.CharField(max_length=100, null=True, blank=True)
    manufacturer = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)
    fingerprint = models.CharField(max_length=100, null=True, blank=True)
    hardware = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        """Representación string de la smartcard."""
        name_parts = [self.firstName, self.lastName]
        name = ' '.join(filter(None, name_parts))
        if name:
            return f"{name} (SN: {self.sn or 'N/A'})"
        return f"Smartcard {self.sn or 'N/A'}"

class SubscriberLoginInfo(models.Model):
    subscriberCode = models.CharField(max_length=100, null=True, blank=True)
    login1 = models.IntegerField(null=True, blank=True)
    login2 = models.CharField(max_length=100, null=True, blank=True)
    additionalLogins = models.JSONField(null=True, blank=True)
    password = models.CharField(max_length=100, null=True, blank=True)
    licenses = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.data

class SubscriberInfo(models.Model):
    # Subscriber fields
    subscriber_code = models.CharField(max_length=100)

    # Smartcard fields
    sn = models.CharField(max_length=100, null=True, blank=True)
    pin_hash = models.CharField(max_length=255, null=True, blank=True)  # PIN hasheado
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    lastActivation = models.DateTimeField(null=True, blank=True)
    lastContact = models.DateTimeField(null=True, blank=True)
    lastServiceListDownload = models.DateTimeField(null=True, blank=True)
    lastActivationIP = models.CharField(max_length=100, null=True, blank=True)
    lastApiKeyId = models.CharField(max_length=100, null=True, blank=True)
    products = models.JSONField(null=True, blank=True)
    packages = models.JSONField(null=True, blank=True)
    packageNames = models.JSONField(null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)

    # Login fields - passwords hasheadas
    login1 = models.IntegerField(null=True, blank=True)
    login2 = models.CharField(max_length=100, null=True, blank=True)
    password_hash = models.CharField(max_length=255, null=True, blank=True)

    # Control de activación
    activated = models.BooleanField(default=False)
    activation_date = models.DateTimeField(null=True, blank=True)
    
    # Security fields
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)