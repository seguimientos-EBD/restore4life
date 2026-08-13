from django.urls import path

from areas import views

app_name = 'areas'

urlpatterns = [
    path('<int:pk>/', views.StudyAreaDetailView.as_view(), name='detail'),
    path('<int:pk>/geojson/', views.StudyAreaGeoJSONView.as_view(), name='geojson'),
    path('<int:pk>/boundary/', views.StudyAreaBoundaryView.as_view(), name='boundary'),
    path('wetlands/<int:pk>/geojson/', views.WetlandGeoJSONView.as_view(), name='wetland-geojson'),
]
