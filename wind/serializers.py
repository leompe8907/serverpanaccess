from django.utils import timezone
from rest_framework import serializers
from .models import (ListOfSubscriber)

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