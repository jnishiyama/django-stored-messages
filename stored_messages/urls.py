"""
At the moment this module does something only when restframework is available
"""

try:
    from django.conf.urls import patterns, url, include
    from rest_framework.routers import DefaultRouter

    from . import views

    router = DefaultRouter()
    router.register(r'inbox', views.InboxViewSet)

    urlpatterns = patterns(
        '',
        url(r'^', include(router.urls)),
    )
except ImportError:
    pass