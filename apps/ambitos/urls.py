from django.urls import path

from ambitos import views

app_name = 'ambitos'

urlpatterns = [
    path('<int:pk>/', views.AmbitoDetailView.as_view(), name='detalle'),
    path('<int:pk>/geojson/', views.AmbitoGeoJSONView.as_view(), name='geojson'),
    path('humedales/<int:pk>/geojson/', views.HumedalGeoJSONView.as_view(), name='humedal-geojson'),
]
