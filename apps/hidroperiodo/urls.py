from django.urls import path

from hidroperiodo import views

app_name = 'hidroperiodo'

urlpatterns = [
    path('<int:humedal_pk>/teselas/', views.TeselasView.as_view(), name='teselas'),
]
