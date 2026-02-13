import requests
import time
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
import logging
import re
import certifi

logger = logging.getLogger(__name__)

DEMO_BOOKING_LINK = "https://calendly.com/l-kush-ofiservices/sia"
DEMO_FALLBACK_EMAIL = "l.kush@ofiservices.com"


class ConversationFlowManager:
    """Manages conversation flow and required information collection."""
    
    CONVERSATION_STEPS = {
        'greeting': {'next': 'info_collection', 'required_info': []},
        'info_collection': {'next': 'product_discussion', 'required_info': ['name', 'email']},
        'product_discussion': {'next': 'qualification', 'required_info': []},
        'qualification': {'next': 'demo_booking', 'required_info': []},
        'demo_booking': {'next': 'completed', 'required_info': ['name', 'email', 'company']}
    }
    
    @classmethod
    def get_missing_info(cls, context) -> List[str]:
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
        return current_step in ['greeting', 'info_collection']
    
    @classmethod
    def get_next_step(cls, current_step: str, has_all_info: bool) -> str:
        if current_step == 'info_collection' and not has_all_info:
            return 'info_collection'
        step_config = cls.CONVERSATION_STEPS.get(current_step, {})
        return step_config.get('next', current_step)


class IntentDetector:
    """Detects user intent and extracts information from messages."""
    
    INTENT_PATTERNS = {
        'greeting': [r'\b(hi|hello|hey|greetings)\b'],
        'demo_request': [
            r'\b(demo|demonstration|book\s+demo|schedule\s+demo|see\s+demo|show\s+me)\b',
            r'\b(book|schedule|arrange)\b',
        ],
        'pricing_inquiry': [r'\b(price|pricing|cost|how\s+much|pricing\s+plan|subscription)\b'],
        'product_inquiry': [r'\b(argo|mark|consuelo|product|feature|capability|what\s+can)\b'],
        'goodbye': [r'\b(bye|goodbye|see\s+you|thanks|thank\s+you)\b'],
    }
    
    @classmethod
    def detect_intent(cls, message: str) -> Tuple[str, float]:
        message_lower = message.lower()
        for intent, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent, 0.85
        return 'general', 0.5
    
    @classmethod
    def extract_user_info(cls, message: str) -> Dict[str, Optional[str]]:
        info = {'name': None, 'email': None, 'company': None}
        
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            info['email'] = email_match.group(0)
        
        name_patterns = [
            r"(?:my name is|i'm|i am|this is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\s|$)",
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, message, re.IGNORECASE)
            if name_match:
                potential_name = name_match.group(1).strip()
                if potential_name.lower() not in ['yes', 'no', 'ok', 'sure', 'hello', 'hi', 'book', 'demo']:
                    info['name'] = potential_name.title()
                    break
        
        company_patterns = [
            r"(?:work at|from|company is|i work for|my company|company:|at)\s+([A-Z][A-Za-z0-9\s&.-]+?)(?:\s|$|\.|,)",
            r"(?:i(?:'m|\sam) (?:at|with|in))\s+([A-Z][A-Za-z0-9\s&.-]+?)(?:\s|$|\.|,)",
        ]
        for pattern in company_patterns:
            company_match = re.search(pattern, message, re.IGNORECASE)
            if company_match:
                potential_company = company_match.group(1).strip()
                if (len(potential_company) > 1 and 
                    potential_company.lower() not in ['gmail', 'yahoo', 'hotmail', 'outlook', 'the', 'a', 'an']):
                    potential_company = re.sub(r'[.,;!?]+$', '', potential_company)
                    info['company'] = potential_company.title()
                    break
        
        return info


