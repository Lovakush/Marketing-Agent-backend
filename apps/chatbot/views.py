from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.db import transaction
from django.conf import settings
from django.utils import timezone
import logging

from .models import ChatSession, ChatMessage, ConversationContext
from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatSessionSerializer,
    UserInfoUpdateSerializer,
)
from .services import (
    GeminiService,
    IntentDetector,
    ConversationFlowManager,
    ConversationAnalyzer,
)

logger = logging.getLogger(__name__)


class ChatBotRateThrottle(AnonRateThrottle):
    """Custom rate limiting for chatbot"""
    rate = '100/hour'  # 100 messages per hour per IP


@api_view(['POST'])
@throttle_classes([ChatBotRateThrottle])
def chatbot(request):
    """
    Main chatbot endpoint with conversation memory and context management.
    
    Handles:
    - Session creation/continuation
    - User information collection
    - Conversation history tracking
    - Intent detection
    - Lead qualification
    """
    
    # Validate incoming request
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                'success': False,
                'error': 'Invalid request',
                'details': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    user_message = validated_data['message']
    session_id = validated_data.get('session_id')
    
    try:
        with transaction.atomic():
            # Get or create session
            session, context = _get_or_create_session(
                session_id=session_id,
                request_data=validated_data,
                request=request
            )
            
            # Save user message
            user_msg_obj = ChatMessage.objects.create(
                session=session,
                message_type='user',
                content=user_message,
            )
            
            # Detect intent and extract information
            detected_intent, confidence = IntentDetector.detect_intent(user_message)
            user_msg_obj.detected_intent = detected_intent
            user_msg_obj.confidence_score = confidence
            user_msg_obj.save(update_fields=['detected_intent', 'confidence_score'])
            
            # Extract and update user information from message
            _extract_and_update_user_info(user_message, session, context)
            
            # Update conversation context based on intent
            _update_conversation_context(
                context=context,
                intent=detected_intent,
                message=user_message
            )
            
            # Get conversation history (last 10 messages for context)
            conversation_history = list(
                session.messages.all().order_by('timestamp')[:10]
            )
            
            # Generate AI response with full context
            ai_response, response_time_ms = GeminiService.generate_response(
                user_message=user_message,
                session=session,
                context=context,
                conversation_history=conversation_history[:-1]  # Exclude current message
            )
            
            # Save bot response
            bot_msg_obj = ChatMessage.objects.create(
                session=session,
                message_type='bot',
                content=ai_response,
                response_time_ms=response_time_ms,
                model_used=GeminiService.MODEL_NAME,
                parent_message=user_msg_obj,
            )
            
            # Update session metadata
            session.increment_message_count()
            
            # Check if user is now a qualified lead
            if ConversationAnalyzer.is_qualified_lead(session, context):
                session.is_qualified_lead = True
                session.status = 'qualified'
                session.save(update_fields=['is_qualified_lead', 'status'])
            
            # Determine what information is still needed
            missing_info = ConversationFlowManager.get_missing_info(context)
            
            # Build response
            response_data = {
                'success': True,
                'session_id': str(session.session_id),
                'message': user_message,
                'response': ai_response,
                'timestamp': bot_msg_obj.timestamp.isoformat(),
                'conversation_step': context.current_step,
                'needs_information': missing_info,
                'response_time_ms': response_time_ms,
            }
            
            # Add suggested actions based on context
            suggested_actions = _get_suggested_actions(context, detected_intent)
            if suggested_actions:
                response_data['suggested_actions'] = suggested_actions
            
            return Response(
                response_data,
                status=status.HTTP_200_OK
            )
            
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}", exc_info=True)
        
        return Response(
            {
                'success': False,
                'error': 'Failed to process your message. Please try again.',
                'details': str(e) if settings.DEBUG else None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def update_user_info(request):
    """
    Endpoint to explicitly update user information.
    Used when user provides info through form fields instead of chat.
    """
    serializer = UserInfoUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                'success': False,
                'error': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    session_id = validated_data['session_id']
    
    try:
        session = ChatSession.objects.get(session_id=session_id)
        context, _ = ConversationContext.objects.get_or_create(session=session)
        
        # Update user information
        if 'user_name' in validated_data:
            session.user_name = validated_data['user_name']
            context.has_name = True
        
        if 'user_email' in validated_data:
            session.user_email = validated_data['user_email']
            context.has_email = True
        
        if 'user_phone' in validated_data:
            session.user_phone = validated_data['user_phone']
        
        if 'company_name' in validated_data:
            session.company_name = validated_data['company_name']
            context.has_company = True
        
        session.save()
        context.save()
        
        return Response({
            'success': True,
            'message': 'User information updated successfully'
        })
        
    except ChatSession.DoesNotExist:
        return Response(
            {
                'success': False,
                'error': 'Session not found'
            },
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def get_session_info(request, session_id):
    """
    Get detailed information about a chat session.
    """
    try:
        session = ChatSession.objects.get(session_id=session_id)
        serializer = ChatSessionSerializer(session)
        
        return Response({
            'success': True,
            'session': serializer.data
        })
        
    except ChatSession.DoesNotExist:
        return Response(
            {
                'success': False,
                'error': 'Session not found'
            },
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
def reset_session(request):
    """
    Reset/archive a session and start fresh.
    """
    session_id = request.data.get('session_id')
    
    if not session_id:
        return Response(
            {
                'success': False,
                'error': 'session_id is required'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        session = ChatSession.objects.get(session_id=session_id)
        session.status = 'archived'
        session.save()
        
        return Response({
            'success': True,
            'message': 'Session archived. Start a new conversation with a new session.'
        })
        
    except ChatSession.DoesNotExist:
        return Response(
            {
                'success': False,
                'error': 'Session not found'
            },
            status=status.HTTP_404_NOT_FOUND
        )


# Helper Functions

def _get_or_create_session(session_id, request_data, request):
    """
    Get existing session or create a new one.
    Also creates associated ConversationContext.
    """
    if session_id:
        try:
            session = ChatSession.objects.get(session_id=session_id)
            context, _ = ConversationContext.objects.get_or_create(session=session)
            return session, context
        except ChatSession.DoesNotExist:
            pass  # Create new session below
    
    # Create new session
    session = ChatSession.objects.create(
        user_name=request_data.get('user_name'),
        user_email=request_data.get('user_email'),
        company_name=request_data.get('company_name'),
        ip_address=_get_client_ip(request),
        user_agent=request_data.get('user_agent') or request.META.get('HTTP_USER_AGENT', ''),
    )
    
    # Create conversation context
    context = ConversationContext.objects.create(
        session=session,
        current_step='greeting',
        has_name=bool(session.user_name),
        has_email=bool(session.user_email),
        has_company=bool(session.company_name),
    )
    
    return session, context


def _extract_and_update_user_info(message, session, context):
    """
    Extract user information from message and update session.
    """
    extracted_info = IntentDetector.extract_user_info(message)
    
    updated = False
    
    if extracted_info['name'] and not session.user_name:
        session.user_name = extracted_info['name']
        context.has_name = True
        updated = True
    
    if extracted_info['email'] and not session.user_email:
        session.user_email = extracted_info['email']
        context.has_email = True
        updated = True
    
    if extracted_info['company'] and not session.company_name:
        session.company_name = extracted_info['company']
        context.has_company = True
        updated = True
    
    if updated:
        session.save()
        context.save()


def _update_conversation_context(context, intent, message):
    """
    Update conversation context based on detected intent and message.
    """
    message_lower = message.lower()
    
    # Update flags based on intent
    if intent == 'demo_request':
        context.asked_for_demo = True
    
    if intent == 'pricing_inquiry':
        context.asked_for_pricing = True
    
    # Track product interests
    products = []
    if 'argo' in message_lower:
        products.append('ARGO')
    if 'mark' in message_lower:
        products.append('MARK')
    if 'consuelo' in message_lower:
        products.append('CONSUELO')
    
    if products:
        existing_products = set(context.preferred_products)
        existing_products.update(products)
        context.preferred_products = list(existing_products)
    
    # Update conversation step
    missing_info = ConversationFlowManager.get_missing_info(context)
    
    if missing_info and context.current_step == 'greeting':
        context.current_step = 'info_collection'
    elif not missing_info and context.current_step == 'info_collection':
        context.current_step = 'product_discussion'
    elif context.asked_for_demo and not missing_info:
        context.current_step = 'demo_booking'
    
    context.save()


def _get_suggested_actions(context, intent):
    """
    Get suggested quick reply actions based on context.
    """
    suggestions = []
    
    if intent == 'product_inquiry':
        if not context.preferred_products:
            suggestions = [
                "Tell me about ARGO",
                "Tell me about MARK",
                "Tell me about CONSUELO"
            ]
        else:
            suggestions = ["Book a demo", "See pricing", "Integration options"]
    
    elif intent == 'demo_request':
        suggestions = ["Yes, book a demo", "Tell me more first"]
    
    elif intent == 'pricing_inquiry':
        suggestions = ["Book a demo", "See features"]
    
    return suggestions


def _get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip