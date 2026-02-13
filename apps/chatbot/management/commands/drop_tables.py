from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Drop chatbot tables'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            tables = ['chat_messages', 'chat_sessions', 'support_tickets']
            for table in tables:
                try:
                    cursor.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
                    self.stdout.write(self.style.SUCCESS(f'✓ Dropped {table}'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ {table}: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Done! Now run: python manage.py makemigrations chatbot'))