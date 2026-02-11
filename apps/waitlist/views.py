from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.db import IntegrityError

from .models import Email
from .serializers import EmailSerializer


@api_view(['POST'])
@throttle_classes([AnonRateThrottle])
def join_waitlist(request):
    serializer = EmailSerializer(data=request.data)

    if serializer.is_valid():
        try:
            email_entry = serializer.save()
            return Response(
                {
                    'success': True,
                    'message': 'Successfully joined the waitlist!',
                    'email': email_entry.email
                },
                status=status.HTTP_201_CREATED
            )
        except IntegrityError:
            return Response(
                {
                    'success': False,
                    'error': 'This email is already on the waitlist'
                },
                status=status.HTTP_409_CONFLICT
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': 'Something went wrong. Please try again.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return Response(
        {
            'success': False,
            'error': serializer.errors
        },
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
def waitlist_stats(request):
    total_count = Email.objects.count()
    all_emails = Email.objects.all()
    serializer = EmailSerializer(all_emails, many=True)

    return Response({
        'total_subscribers': total_count,
        'subscribers': serializer.data
    })