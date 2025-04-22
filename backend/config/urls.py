from django.conf.urls import url, include
from rest_framework.routers import DefaultRouter

from app.gis.api.v4.urls import gis_router
from django.conf.urls.static import static
from django.conf import settings

router = DefaultRouter()

urlpatterns = [
    url(r'^api/v4/', include(gis_router.urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
