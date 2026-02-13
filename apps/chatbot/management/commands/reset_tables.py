from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS chat_messages CASCADE')
            cursor.execute('DROP TABLE IF EXISTS chat_sessions CASCADE')
            cursor.execute('DROP TABLE IF EXISTS support_tickets CASCADE')
        print('✓ Tables dropped!')