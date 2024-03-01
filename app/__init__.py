from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from .settings import env

__all__ = ['app', 'db']

app = Flask(env('FLASK_APP_NAME', cast=str))
db:SQLAlchemy = SQLAlchemy(app)
