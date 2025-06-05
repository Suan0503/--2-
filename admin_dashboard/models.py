from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(80))
