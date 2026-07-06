import os
import re
import datetime
import calendar
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from models import db, User, Category, Transaction, Budget

app = Flask(__name__)

# Core Secret Key for sessions
app.secret_key = os.environ.get('SECRET_KEY', 'finsight-secure-dev-session-key-992211')

# SQLite DB Path configuration inside project directory
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finsight.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

# Initialize DB structure within App Context
with app.app_context():
    db.create_all()


# --- DECORATORS & GLOBALS ---

def login_required(f):
    """Decorator to protect routes from unauthenticated users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def load_logged_in_user():
    """Hooks into each request to verify session state and populate global user context."""
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)


# --- AUTHENTICATION ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Renders registration form and processes new user creations with default categories."""
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        monthly_income_str = request.form.get('monthly_income', '0').strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or not re.match(EMAIL_REGEX, email):
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        try:
            monthly_income = float(monthly_income_str)
            if monthly_income < 0:
                errors.append("Monthly income cannot be negative.")
        except ValueError:
            errors.append("Monthly income must be a valid number.")

        if not errors:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                errors.append("Email is already registered.")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html')

        # Insert User
        user = User(name=name, email=email, monthly_income=monthly_income, currency='INR')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Seed default categories
        default_categories = [
            ('Housing', 'Expense'),
            ('Food & Dining', 'Expense'),
            ('Transportation', 'Expense'),
            ('Utilities', 'Expense'),
            ('Entertainment', 'Expense'),
            ('Others', 'Expense'),
            ('Income', 'Income')
        ]
        for cat_name, cat_type in default_categories:
            category = Category(user_id=user.id, name=cat_name, type=cat_type)
            db.session.add(category)
        db.session.commit()

        # Automatically log user in
        session['user_id'] = user.id
        flash("Registration successful! Welcome to FinSight.", "success")
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticates users via session cookie and redirects appropriately."""
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash("Logged in successfully!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logs the user out and wipes session keys."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


# --- MAIN PLATFORM ROUTES ---

@app.route('/')
@login_required
def dashboard():
    """Main Financial Dashboard presenting monthly insights, Chart.js metrics, and recent activity."""
    today = datetime.date.today()
    current_month_str = today.strftime('%Y-%m') # "YYYY-MM"

    # Define date range for current month
    start_date = datetime.date(today.year, today.month, 1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_date = datetime.date(today.year, today.month, last_day)

    # Monthly transactions list
    monthly_txs = Transaction.query.filter(
        Transaction.user_id == g.user.id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).all()

    # Calculations for summary cards
    total_income = sum(tx.amount for tx in monthly_txs if tx.type == 'Income')
    total_expenses = sum(tx.amount for tx in monthly_txs if tx.type == 'Expense')
    total_savings = total_income - total_expenses

    # Overall budget utilization calculation
    monthly_budgets = Budget.query.filter_by(user_id=g.user.id, month=current_month_str).all()
    budget_map = {b.category_id: b.amount for b in monthly_budgets}
    total_budgeted_amount = sum(budget_map.values())
    
    total_budgeted_expenses = sum(
        tx.amount for tx in monthly_txs 
        if tx.type == 'Expense' and tx.category_id in budget_map
    )
    
    budget_utilization = 0.0
    if total_budgeted_amount > 0:
        budget_utilization = (total_budgeted_expenses / total_budgeted_amount) * 100

    # Donut Chart Data: expense breakdown by category
    expense_categories_map = {}
    for tx in monthly_txs:
        if tx.type == 'Expense':
            cat_name = tx.category.name if tx.category else "Others"
            expense_categories_map[cat_name] = expense_categories_map.get(cat_name, 0.0) + tx.amount
    
    donut_labels = list(expense_categories_map.keys())
    donut_data = list(expense_categories_map.values())

    # Line Chart Data: daily income vs expenses over the last 30 days
    thirty_days_ago = today - datetime.timedelta(days=29)
    recent_30_days_txs = Transaction.query.filter(
        Transaction.user_id == g.user.id,
        Transaction.transaction_date >= thirty_days_ago,
        Transaction.transaction_date <= today
    ).all()

    dates_list = [thirty_days_ago + datetime.timedelta(days=i) for i in range(30)]
    line_labels = [d.strftime('%b %d') for d in dates_list]

    daily_income = {d: 0.0 for d in dates_list}
    daily_expense = {d: 0.0 for d in dates_list}

    for tx in recent_30_days_txs:
        if tx.transaction_date in daily_income:
            if tx.type == 'Income':
                daily_income[tx.transaction_date] += tx.amount
            else:
                daily_expense[tx.transaction_date] += tx.amount

    line_income_data = [daily_income[d] for d in dates_list]
    line_expense_data = [daily_expense[d] for d in dates_list]

    # Recent Transactions list (last 10 transactions)
    recent_transactions = Transaction.query.filter_by(user_id=g.user.id).order_by(
        Transaction.transaction_date.desc(), Transaction.id.desc()
    ).limit(10).all()

    return render_template(
        'dashboard.html',
        current_month_str=today.strftime('%B %Y'),
        total_income=total_income,
        total_expenses=total_expenses,
        total_savings=total_savings,
        budget_utilization=budget_utilization,
        donut_labels=donut_labels,
        donut_data=donut_data,
        line_labels=line_labels,
        line_income_data=line_income_data,
        line_expense_data=line_expense_data,
        recent_transactions=recent_transactions
    )


@app.route('/expenses', methods=['GET'])
@login_required
def expenses():
    """Displays user's transactions with support for filters (type, category, month)."""
    # Filters setup
    filter_type = request.args.get('type', 'All').strip()
    filter_category_str = request.args.get('category_id', 'All').strip()
    filter_month = request.args.get('month', 'All').strip()

    tx_query = Transaction.query.filter_by(user_id=g.user.id)

    if filter_type in ['Income', 'Expense']:
        tx_query = tx_query.filter(Transaction.type == filter_type)

    if filter_category_str != 'All':
        try:
            tx_query = tx_query.filter(Transaction.category_id == int(filter_category_str))
        except ValueError:
            pass

    if filter_month != 'All' and re.match(r'^\d{4}-\d{2}$', filter_month):
        year, month = map(int, filter_month.split('-'))
        last_day = calendar.monthrange(year, month)[1]
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year, month, last_day)
        tx_query = tx_query.filter(
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )

    # Sort primarily by transaction_date desc, and id desc for deterministic ordering
    all_transactions = tx_query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).all()

    # User categories for filters & forms
    categories = Category.query.filter_by(user_id=g.user.id).order_by(Category.name.asc()).all()

    # Distinct transaction months for selection filter
    all_tx_dates = db.session.query(Transaction.transaction_date).filter_by(
        user_id=g.user.id
    ).distinct().all()
    
    unique_months = sorted(
        list(set(d[0].strftime('%Y-%m') for d in all_tx_dates if d[0])),
        reverse=True
    )
    
    # Pre-populate default date for Add Transaction form as today
    today_str = datetime.date.today().strftime('%Y-%m-%d')

    return render_template(
        'expenses.html',
        transactions=all_transactions,
        categories=categories,
        filter_type=filter_type,
        filter_category_str=filter_category_str,
        filter_month=filter_month,
        unique_months=unique_months,
        today_str=today_str
    )


