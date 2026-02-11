from django.contrib import admin
from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['message', 'timestamp', 'session_id']
    search_fields = ['message', 'response']
    list_filter = ['timestamp']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']