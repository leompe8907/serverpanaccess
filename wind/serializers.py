from django.utils import timezone
from rest_framework import serializers
from .models import (ListOfSubscriber, ListOfSmartcards, SubscriberLoginInfo, SubscriberInfo, ListOfProducts)

class ListOfSubscriberSerializer(serializers.ModelSerializer):
    """Serializer para datos raw de suscriptores desde Panaccess"""
    
    class Meta:
        model = ListOfSubscriber
        fields = '__all__'
        
    def validate_code(self, value):
        """Validar que el código del suscriptor no esté vacío"""
        if not value or not value.strip():
            raise serializers.ValidationError("El código del suscriptor es requerido")
        return value.strip()

class ListOfSmartcardsSerializer(serializers.ModelSerializer):
    """Serializer para datos raw de smartcards desde Panaccess"""
    
    class Meta:
        model = ListOfSmartcards
        fields = '__all__'
        
    def validate_sn(self, value):
        """Validar número de serie de smartcard"""
        if not value or not value.strip():
            raise serializers.ValidationError("El número de serie es requerido")
        return value.strip()

class SubscriberLoginInfoSerializer(serializers.ModelSerializer):
    """Serializer para información de login raw desde Panaccess"""
    
    class Meta:
        model = SubscriberLoginInfo
        fields = '__all__'

class ListOfProductsSerializer(serializers.ModelSerializer):
    """Serializer para datos raw de productos desde Panaccess"""
    
    class Meta:
        model = ListOfProducts
        fields = '__all__'


class SubscriberInfoSerializer(serializers.ModelSerializer):
    """
    Serializer principal para el sistema UDID.
    Maneja datos consolidados y seguros.
    """
    
    # Campos de solo escritura para passwords
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    pin = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    # Campos de solo lectura para datos sensibles
    password_hash = serializers.CharField(read_only=True)
    pin_hash = serializers.CharField(read_only=True)
    failed_login_attempts = serializers.IntegerField(read_only=True)
    locked_until = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = SubscriberInfo
        fields = [
            'id', 'subscriber_code', 'sn', 'first_name', 'last_name',
            'lastActivation', 'lastContact', 'lastServiceListDownload',
            'lastActivationIP', 'lastApiKeyId', 'products', 'packages',
            'packageNames', 'model', 'login1', 'login2', 'activated',
            'activation_date', 'last_login', 'created_at', 'updated_at',
            # Write-only fields
            'password', 'pin',
            # Read-only fields  
            'password_hash', 'pin_hash', 'failed_login_attempts', 'locked_until'
        ]


# Serializers para crear suscriptores
class ContactSerializer(serializers.Serializer):
    """Serializer para contactos de suscriptores"""
    type = serializers.ChoiceField(
        choices=['email', 'phone', 'fax', 'skype', 'mobile', 'custodian'],
        required=True
    )
    isBusiness = serializers.BooleanField(required=True)
    contact = serializers.CharField(required=True, max_length=255)


class AddressSerializer(serializers.Serializer):
    """Serializer para direcciones de suscriptores"""
    type = serializers.ChoiceField(
        choices=['private', 'company', 'bill', 'deliver'],
        required=True
    )
    name = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    country = serializers.CharField(required=True, max_length=2)  # Código de 2 letras ISO
    city = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    zip = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=20)
    street = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    addition = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    addition2 = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    addition3 = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    zone = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    district = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    ownership = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=2)
    ownerName = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    ownerPhone = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)


class CreateSubscriberSerializer(serializers.Serializer):
    """
    Serializer para crear un nuevo suscriptor en PanAccess.
    
    El código del suscriptor se genera automáticamente con formato AUTO + número.
    El supervisor se fija automáticamente a "AUTOMATICO".
    """
    # Campos requeridos
    hcId = serializers.CharField(required=True, max_length=100)
    lastName = serializers.CharField(required=True, max_length=100)
    firstName = serializers.CharField(required=True, max_length=100)
    
    # Campos opcionales
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)