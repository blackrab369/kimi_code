from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    user_identifier = db.Column(db.String(255), nullable=True) # GitHub username or session ID
    project_name = db.Column(db.String(255), nullable=False)
    idea_prompt = db.Column(db.Text, nullable=False)
    agents_data = db.Column(db.JSON, nullable=False) # Stores the full JSON result
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Project {self.project_name}>"

class User(db.Model):
    __tablename__ = 'users'
    
    username = db.Column(db.String(255), primary_key=True) # GitHub User or 'anonymous_ip'
    trial_start_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Subscription Fields
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), default=1) # 1 = Free
    subscription_id = db.Column(db.String(255), nullable=True) # Stripe/PayPal Sub ID
    subscription_status = db.Column(db.String(50), default='active') 
    
    # Usage Tracking
    credits_left = db.Column(db.Integer, default=1) # Free tier starts with 1
    voice_chars_left = db.Column(db.Integer, default=0)

    def days_left_in_trial(self):
        # Deprecated logic if using 'package_id', but useful for "Free Trial of Pro"
        delta = datetime.utcnow() - self.trial_start_date
        return max(0, 30 - delta.days)

class Package(db.Model):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False) # Free, Pro, Enterprise
    price = db.Column(db.Float, default=0.0)
    limit_builds = db.Column(db.Integer, default=1)
    limit_voice_chars = db.Column(db.Integer, default=0)
    features_json = db.Column(db.Text, default="[]") # JSON list of feature strings

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.username'))
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'))
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='completed') # pending, completed, failed
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    payment_provider_id = db.Column(db.String(255)) # PayPal Transaction ID

