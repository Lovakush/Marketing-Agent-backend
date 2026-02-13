from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Drop old chatbot tables to allow fresh migration'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            tables = [
                'chat_messages',
                'chat_sessions', 
                'conversation_contexts',
                'bot_performance_metrics',
            ]
            
            for table in tables:
                try:
                    cursor.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
                    self.stdout.write(self.style.SUCCESS(f'✓ Dropped table: {table}'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ Table {table}: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ All old tables dropped!'))
        self.stdout.write(self.style.SUCCESS('Now run: python manage.py migrate chatbot'))