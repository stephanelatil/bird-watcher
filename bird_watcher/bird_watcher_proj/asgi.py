"""
ASGI config for bird_watcher_proj project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""
import os
from django.apps import apps
from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bird_watcher_proj.settings')
apps.populate(settings.INSTALLED_APPS)

from django.conf import settings
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.wsgi import WSGIMiddleware
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from birdwatcher.views import api_router
from birdwatcher.signals import delete_lock_file_on_delete

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Clean up
    delete_lock_file_on_delete()

def get_application() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/thumbnails", StaticFiles(directory="assets/thumbnails"), name="thumbnail")
    app.include_router(api_router, prefix="")
    app.mount("/", WSGIMiddleware(get_wsgi_application()))

    return app    

app = get_application()

@app.on_event("shutdown")
def shutdown_event():
    with open("log.txt", mode="a") as log:
        log.write("Application shutdown")