"""
URL configuration for bird_watcher_proj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path
from django.views.generic.base import RedirectView
from birdwatcher.views import ThumbnailView, VideoListView, StreamVideoView, SingleVideoView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('thumbnail/<int:pk>.webp', ThumbnailView.as_view(), name='get-thumbnail'),
    re_path('videos/?', VideoListView.as_view(), name='video-list'),
    path('video/<int:pk>', SingleVideoView.as_view(), name='video-get'),
    re_path('video/(?P<pk>[1-9][0-9]*)/stream', StreamVideoView.as_view(), name='video-stream'),
    re_path('video/0/stream', StreamVideoView.as_view(), name='video-stream'),
    path(r'', RedirectView.as_view(url='videos', permanent=True), name='index')
]
