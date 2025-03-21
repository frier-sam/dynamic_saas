import json
from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    """Model representing a conversation with context history"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional link to a module if this conversation is specific to a module
    module = models.ForeignKey(
        'modules.Module', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='conversations'
    )
    
    # Store additional context or state
    context = models.TextField(default='{}')
    
    def __str__(self):
        return f"{self.title} ({self.user.username})"
    
    def get_context(self):
        """Returns the context as a Python dictionary"""
        return json.loads(self.context)
    
    def set_context(self, context_dict):
        """Sets the context from a Python dictionary"""
        self.context = json.dumps(context_dict)
        self.save()
    
    def add_to_context(self, key, value):
        """Add or update a specific key in the context"""
        context = self.get_context()
        context[key] = value
        self.set_context(context)


class Message(models.Model):
    """Model representing a message in a conversation"""
    
    MESSAGE_TYPES = (
        ('user', 'User Message'),
        ('assistant', 'Assistant Message'),
        ('system', 'System Message'),
    )

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Store parsed actions from this message
    actions = models.TextField(default='[]')

    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.message_type} message in {self.conversation.title}"
    
    def get_actions(self):
        """Returns the actions as a Python list"""
        return json.loads(self.actions)
    
    def set_actions(self, actions_list):
        """Sets the actions from a Python list"""
        self.actions = json.dumps(actions_list)
        self.save()