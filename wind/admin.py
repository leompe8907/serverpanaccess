from django.contrib import admin
from wind.models import ListOfSubscriber


@admin.register(ListOfSubscriber)
class ListOfSubscriberAdmin(admin.ModelAdmin):
    """
    Configuración del admin para el modelo ListOfSubscriber.
    """
    list_display = [
        'id',
        'code',
        'full_name_display',
        'countryCode',
        'regionId',
        'smartcards_display',
        'created',
        'emails_display',
    ]
    
    list_filter = [
        'countryCode',
        'regionId',
        'created',
        'newsletterAccepted',
    ]
    
    search_fields = [
        'id',
        'code',
        'firstName',
        'lastName',
        'countryCode',
        'emails',
    ]
    
    readonly_fields = [
        'id',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'code', 'firstName', 'lastName')
        }),
        ('Smartcards', {
            'fields': ('smartcards',)
        }),
        ('Información Extendida', {
            'fields': ('regionId', 'countryCode', 'caf', 'supervisor', 'comment', 'ip')
        }),
        ('Contactos', {
            'fields': ('emails', 'phones', 'faxes', 'skypes', 'mobiles', 'custodians')
        }),
        ('Direcciones', {
            'fields': ('address1', 'address2', 'address3', 'addressCount')
        }),
        ('Información Adicional', {
            'fields': ('newsletterAccepted', 'tags', 'uniqueLogin')
        }),
        ('Fechas', {
            'fields': ('created', 'firstOrderTime', 'lastExpiryTime')
        }),
    )
    
    ordering = ['-created']
    
    def full_name_display(self, obj):
        """Muestra el nombre completo del suscriptor."""
        name_parts = [obj.firstName, obj.lastName]
        name = ' '.join(filter(None, name_parts))
        return name or 'Sin nombre'
    full_name_display.short_description = 'Nombre Completo'
    
    def smartcards_display(self, obj):
        """Muestra la cantidad de smartcards."""
        if isinstance(obj.smartcards, list):
            return len(obj.smartcards)
        return 0
    smartcards_display.short_description = 'Smartcards'
    
    def emails_display(self, obj):
        """Muestra el email o 'Sin email'."""
        return obj.emails or 'Sin email'
    emails_display.short_description = 'Email'

