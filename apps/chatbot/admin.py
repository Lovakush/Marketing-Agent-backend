from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import (
    ChatSession,
    ChatMessage,
    ConversationContext,
    BotPerformanceMetrics
)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """Admin interface for chat sessions with analytics"""
    
    list_display = [
        'session_id_short',
        'user_info',
        'status_badge',
        'total_messages',
        'is_qualified_lead',
        'interested_in_display',
        'created_at',
        'last_activity',
    ]
    
    list_filter = [
        'status',
        'is_qualified_lead',
        'created_at',
        'last_activity',
    ]
    
    search_fields = [
        'session_id',
        'user_name',
        'user_email',
        'company_name',
    ]
    
    readonly_fields = [
        'session_id',
        'created_at',
        'last_activity',
        'total_messages',
        'ip_address',
        'user_agent',
    ]
    
    fieldsets = (
        ('Session Information', {
            'fields': ('session_id', 'status', 'created_at', 'last_activity')
        }),
        ('User Information', {
            'fields': ('user_name', 'user_email', 'user_phone', 'company_name')
        }),
        ('Lead Qualification', {
            'fields': ('is_qualified_lead', 'interested_in', 'total_messages')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_qualified', 'archive_sessions', 'escalate_to_human']
    
    def session_id_short(self, obj):
        """Display shortened session ID"""
        return str(obj.session_id)[:8] + '...'
    session_id_short.short_description = 'Session'
    
    def user_info(self, obj):
        """Display user information"""
        parts = []
        if obj.user_name:
            parts.append(f"<b>{obj.user_name}</b>")
        if obj.user_email:
            parts.append(obj.user_email)
        if obj.company_name:
            parts.append(f"({obj.company_name})")
        
        return format_html(' '.join(parts)) if parts else '-'
    user_info.short_description = 'User'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'active': '#4CAF50',
            'qualified': '#2196F3',
            'archived': '#9E9E9E',
            'escalated': '#FF9800',
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def interested_in_display(self, obj):
        """Display interested products as badges"""
        if not obj.interested_in:
            return '-'
        
        badges = []
        for product in obj.interested_in:
            badges.append(
                f'<span style="background-color: #E8B84A; color: #2D1B4E; '
                f'padding: 2px 6px; border-radius: 3px; font-size: 10px; '
                f'margin-right: 3px;">{product}</span>'
            )
        
        return format_html(' '.join(badges))
    interested_in_display.short_description = 'Interested In'
    
    def mark_as_qualified(self, request, queryset):
        """Mark selected sessions as qualified leads"""
        updated = queryset.update(is_qualified_lead=True, status='qualified')
        self.message_user(request, f'{updated} sessions marked as qualified leads.')
    mark_as_qualified.short_description = 'Mark as qualified lead'
    
    def archive_sessions(self, request, queryset):
        """Archive selected sessions"""
        updated = queryset.update(status='archived')
        self.message_user(request, f'{updated} sessions archived.')
    archive_sessions.short_description = 'Archive sessions'
    
    def escalate_to_human(self, request, queryset):
        """Escalate sessions to human agent"""
        updated = queryset.update(status='escalated')
        self.message_user(request, f'{updated} sessions escalated to human.')
    escalate_to_human.short_description = 'Escalate to human'


class ChatMessageInline(admin.TabularInline):
    """Inline display of messages"""
    model = ChatMessage
    extra = 0
    fields = ['message_type', 'content_preview', 'timestamp', 'response_time_ms']
    readonly_fields = ['message_type', 'content_preview', 'timestamp', 'response_time_ms']
    can_delete = False
    
    def content_preview(self, obj):
        """Show preview of message content"""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for individual messages"""
    
    list_display = [
        'id',
        'session_link',
        'message_type_badge',
        'content_preview',
        'detected_intent',
        'confidence_score',
        'timestamp',
        'response_time_ms',
    ]
    
    list_filter = [
        'message_type',
        'detected_intent',
        'timestamp',
        'model_used',
    ]
    
    search_fields = [
        'content',
        'session__user_name',
        'session__user_email',
    ]
    
    readonly_fields = [
        'session',
        'timestamp',
        'response_time_ms',
        'model_used',
        'detected_intent',
        'confidence_score',
    ]
    
    fieldsets = (
        ('Message Information', {
            'fields': ('session', 'message_type', 'content', 'timestamp')
        }),
        ('AI Metadata', {
            'fields': ('model_used', 'response_time_ms', 'detected_intent', 'confidence_score')
        }),
    )
    
    def session_link(self, obj):
        """Link to session"""
        return format_html(
            '<a href="/admin/chatbot/chatsession/{}/change/">{}</a>',
            obj.session.session_id,
            str(obj.session.session_id)[:8] + '...'
        )
    session_link.short_description = 'Session'
    
    def message_type_badge(self, obj):
        """Display message type as badge"""
        colors = {
            'user': '#2196F3',
            'bot': '#4CAF50',
            'system': '#FF9800',
        }
        color = colors.get(obj.message_type, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.message_type.upper()
        )
    message_type_badge.short_description = 'Type'
    
    def content_preview(self, obj):
        """Show preview of message content"""
        preview = obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
        return preview
    content_preview.short_description = 'Message'


@admin.register(ConversationContext)
class ConversationContextAdmin(admin.ModelAdmin):
    """Admin interface for conversation contexts"""
    
    list_display = [
        'session_link',
        'current_step',
        'info_collection_status',
        'product_interests',
        'flags_display',
        'updated_at',
    ]
    
    list_filter = [
        'current_step',
        'has_name',
        'has_email',
        'has_company',
        'asked_for_demo',
        'asked_for_pricing',
    ]
    
    search_fields = [
        'session__user_name',
        'session__user_email',
    ]
    
    readonly_fields = [
        'session',
        'created_at',
        'updated_at',
    ]
    
    def session_link(self, obj):
        """Link to session"""
        return format_html(
            '<a href="/admin/chatbot/chatsession/{}/change/">{}</a>',
            obj.session.session_id,
            str(obj.session.session_id)[:8] + '...'
        )
    session_link.short_description = 'Session'
    
    def info_collection_status(self, obj):
        """Display info collection checkmarks"""
        checks = []
        if obj.has_name:
            checks.append('✓ Name')
        if obj.has_email:
            checks.append('✓ Email')
        if obj.has_company:
            checks.append('✓ Company')
        
        return ' | '.join(checks) if checks else 'No info collected'
    info_collection_status.short_description = 'Info Collected'
    
    def product_interests(self, obj):
        """Display product interests"""
        if obj.preferred_products:
            return ', '.join(obj.preferred_products)
        return '-'
    product_interests.short_description = 'Products'
    
    def flags_display(self, obj):
        """Display conversation flags"""
        flags = []
        if obj.asked_for_demo:
            flags.append('🎯 Demo')
        if obj.asked_for_pricing:
            flags.append('💰 Pricing')
        if obj.needs_human_handoff:
            flags.append('👤 Human')
        
        return ' '.join(flags) if flags else '-'
    flags_display.short_description = 'Flags'


@admin.register(BotPerformanceMetrics)
class BotPerformanceMetricsAdmin(admin.ModelAdmin):
    """Admin interface for bot performance metrics"""
    
    list_display = [
        'session_link',
        'avg_response_time_ms',
        'user_satisfaction_score',
        'conversion_indicators',
        'created_at',
    ]
    
    list_filter = [
        'converted_to_lead',
        'demo_booked',
        'escalation_required',
        'created_at',
    ]
    
    readonly_fields = [
        'session',
        'created_at',
    ]
    
    def session_link(self, obj):
        """Link to session"""
        return format_html(
            '<a href="/admin/chatbot/chatsession/{}/change/">{}</a>',
            obj.session.session_id,
            str(obj.session.session_id)[:8] + '...'
        )
    session_link.short_description = 'Session'
    
    def conversion_indicators(self, obj):
        """Display conversion indicators"""
        indicators = []
        if obj.converted_to_lead:
            indicators.append('✓ Lead')
        if obj.demo_booked:
            indicators.append('✓ Demo')
        if obj.escalation_required:
            indicators.append('⚠ Escalated')
        
        return ' | '.join(indicators) if indicators else '-'
    conversion_indicators.short_description = 'Conversions'


# Customize admin site
admin.site.site_header = 'SIA Chatbot Administration'
admin.site.site_title = 'SIA Chatbot Admin'
admin.site.index_title = 'Chatbot Management Dashboard'