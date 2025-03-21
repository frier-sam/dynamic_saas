from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from modules.models import Module
from chat.models import Conversation


@login_required
def home_view(request):
    """
    Homepage view
    
    Args:
        request: HTTP request
        
    Returns:
        HttpResponse: Rendered template
    """
    # Get recent modules
    recent_modules = Module.objects.filter(
        user=request.user
    ).order_by('-updated_at')[:5]
    
    # Get recent conversations
    recent_conversations = Conversation.objects.filter(
        user=request.user
    ).order_by('-updated_at')[:5]
    
    return render(request, 'core/home.html', {
        'recent_modules': recent_modules,
        'recent_conversations': recent_conversations
    })


def landing_view(request):
    """
    Landing page for unauthenticated users
    
    Args:
        request: HTTP request
        
    Returns:
        HttpResponse: Rendered template
    """
    if request.user.is_authenticated:
        return redirect('home')
        
    return render(request, 'core/landing.html')