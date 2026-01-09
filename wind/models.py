from django.db import models
from django.utils import timezone

from .utils.encryption import encrypt_value, decrypt_value


class ListOfSubscriber(models.Model):
    id = models.CharField(primary_key=True, blank=True, unique=True, max_length=100)
    code = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)
    lastName = models.CharField(max_length=100, null=True, blank=True)
    firstName = models.CharField(max_length=100, null=True, blank=True)
    smartcards = models.JSONField(null=True, blank=True, db_index=True)
    created = models.DateTimeField(null=True, blank=True)  # Cambiado de DateField a DateTimeField
    
    # Nuevos campos de información extendida
    regionId = models.IntegerField(null=True, blank=True)
    countryCode = models.CharField(max_length=10, null=True, blank=True)
    caf = models.CharField(max_length=255, null=True, blank=True)
    supervisor = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Contactos
    emails = models.EmailField(null=True, blank=True, db_index=True)  # Email principal (primer email de la lista)
    phones = models.JSONField(null=True, blank=True)  # Lista de teléfonos
    faxes = models.JSONField(null=True, blank=True)
    skypes = models.JSONField(null=True, blank=True)
    mobiles = models.JSONField(null=True, blank=True)
    custodians = models.JSONField(null=True, blank=True)
    
    # Direcciones (JSON)
    address1 = models.JSONField(null=True, blank=True)
    address2 = models.JSONField(null=True, blank=True)
    address3 = models.JSONField(null=True, blank=True)
    addressCount = models.IntegerField(default=0, null=True, blank=True)
    
    # Información adicional
    newsletterAccepted = models.BooleanField(default=False, null=True, blank=True)
    firstOrderTime = models.DateTimeField(null=True, blank=True)
    lastExpiryTime = models.DateTimeField(null=True, blank=True)
    uniqueLogin = models.IntegerField(null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['emails']),
            models.Index(fields=['smartcards']),
        ]

    def __str__(self):
        """Representación string del suscriptor."""
        name_parts = [self.firstName, self.lastName]
        name = ' '.join(filter(None, name_parts))
        if name:
            return f"{name} ({self.code or self.id})"
        return f"Suscriptor {self.code or self.id}"

class ListOfSmartcards(models.Model):
    sn = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    subscriberCode = models.CharField(max_length=100, null=True, blank=True, db_index=True)
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

    class Meta:
        indexes = [
            models.Index(fields=['subscriberCode']),
            models.Index(fields=['sn']),
        ]

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
    password_hash = models.CharField(max_length=255, null=True, blank=True)  # Password encriptado
    licenses = models.JSONField(null=True, blank=True)

    def __str__(self):
        """Representación string de la información de login."""
        return f"Login Info - Subscriber: {self.subscriberCode or 'N/A'}"
    
    def set_password(self, raw_password):
        """Encripta y guarda el password."""
        if raw_password:
            self.password_hash = encrypt_value(raw_password)
        else:
            self.password_hash = None
    
    def get_password(self):
        """Desencripta y retorna el password."""
        return decrypt_value(self.password_hash) if self.password_hash else None
    
    def check_password(self, raw_password):
        """Verifica si el password proporcionado coincide con el almacenado."""
        if not self.password_hash or not raw_password:
            return False
        return self.get_password() == raw_password

class ListOfProducts(models.Model):
    productId = models.IntegerField(primary_key=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    ordered = models.IntegerField(default=0)
    activeOrders = models.IntegerField(default=0)
    flexiblyOrdered = models.IntegerField(default=0)
    activeFlexibleOrders = models.IntegerField(default=0)
    deleted = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    minRunTime = models.IntegerField(default=0)
    minRunTimeType = models.CharField(max_length=100, null=True, blank=True)
    allowFlexibleRuntime = models.BooleanField(default=False)
    hasOptionalPackages = models.BooleanField(default=False)
    packages = models.JSONField(null=True, blank=True)  # array of int
    optionalPackages = models.JSONField(null=True, blank=True)  # array of int
    catchupGroups = models.JSONField(null=True, blank=True)  # array of int
    streams = models.JSONField(null=True, blank=True)  # array of int
    vodLibraries = models.JSONField(null=True, blank=True)  # array of int
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    def __str__(self):
        """Representación string del producto."""
        return f"{self.name or 'Sin nombre'} (ID: {self.productId})"

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

    class Meta:
        indexes = [
            models.Index(fields=['subscriber_code']),
            models.Index(fields=['sn']),
        ]

class SubscriberEmailRegistry(models.Model):
    """
    Registro de emails para prevenir múltiples cuentas.
    Rastrea emails registrados y si el usuario compró contenido.
    """
    email = models.EmailField(unique=True, db_index=True)
    subscriber_code = models.CharField(max_length=100, null=True, blank=True)
    document = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    has_purchased = models.BooleanField(default=False)
    purchased_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Registro de Email de Suscriptor"
        verbose_name_plural = "Registros de Emails de Suscriptores"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['document']),
        ]
    
    def __str__(self):
        return f"{self.email} - {self.subscriber_code or 'Sin código'}"

class SubscriberDocumentRegistry(models.Model):
    """
    Registro de documentos para prevenir múltiples cuentas.
    Complementa la validación por email con validación por documento de identidad.
    """
    document = models.CharField(max_length=50, unique=True, db_index=True)
    subscriber_code = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    has_purchased = models.BooleanField(default=False)
    purchased_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Registro de Documento de Suscriptor"
        verbose_name_plural = "Registros de Documentos de Suscriptores"
        indexes = [
            models.Index(fields=['document']),
        ]
    
    def __str__(self):
        return f"{self.document} - {self.subscriber_code or 'Sin código'}"