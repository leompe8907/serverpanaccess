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
        'hcId',
        'country',
        'city',
        'smartcards_display',
        'created',
        'modified',
    ]
    
    list_filter = [
        'country',
        'hcId',
        'created',
        'modified',
    ]
    
    search_fields = [
        'id',
        'code',
        'firstName',
        'lastName',
        'hcId',
        'hcName',
        'country',
        'city',
        'zip',
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
        ('Headend', {
            'fields': ('hcId', 'hcName')
        }),
        ('Ubicación', {
            'fields': ('country', 'city', 'zip', 'address')
        }),
        ('Fechas', {
            'fields': ('created', 'modified')
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

