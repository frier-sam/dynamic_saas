from django.urls import path
from .views import signup_view, profile_view, CustomLoginView, CustomLogoutView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('signup/', signup_view, name='signup'),
    path('profile/', profile_view, name='profile'),
]