@app.route('/transactions/add', methods=['POST'])
@login_required
def add_transaction():
    """Adds a new transaction after validating category type correctness."""
    amount_str = request.form.get('amount', '0').strip()
    category_id_str = request.form.get('category_id', '').strip()
    tx_type = request.form.get('type', 'Expense').strip()
    date_str = request.form.get('transaction_date', '').strip()
    description = request.form.get('description', '').strip()
    payment_mode = request.form.get('payment_mode', 'Cash').strip()

    errors = []
    try:
        amount = float(amount_str)
        if amount <= 0:
            errors.append("Transaction amount must be greater than zero.")
    except ValueError:
        errors.append("Invalid transaction amount format.")

    try:
        category_id = int(category_id_str)
        category = Category.query.filter_by(id=category_id, user_id=g.user.id).first()
        if not category:
            errors.append("Selected category does not exist.")
    except ValueError:
        errors.append("Please select a valid category.")

    if tx_type not in ['Income', 'Expense']:
        errors.append("Invalid transaction type.")

    try:
        transaction_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        errors.append("Invalid date format. Use YYYY-MM-DD.")

    if not errors and category.type != tx_type:
        errors.append(f"Category '{category.name}' type is '{category.type}', which doesn't match selected type '{tx_type}'.")

    if errors:
        for error in errors:
            flash(error, 'danger')
    else:
        tx = Transaction(
            user_id=g.user.id,
            category_id=category.id,
            type=tx_type,
            amount=amount,
            description=description,
            transaction_date=transaction_date,
            payment_mode=payment_mode
        )
        db.session.add(tx)
        db.session.commit()
        flash("Transaction recorded successfully!", "success")

    return redirect(url_for('expenses'))


