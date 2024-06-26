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
from birdwatcher.views import VideoListView, LiveStreamView, SingleVideoView, VideoTagView, ConfigView

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path('config/?', ConfigView.as_view(), name=ConfigView.url_name),
    re_path('videos/?', VideoListView.as_view(), name=VideoListView.url_name),
    path('video/<int:pk>/tag', VideoTagView.as_view(), name=VideoTagView.url_name),
    path('video/<int:pk>', SingleVideoView.as_view(), name='video-detail'),
    re_path('livestream/?', LiveStreamView.as_view(), name='video-livestream'),
    path(r'', RedirectView.as_view(url='videos', permanent=True), name='index')
]
