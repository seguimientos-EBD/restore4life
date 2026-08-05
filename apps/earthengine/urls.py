from django.urls import path

from earthengine import views

app_name = 'earthengine'

urlpatterns = [
    path('connect/', views.ConnectView.as_view(), name='connect'),
    path('authorize/', views.AuthorizeView.as_view(), name='authorize'),
    path('disconnect/', views.DisconnectView.as_view(), name='disconnect'),
]
