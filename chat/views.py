from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from .models import Conversation, Message
from .chat_service import ChatService
from modules.models import Module

import json
import logging

logger = logging.getLogger(__name__)


@login_required
def chat_view(request, conversation_id=None):
    """
    Main chat interface view
    
    Args:
        request: HTTP request
        conversation_id (int, optional): ID of an existing conversation
        
    Returns:
        HttpResponse: Rendered template
    """
    user = request.user
    
    # If conversation ID is provided, get that conversation
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=user)
    else:
        # Get the most recent active conversation or create a new one
        conversation = Conversation.objects.filter(user=user, is_active=True).order_by('-updated_at').first()
        
        if not conversation:
            chat_service = ChatService()
            conversation = chat_service.create_conversation(user)
    
    # Get all conversations for the sidebar
    conversations = Conversation.objects.filter(user=user).order_by('-updated_at')
    
    # Get messages for the current conversation
    messages = conversation.messages.all()
    
    # Get modules for the sidebar
    modules = user.modules.all().order_by('-updated_at')
    
    return render(request, 'chat/chat.html', {
        'conversation': conversation,
        'conversations': conversations,
        'messages': messages,
        'modules': modules
    })


class ConversationListAPI(APIView):
    """API view for listing and creating conversations"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all conversations for the user"""
        conversations = Conversation.objects.filter(
            user=request.user
        ).order_by('-updated_at')
        
        # Serialize the conversations
        data = []
        for conv in conversations:
            data.append({
                'id': conv.id,
                'title': conv.title,
                'is_active': conv.is_active,
                'created_at': conv.created_at,
                'updated_at': conv.updated_at,
                'module_id': conv.module.id if conv.module else None,
                'module_name': conv.module.name if conv.module else None
            })
        
        return Response(data)
    
    def post(self, request):
        """Create a new conversation"""
        title = request.data.get('title')
        module_id = request.data.get('module_id')
        
        module = None
        if module_id:
            try:
                module = Module.objects.get(id=module_id, user=request.user)
            except Module.DoesNotExist:
                return Response(
                    {'error': 'Module not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        chat_service = ChatService()
        conversation = chat_service.create_conversation(
            user=request.user,
            title=title,
            module=module
        )
        
        return Response({
            'id': conversation.id,
            'title': conversation.title,
            'is_active': conversation.is_active,
            'created_at': conversation.created_at,
            'updated_at': conversation.updated_at,
            'module_id': conversation.module.id if conversation.module else None,
            'module_name': conversation.module.name if conversation.module else None
        }, status=status.HTTP_201_CREATED)


class ConversationDetailAPI(APIView):
    """API view for retrieving, updating, and deleting a conversation"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, conversation_id):
        """Get a specific conversation"""
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
            
            # Get the messages
            messages_data = []
            for msg in conversation.messages.all():
                messages_data.append({
                    'id': msg.id,
                    'message_type': msg.message_type,
                    'content': msg.content,
                    'created_at': msg.created_at,
                    'actions': msg.get_actions()
                })
            
            return Response({
                'id': conversation.id,
                'title': conversation.title,
                'is_active': conversation.is_active,
                'created_at': conversation.created_at,
                'updated_at': conversation.updated_at,
                'module_id': conversation.module.id if conversation.module else None,
                'module_name': conversation.module.name if conversation.module else None,
                'messages': messages_data,
                'context': conversation.get_context()
            })
            
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def patch(self, request, conversation_id):
        """Update a conversation"""
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
            
            # Update fields
            if 'title' in request.data:
                conversation.title = request.data['title']
            
            if 'is_active' in request.data:
                conversation.is_active = request.data['is_active']
            
            if 'module_id' in request.data:
                module_id = request.data['module_id']
                if module_id:
                    try:
                        module = Module.objects.get(id=module_id, user=request.user)
                        conversation.module = module
                    except Module.DoesNotExist:
                        return Response(
                            {'error': 'Module not found'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                else:
                    conversation.module = None
            
            conversation.save()
            
            return Response({
                'id': conversation.id,
                'title': conversation.title,
                'is_active': conversation.is_active,
                'created_at': conversation.created_at,
                'updated_at': conversation.updated_at,
                'module_id': conversation.module.id if conversation.module else None,
                'module_name': conversation.module.name if conversation.module else None
            })
            
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, conversation_id):
        """Delete a conversation"""
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
            
            conversation.delete()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, conversation_id):
    """
    Send a message to a conversation and get a response
    
    Args:
        request: HTTP request
        conversation_id (int): ID of the conversation
        
    Returns:
        Response: JSON response with the assistant's message
    """
    try:
        conversation = Conversation.objects.get(
            id=conversation_id,
            user=request.user
        )
        
        # Get the message content
        content = request.data.get('content')
        
        if not content:
            return Response(
                {'error': 'Message content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process the message
        chat_service = ChatService()
        response = chat_service.process_message(conversation, content)
        
        # Return the assistant's message
        assistant_message = response['message']
        return Response({
            'id': assistant_message.id,
            'message_type': assistant_message.message_type,
            'content': assistant_message.content,
            'created_at': assistant_message.created_at,
            'actions': assistant_message.get_actions(),
            'intent': response.get('intent')
        })
        
    except Conversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return Response(
            {'error': 'Error processing message'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )