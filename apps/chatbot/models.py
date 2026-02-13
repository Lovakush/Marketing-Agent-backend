from django.db import models
from django.core.validators import EmailValidator
import uuid


class ChatSession(models.Model):
    """
    Represents a unique chat session for a user.
    Tracks user information and session metadata.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('qualified', 'Qualified Lead'),
        ('archived', 'Archived'),
        ('escalated', 'Escalated to Human'),
    ]
    
    session_id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique session identifier"
    )
    
    # User Information (collected during conversation)
    user_name = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="User's name"
    )
    user_email = models.EmailField(
        validators=[EmailValidator()],
        null=True, 
        blank=True,
        help_text="User's email for follow-up"
    )
    user_phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Optional phone number"
    )
    company_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="User's company name"
    )
    
    # Session Metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current session status"
    )
    
    # Tracking
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Session start time"
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last message time"
    )
    
    # Lead Qualification
    is_qualified_lead = models.BooleanField(
        default=False,
        help_text="Whether user is qualified for demo"
    )
    interested_in = models.JSONField(
        default=list,
        blank=True,
        help_text="Products/features user is interested in (ARGO, MARK, CONSUELO)"
    )
    
    # Technical
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="User's IP address"
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User's browser info"
    )
    
    # Analytics
    total_messages = models.IntegerField(
        default=0,
        help_text="Total messages in this session"
    )
    conversation_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Total time spent in conversation"
    )
    
    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['-last_activity']),
            models.Index(fields=['user_email']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        if self.user_name:
            return f"Session: {self.user_name} ({self.session_id})"
        return f"Session: {self.session_id}"
    
    def get_conversation_history(self, limit=10):
        """Get recent conversation history for context"""
        return self.messages.all()[:limit]
    
    def increment_message_count(self):
        """Increment total message counter"""
        self.total_messages += 1
        self.save(update_fields=['total_messages', 'last_activity'])


class ChatMessage(models.Model):
    """
    Individual messages within a chat session.
    Supports user messages, bot responses, and system messages.
    """
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User Message'),
        ('bot', 'Bot Response'),
        ('system', 'System Message'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Associated chat session"
    )
    
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='user',
        help_text="Type of message"
    )
    
    # Message Content
    content = models.TextField(
        help_text="Message content"
    )
    
    # Bot Response Metadata
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time taken to generate response (milliseconds)"
    )
    model_used = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        default='gemini-2.5-flash',
        help_text="AI model used for response"
    )
    
    # Intent Detection (for analytics)
    detected_intent = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Detected user intent (product_inquiry, pricing, demo_request, etc.)"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence score for intent detection (0-1)"
    )
    
    # Metadata
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Message timestamp"
    )
    
    # For tracking conversation flow
    parent_message = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replies',
        help_text="Parent message (for threading)"
    )
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['message_type']),
            models.Index(fields=['detected_intent']),
        ]

    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}... ({self.timestamp})"


class ConversationContext(models.Model):
    """
    Stores extracted context and state from ongoing conversations.
    Used for maintaining conversation flow and personalization.
    """
    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='context',
        help_text="Associated chat session"
    )
    
    # Conversation State
    current_step = models.CharField(
        max_length=50,
        default='greeting',
        help_text="Current conversation step (greeting, info_collection, product_discussion, etc.)"
    )
    
    # Information Collection Status
    has_name = models.BooleanField(default=False)
    has_email = models.BooleanField(default=False)
    has_company = models.BooleanField(default=False)
    
    # User Preferences & Interests
    preferred_products = models.JSONField(
        default=list,
        blank=True,
        help_text="List of products user showed interest in"
    )
    
    pain_points = models.JSONField(
        default=list,
        blank=True,
        help_text="User's mentioned pain points or challenges"
    )
    
    questions_asked = models.JSONField(
        default=list,
        blank=True,
        help_text="Topics/questions user has asked about"
    )
    
    # Conversation Flags
    asked_for_demo = models.BooleanField(
        default=False,
        help_text="User requested a demo"
    )
    asked_for_pricing = models.BooleanField(
        default=False,
        help_text="User asked about pricing"
    )
    needs_human_handoff = models.BooleanField(
        default=False,
        help_text="Conversation needs human intervention"
    )
    
    # Custom data storage
    custom_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional custom context data"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'conversation_contexts'
    
    def __str__(self):
        return f"Context for {self.session}"
    
    def update_step(self, new_step):
        """Update the current conversation step"""
        self.current_step = new_step
        self.save(update_fields=['current_step', 'updated_at'])
    
    def mark_info_collected(self, info_type):
        """Mark that a specific piece of information has been collected"""
        if info_type == 'name':
            self.has_name = True
        elif info_type == 'email':
            self.has_email = True
        elif info_type == 'company':
            self.has_company = True
        self.save(update_fields=[f'has_{info_type}', 'updated_at'])


class BotPerformanceMetrics(models.Model):
    """
    Track bot performance metrics for analytics and optimization.
    """
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    # Response Quality
    avg_response_time_ms = models.FloatField(
        null=True,
        help_text="Average response time in milliseconds"
    )
    
    # User Engagement
    user_satisfaction_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="User satisfaction rating (1-5)"
    )
    
    escalation_required = models.BooleanField(
        default=False,
        help_text="Whether conversation needed human escalation"
    )
    
    # Conversion Tracking
    converted_to_lead = models.BooleanField(
        default=False,
        help_text="Whether user became a qualified lead"
    )
    demo_booked = models.BooleanField(
        default=False,
        help_text="Whether user booked a demo"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bot_performance_metrics'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Metrics for {self.session}"