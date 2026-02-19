"""
Database health check command.
Usage: python manage.py db_health_check
"""

from django.core.management.base import BaseCommand
from django.db import connection
from apps.auth_app.models import SupabaseUser
from apps.tenants.models import Tenant, AgentConfig


class Command(BaseCommand):
    help = 'Check database health and identify issues'

    def handle(self, *args, **options):
        self.stdout.write("="*60)
        self.stdout.write("DATABASE HEALTH CHECK")
        self.stdout.write("="*60)
        
        # Check 1: Users without supabase_uid
        self.check_null_uids()
        
        # Check 2: Users without tenants
        self.check_orphaned_users()
        
        # Check 3: Tenant statistics
        self.check_tenants()
        
        # Check 4: Agent configurations
        self.check_agent_configs()
        
        # Check 5: Table counts
        self.check_table_counts()
        
        # Check 6: RLS status (if possible)
        self.check_rls_status()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("Health check complete!")
        self.stdout.write("="*60)
    
    def check_null_uids(self):
        """Check for users with null supabase_uid."""
        self.stdout.write("\n1. Checking for NULL supabase_uid...")
        
        null_uid_users = SupabaseUser.objects.filter(supabase_uid__isnull=True)
        count = null_uid_users.count()
        
        if count > 0:
            self.stdout.write(self.style.ERROR(f"   ❌ Found {count} users with NULL supabase_uid"))
            for user in null_uid_users[:5]:
                self.stdout.write(f"      - {user.email} (ID: {user.id})")
            if count > 5:
                self.stdout.write(f"      ... and {count - 5} more")
            self.stdout.write(self.style.WARNING("   Run: python manage.py cleanup_null_uids --delete"))
        else:
            self.stdout.write(self.style.SUCCESS("   ✅ All users have supabase_uid"))
    
    def check_orphaned_users(self):
        """Check for users without tenants."""
        self.stdout.write("\n2. Checking for users without tenants...")
        
        orphaned = SupabaseUser.objects.filter(tenant__isnull=True)
        count = orphaned.count()
        
        if count > 0:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Found {count} users without tenants"))
            for user in orphaned[:3]:
                self.stdout.write(f"      - {user.email}")
            self.stdout.write("   (This is OK if users haven't subscribed yet)")
        else:
            self.stdout.write(self.style.SUCCESS("   ✅ All users have tenants"))
    
    def check_tenants(self):
        """Check tenant statistics."""
        self.stdout.write("\n3. Checking tenants...")
        
        total = Tenant.objects.count()
        active = Tenant.objects.filter(status='active').count()
        trial = Tenant.objects.filter(status='trial').count()
        
        self.stdout.write(f"   Total tenants: {total}")
        self.stdout.write(f"   Active: {active}")
        self.stdout.write(f"   Trial: {trial}")
        
        # Check subscription distribution
        subs = Tenant.objects.values('subscribed_agents').annotate(count=Count('tenant_id'))
        self.stdout.write("   Subscriptions:")
        for sub in subs:
            self.stdout.write(f"      - {sub['subscribed_agents']}: {sub['count']}")
    
    def check_agent_configs(self):
        """Check agent configurations."""
        self.stdout.write("\n4. Checking agent configurations...")
        
        configs = AgentConfig.objects.all()
        mark_configs = configs.filter(agent_type='mark').count()
        hr_configs = configs.filter(agent_type='hr').count()
        
        self.stdout.write(f"   Marketing (n8n) configs: {mark_configs}")
        self.stdout.write(f"   HR (AWS) configs: {hr_configs}")
        
        # Check for configs without endpoints
        empty_configs = configs.filter(endpoint_url__isnull=True).count()
        if empty_configs > 0:
            self.stdout.write(self.style.WARNING(f"   ⚠️  {empty_configs} configs without endpoint_url"))
        else:
            self.stdout.write(self.style.SUCCESS("   ✅ All configs have endpoints"))
    
    def check_table_counts(self):
        """Check record counts in key tables."""
        self.stdout.write("\n5. Table record counts...")
        
        tables = [
            ('supabase_users', SupabaseUser),
            ('tenants', Tenant),
            ('agent_configs', AgentConfig),
        ]
        
        for name, model in tables:
            count = model.objects.count()
            self.stdout.write(f"   {name}: {count} records")
    
    def check_rls_status(self):
        """Check if RLS is enabled (PostgreSQL only)."""
        self.stdout.write("\n6. Checking RLS status...")
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT tablename, rowsecurity 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    AND tablename IN (
                        'supabase_users', 'tenants', 'agent_configs',
                        'login_attempts', 'refresh_tokens'
                    )
                    ORDER BY tablename;
                """)
                rows = cursor.fetchall()
                
                if rows:
                    self.stdout.write("   RLS Status:")
                    for table, rls in rows:
                        status = "✅ ON" if rls else "❌ OFF"
                        self.stdout.write(f"      {table}: {status}")
                else:
                    self.stdout.write("   (Could not check RLS)")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Could not check RLS: {e}"))


# Add Count import
from django.db.models import Count
