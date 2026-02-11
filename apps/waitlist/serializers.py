from rest_framework import serializers
from .models import Email


class EmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Email
        fields = ['id', 'email', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_email(self, value):
        return value.lower().strip()