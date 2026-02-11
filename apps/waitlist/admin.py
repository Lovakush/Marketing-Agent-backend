from django.contrib import admin
from .models import Email


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ['email', 'created_at', 'id']
    search_fields = ['email']
    ordering = ['-created_at']
    readonly_fields = ['created_at']