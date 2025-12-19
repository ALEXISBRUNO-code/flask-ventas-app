import os
from datetime import timedelta

class Config:
    # Configuración general
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu-clave-secreta-super-segura-cambiar-en-produccion'
    
    # Configuración de base de datos
    # Para desarrollo local (SQLite)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///techstore.db'
    
    # Para Azure SQL Database (se usará en producción)
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de sesión
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = False  # Cambiar a True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'