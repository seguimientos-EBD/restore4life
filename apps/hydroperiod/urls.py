from django.urls import path

from hydroperiod import views

app_name = 'hydroperiod'

# The area to analyse travels as a parameter, not in the path: it may be a wetland from
# the database or a shape drawn on the map, and only one of those has a primary key.
urlpatterns = [
    path('tiles/', views.TilesView.as_view(), name='tiles'),
    path('inspect/', views.InspectView.as_view(), name='inspect'),
    path('stats/', views.StatsView.as_view(), name='stats'),
    path('export/', views.ExportView.as_view(), name='export'),
]
