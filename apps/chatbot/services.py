import requests
import time
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
import logging
import re

logger = logging.getLogger(__name__)


# DEMO BOOKING CONFIGURATION
DEMO_BOOKING_LINK = "https://calendly.com/l-kush-ofiservices/sia"
DEMO_FALLBACK_EMAIL = "l.kush@ofiservices.com"


class ConversationFlowManager:
    """Manages conversation flow and determines what information to collect."""
    
    CONVERSATION_STEPS = {
        'greeting': {
            'next': 'info_collection',
            'required_info': []
        },
        'info_collection': {
            'next': 'product_discussion',
            'required_info': ['name', 'email']
        },
        'product_discussion': {
            'next': 'qualification',
            'required_info': []
        },
        'qualification': {
            'next': 'demo_booking',
            'required_info': []
        },
        'demo_booking': {
            'next': 'completed',
            'required_info': ['name', 'email', 'company']
        }
    }
    
    @classmethod
    def get_missing_info(cls, context) -> List[str]:
        """Determine what information is still needed"""
        missing = []
        
        if not context.has_name:
            missing.append('name')
        if not context.has_email:
            missing.append('email')
        if not context.has_company and context.asked_for_demo:
            missing.append('company')
            
        return missing
    
    @classmethod
    def should_collect_info(cls, current_step: str) -> bool:
        """Check if we should be collecting user info at this step"""
        return current_step in ['greeting', 'info_collection']
    
    @classmethod
    def get_next_step(cls, current_step: str, has_all_info: bool) -> str:
        """Determine the next conversation step"""
        if current_step == 'info_collection' and not has_all_info:
            return 'info_collection'
        
        step_config = cls.CONVERSATION_STEPS.get(current_step, {})
        return step_config.get('next', current_step)


class IntentDetector:
    """Detects user intent from messages."""
    
    INTENT_PATTERNS = {
        'demo_request': [
            'demo', 'demonstration', 'show me', 'can i see',
            'book a call', 'schedule', 'meeting', 'book', 'calendly',
            'appointment', 'talk to', 'speak with'
        ],
        'pricing_inquiry': [
            'price', 'cost', 'pricing', 'how much', 'expensive',
            'payment', 'subscription', 'plan', 'fee'
        ],
        'product_inquiry': [
            'argo', 'mark', 'consuelo', 'feature', 'what does',
            'how does', 'capability', 'can it', 'tell me about'
        ],
        'technical_question': [
            'integrate', 'api', 'technical', 'setup', 'implementation',
            'how long', 'install', 'deploy'
        ],
        'general_inquiry': [
            'what is', 'explain', 'help', 'hello', 'hi'
        ],
        'provide_info': [
            'my name is', 'i am', 'email', '@', 'company', 'work at', 'from'
        ],
        'confirmation': [
            'yes', 'sure', 'ok', 'yeah', 'yep', 'correct', 'right', 'exactly'
        ]
    }
    
    @classmethod
    def detect_intent(cls, message: str) -> Tuple[str, float]:
        """
        Detect the primary intent of the message.
        Returns: (intent, confidence_score)
        """
        message_lower = message.lower().strip()
        
        # Check for each intent
        intent_scores = {}
        
        for intent, patterns in cls.INTENT_PATTERNS.items():
            score = sum(1 for pattern in patterns if pattern in message_lower)
            if score > 0:
                intent_scores[intent] = score
        
        if not intent_scores:
            return 'general_inquiry', 0.5
        
        # Get intent with highest score
        detected_intent = max(intent_scores, key=intent_scores.get)
        max_score = intent_scores[detected_intent]
        
        # Calculate confidence (simple heuristic)
        confidence = min(max_score / 3.0, 1.0)
        
        return detected_intent, confidence
    
    @classmethod
    def extract_user_info(cls, message: str) -> Dict[str, Optional[str]]:
        """
        Extract user information from message (name, email, company).
        Returns dict with extracted info.
        """
        info = {
            'name': None,
            'email': None,
            'company': None
        }
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            info['email'] = email_match.group(0)
        
        # Extract name (improved patterns)
        name_patterns = [
            r"(?:my name is|i'm|i am|this is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\s|$)",
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, message, re.IGNORECASE)
            if name_match:
                potential_name = name_match.group(1).strip()
                # Filter out common false positives
                if potential_name.lower() not in ['yes', 'no', 'ok', 'sure', 'hello', 'hi']:
                    info['name'] = potential_name.title()
                    break
        
        # Extract company (improved patterns)
        company_patterns = [
            r"(?:work at|from|company is|i work for|my company|company:|at)\s+([A-Z][A-Za-z0-9\s&.-]+?)(?:\s|$|\.|,)",
            r"(?:i(?:'m|\sam) (?:at|with|in))\s+([A-Z][A-Za-z0-9\s&.-]+?)(?:\s|$|\.|,)",
        ]
        
        for pattern in company_patterns:
            company_match = re.search(pattern, message, re.IGNORECASE)
            if company_match:
                potential_company = company_match.group(1).strip()
                # Filter out common false positives and clean up
                if (len(potential_company) > 1 and 
                    potential_company.lower() not in ['gmail', 'yahoo', 'hotmail', 'outlook', 'the', 'a', 'an']):
                    # Remove trailing punctuation
                    potential_company = re.sub(r'[.,;!?]+$', '', potential_company)
                    info['company'] = potential_company.title()
                    break
        
        return info


