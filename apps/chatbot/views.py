from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
import requests

from .models import ChatMessage
from .serializers import ChatMessageSerializer
from .services import GeminiService


@api_view(['POST'])
@throttle_classes([AnonRateThrottle])
def chatbot(request):
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id', None)

        if not message:
            return Response(
                {
                    'success': False,
                    'error': 'Message is required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        ai_response = GeminiService.generate_response(message)

        chat_message = ChatMessage.objects.create(
            message=message,
            response=ai_response,
            session_id=session_id
        )

        return Response(
            {
                'success': True,
                'message': message,
                'response': ai_response,
                'timestamp': chat_message.timestamp
            },
            status=status.HTTP_200_OK
        )

    except requests.exceptions.RequestException as e:
        return Response(
            {
                'success': False,
                'error': 'Failed to connect to AI service. Please try again.',
                'details': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except KeyError as e:
        return Response(
            {
                'success': False,
                'error': 'Unexpected response from AI service.',
                'details': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {
                'success': False,
                'error': 'Failed to generate response. Please try again.',
                'details': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )