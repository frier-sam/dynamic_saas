from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, LoginForm
from django.contrib.auth.views import LoginView, LogoutView


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'users/login.html'


class CustomLogoutView(LogoutView):
    next_page = 'login'


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, f"Account created for {username}!")
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'users/signup.html', {'form': form})


@login_required
def profile_view(request):
    return render(request, 'users/profile.html')