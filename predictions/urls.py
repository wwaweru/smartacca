from django.urls import path
from . import views

app_name = 'predictions'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('post-mortem/', views.post_mortem, name='post_mortem'),
]
