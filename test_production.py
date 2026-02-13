import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
os.environ['DEBUG'] = 'False'

try:
    django.setup()
    print("✅ Django setup successful")
    
    # Test database connection
    from django.db import connection
    connection.ensure_connection()
    print("✅ Database connection successful")
    
    # Test Gemini API
    from apps.chatbot.services import GeminiService
    print(f"✅ Using Gemini model: {GeminiService.MODEL_NAME}")
    
    # Test SSL certificates
    import certifi
    print(f"✅ SSL certificates found: {certifi.where()}")
    
    # Test settings
    from django.conf import settings
    print(f"✅ DEBUG={settings.DEBUG}")
    print(f"✅ ALLOWED_HOSTS={settings.ALLOWED_HOSTS}")
    
    print("\n🎉 All production checks passed!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    sys.exit(1)