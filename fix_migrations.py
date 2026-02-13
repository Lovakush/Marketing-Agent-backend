import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import connection

# Delete migration files
migration_files = [
    'apps/chatbot/migrations/0001_initial.py',
    'apps/waitlist/migrations/0001_initial.py',
]

for file in migration_files:
    if os.path.exists(file):
        os.remove(file)
        print(f"✓ Deleted: {file}")

# Clear migration history
with connection.cursor() as cursor:
    cursor.execute("DELETE FROM django_migrations WHERE app IN ('chatbot', 'waitlist');")
    print("✓ Cleared migration history from database!")

print("\nNow run:")
print("1. python manage.py makemigrations")
print("2. python manage.py migrate")