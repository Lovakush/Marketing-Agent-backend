from django.db import models


class ChatMessage(models.Model):
    message = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['-timestamp']

    def __str__(self):
        return f"Message at {self.timestamp}"