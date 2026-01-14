# models.py
from extensions          import db
from flask_login         import UserMixin
from datetime            import datetime

class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

class PdfHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String, nullable=False)
    json_path = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