@app.route('/transactions/edit/<int:tx_id>', methods=['POST'])
@login_required
def edit_transaction(tx_id):
    """Modifies an existing transaction check validation values."""
    tx = Transaction.query.filter_by(id=tx_id, user_id=g.user.id).first_or_404()

    amount_str = request.form.get('amount', '0').strip()
    category_id_str = request.form.get('category_id', '').strip()
    tx_type = request.form.get('type', 'Expense').strip()
    date_str = request.form.get('transaction_date', '').strip()
    description = request.form.get('description', '').strip()
    payment_mode = request.form.get('payment_mode', 'Cash').strip()

    errors = []
    try:
        amount = float(amount_str)
        if amount <= 0:
            errors.append("Transaction amount must be greater than zero.")
    except ValueError:
        errors.append("Invalid transaction amount format.")

    try:
        category_id = int(category_id_str)
        category = Category.query.filter_by(id=category_id, user_id=g.user.id).first()
        if not category:
            errors.append("Selected category does not exist.")
    except ValueError:
        errors.append("Please select a valid category.")

    if tx_type not in ['Income', 'Expense']:
        errors.append("Invalid transaction type.")

    try:
        transaction_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        errors.append("Invalid date format. Use YYYY-MM-DD.")

    if not errors and category.type != tx_type:
        errors.append(f"Category '{category.name}' type is '{category.type}', which doesn't match selected type '{tx_type}'.")

    if errors:
        for error in errors:
            flash(error, 'danger')
    else:
        tx.amount = amount
        tx.category_id = category.id
        tx.type = tx_type
        tx.transaction_date = transaction_date
        tx.description = description
        tx.payment_mode = payment_mode
        db.session.commit()
        flash("Transaction updated successfully!", "success")

    return redirect(url_for('expenses'))


