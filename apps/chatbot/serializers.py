from rest_framework import serializers
from .models import (
    ChatSession, 
    ChatMessage, 
    ConversationContext,
    BotPerformanceMetrics
)


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for individual chat messages"""
    
    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'message_type',
            'content',
            'timestamp',
            'response_time_ms',
            'detected_intent',
            'confidence_score',
        ]
        read_only_fields = [
            'id', 
            'timestamp', 
            'response_time_ms',
            'detected_intent',
            'confidence_score'
        ]


class ConversationContextSerializer(serializers.ModelSerializer):
    """Serializer for conversation context"""
    
    class Meta:
        model = ConversationContext
        fields = [
            'current_step',
            'has_name',
            'has_email',
            'has_company',
            'preferred_products',
            'pain_points',
            'asked_for_demo',
            'asked_for_pricing',
        ]
        read_only_fields = fields


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat sessions"""
    
    recent_messages = serializers.SerializerMethodField()
    context = ConversationContextSerializer(read_only=True)
    
    class Meta:
        model = ChatSession
        fields = [
            'session_id',
            'user_name',
            'user_email',
            'company_name',
            'status',
            'created_at',
            'last_activity',
            'total_messages',
            'is_qualified_lead',
            'interested_in',
            'recent_messages',
            'context',
        ]
        read_only_fields = [
            'session_id',
            'created_at',
            'last_activity',
            'total_messages',
        ]
    
    def get_recent_messages(self, obj):
        """Get last 5 messages"""
        messages = obj.messages.all()[:5]
        return ChatMessageSerializer(messages, many=True).data


class ChatRequestSerializer(serializers.Serializer):
    """Serializer for incoming chat requests"""
    
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=5000,
        error_messages={
            'required': 'Message is required',
            'blank': 'Message cannot be empty',
            'max_length': 'Message is too long (max 5000 characters)'
        }
    )
    
    session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Session ID for continuing conversation"
    )
    
    # Optional user information (can be provided upfront)
    user_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255
    )
    
    user_email = serializers.EmailField(
        required=False,
        allow_blank=True
    )
    
    company_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255
    )
    
    # Technical metadata
    user_agent = serializers.CharField(
        required=False,
        allow_blank=True
    )
    
    ip_address = serializers.IPAddressField(
        required=False,
        allow_null=True
    )


class ChatResponseSerializer(serializers.Serializer):
    """Serializer for chat responses"""
    
    success = serializers.BooleanField(default=True)
    
    session_id = serializers.UUIDField(
        help_text="Session ID for this conversation"
    )
    
    message = serializers.CharField(
        help_text="User's message"
    )
    
    response = serializers.CharField(
        help_text="Bot's response"
    )
    
    timestamp = serializers.DateTimeField(
        help_text="Response timestamp"
    )
    
    # Additional context
    conversation_step = serializers.CharField(
        required=False,
        help_text="Current step in conversation flow"
    )
    
    needs_information = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Information still needed from user (name, email, etc.)"
    )
    
    suggested_actions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Suggested quick replies or actions"
    )
    
    # Metadata
    response_time_ms = serializers.IntegerField(
        required=False,
        help_text="Response generation time"
    )


class UserInfoUpdateSerializer(serializers.Serializer):
    """Serializer for updating user information"""
    
    session_id = serializers.UUIDField(required=True)
    user_name = serializers.CharField(required=False, allow_blank=True)
    user_email = serializers.EmailField(required=False, allow_blank=True)
    user_phone = serializers.CharField(required=False, allow_blank=True)
    company_name = serializers.CharField(required=False, allow_blank=True)


class SessionStatsSerializer(serializers.Serializer):
    """Serializer for session statistics"""
    
    total_sessions = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    qualified_leads = serializers.IntegerField()
    avg_messages_per_session = serializers.FloatField()
    avg_response_time_ms = serializers.FloatField()
    conversion_rate = serializers.FloatField()