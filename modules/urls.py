from django.urls import path
from . import views

urlpatterns = [
    # Web views
    path('', views.module_list_view, name='module_list'),
    path('<int:module_id>/', views.module_detail_view, name='module_detail'),
    
    # API endpoints
    path('api/modules/', views.ModuleListAPI.as_view(), name='module_list_api'),
    path('api/modules/<int:module_id>/', views.ModuleDetailAPI.as_view(), name='module_detail_api'),
    path('api/modules/<int:module_id>/data/<str:table_name>/', views.module_data_api, name='module_data_api'),
    path('api/modules/<int:module_id>/data/<str:table_name>/<int:record_id>/', views.module_data_record_api, name='module_data_record_api'),
    path('api/modules/<int:module_id>/generate_ui/', views.generate_ui_api, name='generate_ui_api'),
]