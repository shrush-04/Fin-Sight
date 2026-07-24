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
    investments = db.relationship('Investment', backref='user', lazy=True, cascade="all, delete-orphan")
    goals = db.relationship('Goal', backref='user', lazy=True, cascade="all, delete-orphan")
    cibil_scores = db.relationship('CibilScore', backref='user', lazy=True, cascade="all, delete-orphan")

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


class Investment(db.Model):
    """Investment holdings model."""
    __tablename__ = 'investments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    asset_type = db.Column(db.String(50), nullable=False) # Stock/Mutual Fund/ETF/Bond/Gold/Cash/Other
    asset_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    purchase_price = db.Column(db.Float, nullable=False, default=0.0)
    current_value = db.Column(db.Float, nullable=False, default=0.0)
    purchase_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    history = db.relationship('PortfolioHistory', backref='investment', lazy=True, cascade="all, delete-orphan")


class PortfolioHistory(db.Model):
    """Historical value snapshots for investments."""
    __tablename__ = 'portfolio_history'
    
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investments.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    units = db.Column(db.Float, nullable=False)
    nav_price = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Goal(db.Model):
    """Financial goal model."""
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    goal_name = db.Column(db.String(150), nullable=False)
    goal_type = db.Column(db.String(50), nullable=False) # Home/Retirement/Travel/Education/Other
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, nullable=False, default=0.0)
    target_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='On Track') # On Track/At Risk/Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    transactions = db.relationship('GoalTransaction', backref='goal', lazy=True, cascade="all, delete-orphan")


class GoalTransaction(db.Model):
    """Contributions toward a financial goal."""
    __tablename__ = 'goal_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Notification(db.Model):
    """Alerts and notifications for budgets, investments, goals, and system summaries."""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'Budget', 'Investment', 'Goal', 'System'
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CibilScore(db.Model):
    """Self-reported CIBIL Credit Score tracking model."""
    __tablename__ = 'cibil_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Integer, nullable=False) # 300-900 validation handled server-side
    recorded_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