class GeminiService:
    """AI service for generating chatbot responses using Google Gemini."""
    
    MODEL_NAME = "gemini-2.5-flash"
    
    SYSTEM_CONTEXT = f"""You are SIA Assistant - a professional AI chatbot for SIA (Sales Intelligence Agents).
You help users learn about our AI agents: ARGO (Sales), MARK (Marketing), and CONSUELO (HR).

CRITICAL RULES:
1. NEVER ask for information that's already collected (shown in context below each message)
2. When user requests a demo and you have all required info → provide booking link immediately
3. Keep responses concise (2-3 sentences)
4. Use user's name when you know it
5. Never say "how can I help?" after user already stated their need

DEMO BOOKING:
- Has name + email + company → Provide: {DEMO_BOOKING_LINK}
- Missing info → Ask only for missing info, then provide link
- Never ask for already collected information

RESPONSE STYLE:
- Professional and friendly
- Direct and efficient
- No unnecessary questions

Context format example:
[✓ ALREADY COLLECTED: Name: John, Email: john@example.com]
[✗ STILL NEED: company]
[🎯 DEMO REQUESTED → Ask for company, then provide link]

Always check the context provided with each user message."""

    @classmethod
    def build_conversation_history(cls, messages: List) -> List[Dict]:
        conversation = []
        for msg in messages:
            role = "user" if msg.message_type == "user" else "model"
            conversation.append({"role": role, "parts": [{"text": msg.content}]})
        return conversation
    
    @classmethod
    def build_context_enhanced_prompt(cls, user_message: str, session, context) -> str:
        context_parts = []
        
        known_info = []
        if session.user_name:
            known_info.append(f"Name: {session.user_name}")
        if session.user_email:
            known_info.append(f"Email: {session.user_email}")
        if session.company_name:
            known_info.append(f"Company: {session.company_name}")
        
        if known_info:
            context_parts.append(f"[✓ ALREADY COLLECTED: {', '.join(known_info)}]")
        
        missing_info = ConversationFlowManager.get_missing_info(context)
        if missing_info:
            context_parts.append(f"[✗ STILL NEED: {', '.join(missing_info)}]")
        else:
            context_parts.append("[✓ ALL BASIC INFO COLLECTED]")
        
        if context.preferred_products:
            context_parts.append(f"[📌 Interested in: {', '.join(context.preferred_products)}]")
        
        if context.asked_for_demo:
            if missing_info:
                context_parts.append(f"[🎯 DEMO REQUESTED → Ask for: {', '.join(missing_info)}, then provide link]")
            else:
                context_parts.append(f"[🎯 DEMO REQUESTED + ALL INFO COLLECTED → PROVIDE LINK NOW: {DEMO_BOOKING_LINK}]")
        
        if context_parts:
            context_block = "\n".join(context_parts)
            return f"{context_block}\n\nUser's message: {user_message}"
        
        return user_message
    
    @classmethod
    def generate_response(
        cls,
        user_message: str,
        session,
        context,
        conversation_history: List = None
    ) -> Tuple[str, int]:
        start_time = time.time()
        
        try:
            api_key = settings.GEMINI_API_KEY
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cls.MODEL_NAME}:generateContent?key={api_key}"
            
            headers = {'Content-Type': 'application/json'}
            
            history = []
            if conversation_history:
                history = cls.build_conversation_history(conversation_history)
            
            enhanced_message = cls.build_context_enhanced_prompt(user_message, session, context)
            
            history.append({"role": "user", "parts": [{"text": enhanced_message}]})
            
            payload = {
                "system_instruction": {"parts": [{"text": cls.SYSTEM_CONTEXT}]},
                "contents": history,
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 512,
                }
            }
            
            response = requests.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=30,
                verify=certifi.where()
            )
            response.raise_for_status()
            
            response_data = response.json()
            ai_response = response_data['candidates'][0]['content']['parts'][0]['text']
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return ai_response, response_time_ms
            
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error: {str(e)}")
            return "I'm experiencing a secure connection issue. Please try again.", 1000
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API Error: {str(e)}")
            return "I'm having trouble connecting. Please try again in a moment.", 1000
            
        except KeyError as e:
            logger.error(f"Response format error: {str(e)}")
            return "Sorry, I got confused. Could you rephrase that?", 1000
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return "Something went wrong. Let's try again.", 1000


class ConversationAnalyzer:
    """Analyzes conversations for lead qualification and metrics."""
    
    @classmethod
    def analyze_user_engagement(cls, session) -> Dict:
        return {
            'total_messages': session.total_messages,
            'duration': session.conversation_duration,
            'is_qualified': session.is_qualified_lead,
        }
    
    @classmethod
    def is_qualified_lead(cls, session, context) -> bool:
        has_all_info = (
            session.user_name and 
            session.user_email and 
            session.company_name
        )
        
        has_shown_interest = (
            context.asked_for_demo or 
            context.asked_for_pricing or 
            len(context.preferred_products) > 0
        )
        
        return has_all_info and has_shown_interest