@app.route('/transactions/delete/<int:tx_id>', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    """Deletes a transaction."""
    tx = Transaction.query.filter_by(id=tx_id, user_id=g.user.id).first_or_404()
    db.session.delete(tx)
    db.session.commit()
    flash("Transaction deleted successfully!", "success")
    return redirect(url_for('expenses'))


@app.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    """Displays spending against budgeted categories and updates or creates new budget parameters."""
    if request.method == 'POST':
        category_id_str = request.form.get('category_id', '').strip()
        month = request.form.get('month', '').strip() # e.g. "YYYY-MM"
        amount_str = request.form.get('amount', '0').strip()

        errors = []
        try:
            category_id = int(category_id_str)
            category = Category.query.filter_by(id=category_id, user_id=g.user.id, type='Expense').first()
            if not category:
                errors.append("Budgets can only be created for Expense categories.")
        except ValueError:
            errors.append("Please select a valid category.")

        if not re.match(r'^\d{4}-\d{2}$', month):
            errors.append("Month must be in YYYY-MM format.")

        try:
            amount = float(amount_str)
            if amount <= 0:
                errors.append("Budget limit must be greater than zero.")
        except ValueError:
            errors.append("Invalid budget limit amount.")

        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            # Check for existing budget configs
            existing_budget = Budget.query.filter_by(
                user_id=g.user.id,
                category_id=category_id,
                month=month
            ).first()
            
            if existing_budget:
                existing_budget.amount = amount
                flash("Budget limit updated successfully!", "success")
            else:
                new_budget = Budget(
                    user_id=g.user.id,
                    category_id=category_id,
                    amount=amount,
                    month=month
                )
                db.session.add(new_budget)
                flash("Budget limit set successfully!", "success")
            db.session.commit()
            return redirect(url_for('budgets', month=month))

    # GET Filter Month setup (defaults to current month)
    filter_month = request.args.get('month', datetime.date.today().strftime('%Y-%m')).strip()
    if not re.match(r'^\d{4}-\d{2}$', filter_month):
        filter_month = datetime.date.today().strftime('%Y-%m')

    # Date ranges for budget month to evaluate actual expenses
    year, m = map(int, filter_month.split('-'))
    last_day = calendar.monthrange(year, m)[1]
    start_date = datetime.date(year, m, 1)
    end_date = datetime.date(year, m, last_day)

    user_budgets = Budget.query.filter_by(user_id=g.user.id, month=filter_month).all()

    budget_details = []
    for b in user_budgets:
        spent_sum = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.user_id == g.user.id,
            Transaction.category_id == b.category_id,
            Transaction.type == 'Expense',
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar()
        spent = spent_sum if spent_sum else 0.0
        
        percentage = (spent / b.amount) * 100 if b.amount > 0 else 0.0
        
        status_color = 'success'
        if percentage >= 100:
            status_color = 'danger'
        elif percentage >= 80:
            status_color = 'warning'

        budget_details.append({
            'budget': b,
            'category_name': b.category.name if b.category else "Others",
            'spent': spent,
            'percentage': percentage,
            'status_color': status_color
        })

    # Pull only expense categories for dropdown selection
    expense_categories = Category.query.filter_by(user_id=g.user.id, type='Expense').order_by(Category.name.asc()).all()

    # Get distinct months of budgets to show in filter dropdown
    all_budget_months = db.session.query(Budget.month).filter_by(
        user_id=g.user.id
    ).distinct().all()
    
    budget_months = sorted(
        list(set(bm[0] for bm in all_budget_months if bm[0])),
        reverse=True
    )
    if filter_month not in budget_months:
        budget_months.insert(0, filter_month)

    # Form defaults
    default_month = datetime.date.today().strftime('%Y-%m')

    return render_template(
        'budgets.html',
        budget_details=budget_details,
        expense_categories=expense_categories,
        filter_month=filter_month,
        budget_months=budget_months,
        default_month=default_month
    )


@app.route('/budgets/delete/<int:budget_id>', methods=['POST'])
@login_required
def delete_budget(budget_id):
    """Deletes a category budget limit entry."""
    budget = Budget.query.filter_by(id=budget_id, user_id=g.user.id).first_or_404()
    db.session.delete(budget)
    db.session.commit()
    flash("Budget deleted successfully!", "success")
    return redirect(url_for('budgets', month=budget.month))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Allows user to adjust visual profile and monthly settings variables."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        monthly_income_str = request.form.get('monthly_income', '0').strip()
        currency = request.form.get('currency', 'INR').strip()

        errors = []
        if not name:
            errors.append("Profile name cannot be blank.")
        try:
            monthly_income = float(monthly_income_str)
            if monthly_income < 0:
                errors.append("Monthly income cannot be negative.")
        except ValueError:
            errors.append("Invalid monthly income value.")

        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            g.user.name = name
            g.user.monthly_income = monthly_income
            g.user.currency = currency
            db.session.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('profile'))

    return render_template('profile.html')


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
