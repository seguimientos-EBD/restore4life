from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from generic import urls as generic_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('earthengine/', include('earthengine.urls')),
    path('areas/', include('areas.urls')),
    path('hydroperiod/', include('hydroperiod.urls')),
    path('', include(generic_urls)),
]

if settings.DEBUG:
    urlpatterns.append(re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}))