class GeminiService:
    """Enhanced Gemini AI Service with conversation memory and context."""
    
    MODEL_NAME = "gemini-2.5-flash"
    
    # FIXED: Improved system context with strict instructions
    SYSTEM_CONTEXT = f"""
## Role & Identity
You are SIA Assistant - a professional AI chatbot for SIA (Sales Intelligence Agents).
You help users learn about our three AI agents: ARGO (Sales), MARK (Marketing), and CONSUELO (HR).

## CRITICAL RULES - FOLLOW STRICTLY

### 1. NEVER REPEAT INFORMATION USER ALREADY PROVIDED
- If user already told you their company name, NEVER ask again
- If you already have their email, DON'T ask for it again
- If you know their name, use it naturally but don't keep confirming it

### 2. DEMO BOOKING PROTOCOL
When user asks to book a demo:
- If you have name + email + company → Provide the demo link IMMEDIATELY
- Demo booking link: {DEMO_BOOKING_LINK}
- Format: "Perfect! Book your demo here: {DEMO_BOOKING_LINK}"
- NEVER say "I can help you book" without providing the actual link
- NEVER ask for availability - just give them the link to choose their time

### 3. CONVERSATION CONTEXT
- You will receive context about what you already know about the user
- Use this context to avoid repetition
- Be natural - don't sound robotic

### 4. INFORMATION COLLECTION (Only ask if NOT already collected)
Priority order:
1. Name (if missing) - "What's your name?"
2. Email (if missing) - "What's your email?"
3. Company (if missing AND they want demo) - "Which company are you with?"

### 5. TONE & STYLE
- Professional but friendly
- Concise - keep responses under 3-4 sentences
- No repetitive phrases like "Thanks, [Name]. So you're with [Company]"
- If you already acknowledged their company, DON'T repeat it

## Product Knowledge Base

### ARGO (Sales Agent)
- **Function**: Full-funnel sales automation from lead gen to signed quote
- **Impact**: Reps save 12 hours/week; +87% leads contacted; +45% meetings booked
- **Key Features**:
  * One-click lead generation
  * Real-time "Probability-to-Land" (P-to-L) ML scoring
  * Intelligent product matching
  * Auto-personalized emails
  * Self-learning loop
  * Manager dashboard with live analytics

### MARK (Marketing Agent)
- **Function**: Replaces/augments full marketing team
- **Impact**: +200% content/week; +82% engagement; -60% draft-to-publish time
- **Key Features**:
  * Live trend radar
  * Engagement predictor
  * Multi-platform AI post generator
  * Smart scheduler
  * Marketing coach
  * Unified campaign dashboard

### CONSUELO (HR/Talent Agent)  
- **Function**: Automates 80% of hiring
- **Impact**: +60% recruiter capacity; -65% time-to-shortlist; +18% offer acceptance
- **Key Features**:
  * Resume parser + AI fit scoring
  * Smart filter dashboard
  * Interview question generator
  * Auto tech-test grading
  * Real-time status alerts
  * Hiring insights panel

## Implementation
- **Timeline**: 15-min setup, 30-day deployment
- **Integrations**: HubSpot, Salesforce, Slack, Teams, Gmail, Pipedrive

## Response Examples

### BAD (Repetitive):
User: "My company is Acme Corp"
Bot: "Thanks, John. So you're with Acme Corp. What can I help you with?"
User: "Book a demo"
Bot: "Great! Just to confirm, you're with Acme Corp?"
❌ ANNOYING - already confirmed!

### GOOD (Natural):
User: "My company is Acme Corp"
Bot: "Perfect! Are you interested in ARGO, MARK, or CONSUELO?"
User: "Book a demo"
Bot: "Excellent! Book your demo here: {DEMO_BOOKING_LINK} - Choose a time that works for you!"
✅ HELPFUL - direct and efficient!

## Remember
- Check the context I give you - it shows what you already know
- Use demo link immediately when user wants to book
- Never repeat information unnecessarily
- Be helpful, not annoying
"""

    @classmethod
    def build_conversation_history(cls, messages: List) -> List[Dict]:
        """
        Build conversation history in Gemini's expected format.
        """
        conversation = []
        
        for msg in messages:
            role = "user" if msg.message_type == "user" else "model"
            conversation.append({
                "role": role,
                "parts": [{"text": msg.content}]
            })
        
        return conversation
    
    @classmethod
    def build_context_enhanced_prompt(
        cls,
        user_message: str,
        session,
        context
    ) -> str:
        """
        FIXED: Better context building - shows what we already know
        """
        context_parts = []
        
        # Show what we already have
        known_info = []
        if session.user_name:
            known_info.append(f"Name: {session.user_name}")
        if session.user_email:
            known_info.append(f"Email: {session.user_email}")
        if session.company_name:
            known_info.append(f"Company: {session.company_name}")
        
        if known_info:
            context_parts.append(f"[✓ Already collected: {', '.join(known_info)}]")
        
        # Show what we still need
        missing_info = ConversationFlowManager.get_missing_info(context)
        if missing_info:
            context_parts.append(f"[✗ Still need: {', '.join(missing_info)}]")
        else:
            context_parts.append("[✓ All basic info collected]")
        
        # Show interests
        if context.preferred_products:
            context_parts.append(f"[Interested in: {', '.join(context.preferred_products)}]")
        
        # Show demo request flag
        if context.asked_for_demo:
            if session.company_name:
                context_parts.append(f"[🎯 DEMO REQUESTED - USER HAS ALL INFO - PROVIDE LINK: {DEMO_BOOKING_LINK}]")
            else:
                context_parts.append("[🎯 DEMO REQUESTED - Need company name, then provide link]")
        
        # Combine with user message
        if context_parts:
            context_block = "\n".join(context_parts)
            return f"{context_block}\n\nUser: {user_message}"
        
        return user_message
    
    @classmethod
    def generate_response(
        cls,
        user_message: str,
        session,
        context,
        conversation_history: List = None
    ) -> Tuple[str, int]:
        """
        Generate AI response with full conversation context.
        """
        start_time = time.time()
        
        try:
            api_key = settings.GEMINI_API_KEY
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cls.MODEL_NAME}:generateContent?key={api_key}"
            
            headers = {'Content-Type': 'application/json'}
            
            # Build conversation history
            history = []
            if conversation_history:
                history = cls.build_conversation_history(conversation_history)
            
            # Enhanced message with context
            enhanced_message = cls.build_context_enhanced_prompt(
                user_message,
                session,
                context
            )
            
            # Add current user message
            history.append({
                "role": "user",
                "parts": [{"text": enhanced_message}]
            })
            
            payload = {
                "system_instruction": {
                    "parts": [{"text": cls.SYSTEM_CONTEXT}]
                },
                "contents": history,
                "generationConfig": {
                    "temperature": 0.7,  # Slightly lower for more consistent responses
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 512,  # Shorter responses
                }
            }
            
            response = requests.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=30
            )
            response.raise_for_status()
            
            response_data = response.json()
            ai_response = response_data['candidates'][0]['content']['parts'][0]['text']
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return ai_response, response_time_ms
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise
        except KeyError as e:
            logger.error(f"Unexpected Gemini response format: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise


class ConversationAnalyzer:
    """Analyzes conversations for insights and tracking."""
    
    @classmethod
    def analyze_user_engagement(cls, session) -> Dict:
        """Analyze user engagement metrics for a session."""
        from django.db.models import Avg
        messages = session.messages.all()
        
        return {
            'total_messages': messages.count(),
            'user_messages': messages.filter(message_type='user').count(),
            'bot_messages': messages.filter(message_type='bot').count(),
            'avg_response_time': messages.filter(
                message_type='bot',
                response_time_ms__isnull=False
            ).aggregate(avg_time=Avg('response_time_ms'))['avg_time'],
        }
    
    @classmethod
    def is_qualified_lead(cls, session, context) -> bool:
        """Determine if user is a qualified lead based on engagement."""
        criteria = {
            'has_contact_info': context.has_name and context.has_email,
            'showed_interest': len(context.preferred_products) > 0,
            'engaged_conversation': session.total_messages >= 3,
            'high_intent': context.asked_for_demo or context.asked_for_pricing,
        }
        
        # Lead is qualified if they meet at least 3 criteria
        return sum(criteria.values()) >= 3