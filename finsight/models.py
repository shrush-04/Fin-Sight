from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    """User profile model representing app users."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    monthly_income = db.Column(db.Float, default=0.0, nullable=False)
    currency = db.Column(db.String(10), default='INR', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    categories = db.relationship('Category', backref='user', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade="all, delete-orphan")
    budgets = db.relationship('Budget', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        """Hashes password using werkzeug.security."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks password against stored hash."""
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    """Transaction category model (Housing, Food, etc.) customized per user."""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'Income' or 'Expense'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transactions = db.relationship('Transaction', backref='category', lazy=True, cascade="all, delete-orphan")
    budgets = db.relationship('Budget', backref='category', lazy=True, cascade="all, delete-orphan")


class Transaction(db.Model):
    """Income or Expense transaction record."""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'Income' or 'Expense'
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    transaction_date = db.Column(db.Date, nullable=False)
    payment_mode = db.Column(db.String(50), nullable=False) # e.g. UPI, Card, Cash, Bank Transfer
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Budget(db.Model):
    """Category-level budget constraint for a specific month (YYYY-MM)."""
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(7), nullable=False) # YYYY-MM format
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
