from django.urls import path
from . import views
app_name = 'clients'

urlpatterns = [
    path('create/', views.create_client, name='create_client'),
]
