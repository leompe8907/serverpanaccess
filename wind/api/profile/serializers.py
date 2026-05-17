from django.contrib.auth import get_user_model
from rest_framework import serializers

from wind.models import ListOfProducts, ListOfSubscriber, SubscriberEmailRegistry
from wind.serializers import ListOfProductsSerializer

User = get_user_model()


class ProfileMeSerializer(serializers.ModelSerializer):
    subscriber_code = serializers.SerializerMethodField()
    subscriber = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "pk",
            "email",
            "first_name",
            "last_name",
            "subscriber_code",
            "subscriber",
        ]
        read_only_fields = fields

    def get_subscriber_code(self, obj):
        try:
            return SubscriberEmailRegistry.objects.get(email=obj.email).subscriber_code
        except SubscriberEmailRegistry.DoesNotExist:
            return None

    def get_subscriber(self, obj):
        code = self.get_subscriber_code(obj)
        if not code:
            return None
        sub = ListOfSubscriber.objects.filter(code=code).first()
        if not sub:
            return None
        return {
            "code": sub.code,
            "firstName": sub.firstName,
            "lastName": sub.lastName,
            "emails": sub.emails,
        }


class ProfilePasswordSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    newPass = serializers.CharField(max_length=255, write_only=True)


class ProfileProductSerializer(ListOfProductsSerializer):
    """Catálogo local sincronizado (lectura)."""

    class Meta(ListOfProductsSerializer.Meta):
        model = ListOfProducts
        fields = [
            "productId",
            "name",
            "description",
            "deleted",
            "packages",
            "optionalPackages",
            "updated_at",
        ]
