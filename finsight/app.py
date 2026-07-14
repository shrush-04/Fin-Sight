import os
import re
import datetime
import calendar
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from models import db, User, Category, Transaction, Budget, Investment, PortfolioHistory, Goal, GoalTransaction

# --- OCR IMPORTS (optional; graceful fallback if not installed) ---
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    from PIL import Image
    # Windows users: set the path to the Tesseract binary if needed.
   
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

app = Flask(__name__)

# Core Secret Key for sessions
app.secret_key = os.environ.get('SECRET_KEY', 'finsight-secure-dev-session-key-992211')

# SQLite DB Path configuration inside project directory
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finsight.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Receipt upload configuration
RECEIPT_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'receipts')
os.makedirs(RECEIPT_UPLOAD_FOLDER, exist_ok=True)
ALLOWED_RECEIPT_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_RECEIPT_SIZE_MB = 10

db.init_app(app)

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'


# --- OCR HELPER FUNCTIONS ---

def allowed_receipt_file(filename):
    """Validates that the uploaded file has an accepted image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_RECEIPT_EXTENSIONS


def guess_category_from_merchant(merchant_name, categories):
    """
    Applies simple keyword heuristics to guess the best matching expense
    category from the user's category list based on merchant/payee name.
    """
    name_lower = merchant_name.lower()

    keyword_map = [
        (['swiggy', 'zomato', 'restaurant', 'cafe', 'food', 'pizza', 'burger', 'biryani', 'kitchen', 'dhaba', 'eatery', 'bakery'], 'Food & Dining'),
        (['uber', 'ola', 'metro', 'rapido', 'bus', 'train', 'flight', 'airways', 'petrol', 'fuel', 'irctc', 'indigo', 'air india'], 'Transportation'),
        (['electricity', 'water', 'gas', 'broadband', 'internet', 'bill', 'recharge', 'airtel', 'jio', 'bsnl', 'vi ', 'vodafone', 'tata power', 'bescom', 'msedcl'], 'Utilities'),
        (['netflix', 'spotify', 'amazon prime', 'hotstar', 'zee5', 'sonyliv', 'movie', 'cinema', 'pvr', 'inox', 'bookmyshow', 'gaming', 'game'], 'Entertainment'),
        (['rent', 'housing', 'flat', 'apartment', 'maintenance', 'society'], 'Housing'),
    ]

    # Try to find a matching user category by keyword
    for keywords, cat_name in keyword_map:
        if any(kw in name_lower for kw in keywords):
            for cat in categories:
                if cat.type == 'Expense' and cat.name.lower() == cat_name.lower():
                    return cat

    # Fallback: return the first 'Others' expense category
    for cat in categories:
        if cat.type == 'Expense' and cat.name.lower() == 'others':
            return cat

    # Final fallback: first expense category available
    for cat in categories:
        if cat.type == 'Expense':
            return cat

    return None


def parse_ocr_text(ocr_text):
    """
    Parses raw OCR text and extracts:
      - amount (float or None)
      - merchant (str or '')
      - date (str in YYYY-MM-DD or '')
      - gst_amount (float or None)
    Returns a dict with those keys plus 'amount_confident' bool.
    """
    result = {
        'amount': None,
        'amount_confident': False,
        'merchant': '',
        'date': '',
        'gst_amount': None,
    }

    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]

    # --- Amount extraction ---
    # Priority 1: patterns like "Total: ₹1,234.50" / "Amount Paid ₹999"
    total_patterns = [
        r'(?:total|amount\s*paid|grand\s*total|net\s*amount|amt\s*paid)[\s:₹Rs.INR]*([\d,]+(?:\.\d{1,2})?)',
        r'[₹Rs\.INR]+\s*([\d,]+(?:\.\d{1,2})?)',
        r'([\d,]+(?:\.\d{1,2})?)\s*(?:INR|Rs|₹)',
    ]
    for pattern in total_patterns:
        matches = re.findall(pattern, ocr_text, re.IGNORECASE)
        if matches:
            # Take the largest numeric match (most likely to be the total)
            candidates = []
            for m in matches:
                try:
                    candidates.append(float(m.replace(',', '')))
                except ValueError:
                    pass
            if candidates:
                result['amount'] = max(candidates)
                result['amount_confident'] = True
                break

    # --- Date extraction ---
    date_patterns = [
        r'(?:date[:\s]*)?(\d{2}[\-/]\d{2}[\-/]\d{4})',  # dd-mm-yyyy or dd/mm/yyyy
        r'(?:date[:\s]*)?(\d{4}[\-/]\d{2}[\-/]\d{2})',  # yyyy-mm-dd
        r'(?:date[:\s]*)?([\d]{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})',  # 14 Jul 2025
    ]
    for pattern in date_patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            raw_date = match.group(1).strip()
            parsed_date = None
            for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
                try:
                    parsed_date = datetime.datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue
            if parsed_date:
                result['date'] = parsed_date.strftime('%Y-%m-%d')
                break

    # --- GST / CGST / SGST extraction ---
    gst_pattern = r'(?:GST|CGST|SGST|IGST)[\s:₹Rs.INR]*([\d,]+(?:\.\d{1,2})?)'
    gst_matches = re.findall(gst_pattern, ocr_text, re.IGNORECASE)
    if gst_matches:
        gst_vals = []
        for m in gst_matches:
            try:
                gst_vals.append(float(m.replace(',', '')))
            except ValueError:
                pass
        if gst_vals:
            result['gst_amount'] = sum(gst_vals)

    # --- Merchant / payee extraction ---
    # Strategy 1: look for "Paid to" or "To:" patterns
    paid_to_match = re.search(r'(?:paid\s*to|to)[:\s]+([^\n\d]{3,50})', ocr_text, re.IGNORECASE)
    if paid_to_match:
        result['merchant'] = paid_to_match.group(1).strip()
    else:
        # Strategy 2: use the first non-empty, non-numeric line (usually the merchant header)
        for line in lines[:5]:
            if len(line) >= 3 and not re.match(r'^[\d\s₹Rs.,:/\-]+$', line):
                result['merchant'] = line
                break

    # Sanitize merchant name length
    if result['merchant']:
        result['merchant'] = result['merchant'][:100]

    return result

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
def home():
    """Renders the landing page if not logged in, or redirects to the dashboard."""
    if 'user_id' in session and g.user:
        return redirect(url_for('dashboard'))
    return render_template('home.html')


@app.route('/dashboard')
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

    # Net savings (lifetime calculation) or savings from transaction history
    all_income = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=g.user.id, type='Income').scalar() or 0.0
    all_expenses = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=g.user.id, type='Expense').scalar() or 0.0
    lifetime_savings = all_income - all_expenses

    # Total current value of investments
    total_investments_val = db.session.query(db.func.sum(Investment.current_value)).filter_by(user_id=g.user.id).scalar() or 0.0
    
    # Net Worth = Lifetime Savings + Total Investments Current Value
    net_worth = lifetime_savings + total_investments_val

    # Active Goals count (status != 'Completed')
    active_goals_count = Goal.query.filter(Goal.user_id == g.user.id, Goal.status != 'Completed').count()

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
        recent_transactions=recent_transactions,
        net_worth=net_worth,
        active_goals_count=active_goals_count
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


# --- RECEIPT OCR ROUTES ---

@app.route('/receipts/scan', methods=['POST'])
@login_required
def scan_receipt():
    """
    Accepts an uploaded receipt image, runs Tesseract OCR on it,
    extracts structured fields, and returns a JSON payload for
    the frontend review form.
    """
    if not OCR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'OCR engine not available. Please install pytesseract and Pillow (pip install pytesseract Pillow) and ensure Tesseract is installed on the system.'
        }), 500

    if 'receipt' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded.'}), 400

    file = request.files['receipt']
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected.'}), 400

    if not allowed_receipt_file(file.filename):
        return jsonify({'success': False, 'error': 'Unsupported file type. Please upload a JPEG or PNG image.'}), 400

    # Save the file with a unique timestamped name
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'receipt_{g.user.id}_{int(datetime.datetime.utcnow().timestamp())}.{ext}'
    save_path = os.path.join(RECEIPT_UPLOAD_FOLDER, unique_name)

    try:
        file.save(save_path)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to save the uploaded file: {str(e)}'}), 500

    # Run Tesseract OCR
    try:
        img = Image.open(save_path)
        # Use a Tesseract config that works well with receipts
        ocr_config = r'--oem 3 --psm 6'
        ocr_text = pytesseract.image_to_string(img, config=ocr_config)
    except pytesseract.TesseractNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Tesseract OCR engine not found. Windows users: install it from https://github.com/UB-Mannheim/tesseract/wiki and set the path in app.py if needed.'
        }), 500
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to read the image: {str(e)}'}), 500

    # Parse the OCR text
    parsed = parse_ocr_text(ocr_text)

    # Build category guess
    categories = Category.query.filter_by(user_id=g.user.id, type='Expense').order_by(Category.name.asc()).all()
    guessed_category = guess_category_from_merchant(parsed['merchant'], categories)

    # Build the thumbnail URL (served via /static/)
    thumbnail_url = url_for('static', filename=f'uploads/receipts/{unique_name}')

    return jsonify({
        'success': True,
        'amount': parsed['amount'],
        'amount_confident': parsed['amount_confident'],
        'merchant': parsed['merchant'],
        'date': parsed['date'] or datetime.date.today().strftime('%Y-%m-%d'),
        'gst_amount': parsed['gst_amount'],
        'guessed_category_id': guessed_category.id if guessed_category else None,
        'thumbnail_url': thumbnail_url,
        'ocr_text_preview': ocr_text[:500]  # helpful for debugging
    })


@app.route('/receipts/confirm', methods=['POST'])
@login_required
def confirm_receipt():
    """
    Saves the user-reviewed/corrected OCR-extracted data as a normal
    Expense transaction — identical to the manual add_transaction flow.
    """
    amount_str = request.form.get('amount', '0').strip()
    category_id_str = request.form.get('category_id', '').strip()
    date_str = request.form.get('transaction_date', '').strip()
    description = request.form.get('description', '').strip()
    payment_mode = request.form.get('payment_mode', 'UPI').strip()

    errors = []
    try:
        amount = float(amount_str)
        if amount <= 0:
            errors.append('Transaction amount must be greater than zero.')
    except ValueError:
        errors.append('Invalid transaction amount.')

    try:
        category_id = int(category_id_str)
        category = Category.query.filter_by(id=category_id, user_id=g.user.id, type='Expense').first()
        if not category:
            errors.append('Selected category is invalid.')
    except ValueError:
        errors.append('Please select a valid expense category.')

    try:
        transaction_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        errors.append('Invalid date format.')

    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('expenses'))

    tx = Transaction(
        user_id=g.user.id,
        category_id=category.id,
        type='Expense',
        amount=amount,
        description=description,
        transaction_date=transaction_date,
        payment_mode=payment_mode
    )
    db.session.add(tx)
    db.session.commit()
    flash('Receipt transaction saved successfully!', 'success')
    return redirect(url_for('expenses'))


# --- INVESTMENTS PORTFOLIO ROUTES ---

@app.route('/investments', methods=['GET', 'POST'])
@login_required
def investments():
    """Displays holdings, handles new investments addition, displays asset allocation and history."""
    if request.method == 'POST':
        asset_type = request.form.get('asset_type', '').strip()
        asset_name = request.form.get('asset_name', '').strip()
        quantity_str = request.form.get('quantity', '0').strip()
        purchase_price_str = request.form.get('purchase_price', '0').strip()
        current_value_str = request.form.get('current_value', '').strip()
        purchase_date_str = request.form.get('purchase_date', '').strip()

        errors = []
        if not asset_type or asset_type not in ['Stock', 'Mutual Fund', 'ETF', 'Bond', 'Gold', 'Cash', 'Other']:
            errors.append("Please select a valid asset type.")
        if not asset_name:
            errors.append("Asset name is required.")
        
        try:
            quantity = float(quantity_str)
            if quantity <= 0:
                errors.append("Quantity must be greater than zero.")
        except ValueError:
            errors.append("Invalid quantity format.")

        try:
            purchase_price = float(purchase_price_str)
            if purchase_price <= 0:
                errors.append("Purchase price must be greater than zero.")
        except ValueError:
            errors.append("Invalid purchase price format.")

        if not current_value_str:
            # Default to quantity * purchase_price if current value is blank
            current_value = quantity * purchase_price
        else:
            try:
                current_value = float(current_value_str)
                if current_value < 0:
                    errors.append("Current value cannot be negative.")
            except ValueError:
                errors.append("Invalid current value format.")

        try:
            purchase_date = datetime.datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
        except ValueError:
            errors.append("Invalid purchase date format. Use YYYY-MM-DD.")

        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            inv = Investment(
                user_id=g.user.id,
                asset_type=asset_type,
                asset_name=asset_name,
                quantity=quantity,
                purchase_price=purchase_price,
                current_value=current_value,
                purchase_date=purchase_date
            )
            db.session.add(inv)
            db.session.commit()

            # Record initial portfolio history snapshot
            hist = PortfolioHistory(
                investment_id=inv.id,
                date=datetime.date.today(),
                units=quantity,
                nav_price=current_value / quantity,
                total_value=current_value
            )
            db.session.add(hist)
            db.session.commit()

            flash("Investment holding recorded successfully!", "success")
            return redirect(url_for('investments'))

    # Load holdings
    holdings = Investment.query.filter_by(user_id=g.user.id).order_by(Investment.asset_name.asc()).all()

    # Calculations for summary cards
    total_invested = 0.0
    total_current_val = 0.0

    # Donut Chart Allocation data
    allocation_map = {}

    for h in holdings:
        invested = h.quantity * h.purchase_price
        total_invested += invested
        total_current_val += h.current_value
        
        allocation_map[h.asset_type] = allocation_map.get(h.asset_type, 0.0) + h.current_value

    overall_return_amt = total_current_val - total_invested
    overall_return_pct = 0.0
    if total_invested > 0:
        overall_return_pct = (overall_return_amt / total_invested) * 100

    donut_labels = list(allocation_map.keys())
    donut_data = list(allocation_map.values())

    # Line Chart: Portfolio Performance Over Time
    # Query history entries grouped by date
    history_records = db.session.query(
        PortfolioHistory.date,
        db.func.sum(PortfolioHistory.total_value)
    ).join(Investment).filter(Investment.user_id == g.user.id)\
     .group_by(PortfolioHistory.date)\
     .order_by(PortfolioHistory.date.asc()).all()

    line_labels = []
    line_data = []

    if history_records:
        for r in history_records:
            line_labels.append(r[0].strftime('%b %d, %Y'))
            line_data.append(round(r[1], 2))
    else:
        # Fallback if no history records exist yet
        line_labels = [datetime.date.today().strftime('%b %d, %Y')]
        line_data = [round(total_current_val, 2)]

    today_str = datetime.date.today().strftime('%Y-%m-%d')

    return render_template(
        'investments.html',
        holdings=holdings,
        total_invested=total_invested,
        total_current_val=total_current_val,
        overall_return_amt=overall_return_amt,
        overall_return_pct=overall_return_pct,
        donut_labels=donut_labels,
        donut_data=donut_data,
        line_labels=line_labels,
        line_data=line_data,
        today_str=today_str
    )


@app.route('/investments/update_value/<int:inv_id>', methods=['POST'])
@login_required
def update_investment_value(inv_id):
    """Updates the current value of a holding and appends a PortfolioHistory record."""
    inv = Investment.query.filter_by(id=inv_id, user_id=g.user.id).first_or_404()
    current_value_str = request.form.get('current_value', '0').strip()

    try:
        current_value = float(current_value_str)
        if current_value < 0:
            flash("Current value cannot be negative.", "danger")
            return redirect(url_for('investments'))
    except ValueError:
        flash("Invalid current value format.", "danger")
        return redirect(url_for('investments'))

    inv.current_value = current_value
    inv.updated_at = datetime.datetime.utcnow()

    # Append to history for the date
    # Check if a record already exists for today to update it, or create a new one
    today = datetime.date.today()
    existing_hist = PortfolioHistory.query.filter_by(investment_id=inv.id, date=today).first()
    if existing_hist:
        existing_hist.units = inv.quantity
        existing_hist.nav_price = current_value / inv.quantity if inv.quantity > 0 else 0
        existing_hist.total_value = current_value
    else:
        hist = PortfolioHistory(
            investment_id=inv.id,
            date=today,
            units=inv.quantity,
            nav_price=current_value / inv.quantity if inv.quantity > 0 else 0,
            total_value=current_value
        )
        db.session.add(hist)

    db.session.commit()
    flash(f"Current value for {inv.asset_name} updated successfully!", "success")
    return redirect(url_for('investments'))


@app.route('/investments/delete/<int:inv_id>', methods=['POST'])
@login_required
def delete_investment(inv_id):
    """Deletes an investment holding completely."""
    inv = Investment.query.filter_by(id=inv_id, user_id=g.user.id).first_or_404()
    db.session.delete(inv)
    db.session.commit()
    flash("Investment holding deleted successfully.", "success")
    return redirect(url_for('investments'))


# --- FINANCIAL GOALS ROUTES ---

@app.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    """Displays user goals, creates new goals, and shows projection results."""
    if request.method == 'POST':
        goal_name = request.form.get('goal_name', '').strip()
        goal_type = request.form.get('goal_type', '').strip()
        target_amount_str = request.form.get('target_amount', '0').strip()
        current_amount_str = request.form.get('current_amount', '0').strip()
        target_date_str = request.form.get('target_date', '').strip()

        errors = []
        if not goal_name:
            errors.append("Goal name is required.")
        if not goal_type or goal_type not in ['Home', 'Retirement', 'Travel', 'Education', 'Other']:
            errors.append("Please select a valid goal type.")
        
        try:
            target_amount = float(target_amount_str)
            if target_amount <= 0:
                errors.append("Target amount must be greater than zero.")
        except ValueError:
            errors.append("Invalid target amount format.")

        try:
            current_amount = float(current_amount_str)
            if current_amount < 0:
                errors.append("Current amount cannot be negative.")
        except ValueError:
            errors.append("Invalid current amount format.")

        try:
            target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
            if target_date <= datetime.date.today():
                errors.append("Target date must be in the future.")
        except ValueError:
            errors.append("Invalid target date format. Use YYYY-MM-DD.")

        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            goal = Goal(
                user_id=g.user.id,
                goal_name=goal_name,
                goal_type=goal_type,
                target_amount=target_amount,
                current_amount=current_amount,
                target_date=target_date,
                status='On Track'
            )
            db.session.add(goal)
            db.session.commit()

            # Record initial contribution if current_amount > 0
            if current_amount > 0:
                gt = GoalTransaction(
                    goal_id=goal.id,
                    amount=current_amount,
                    date=datetime.date.today()
                )
                db.session.add(gt)
                db.session.commit()

            flash("Financial Goal created successfully!", "success")
            return redirect(url_for('goals'))

    # Load goals
    user_goals = Goal.query.filter_by(user_id=g.user.id).order_by(Goal.target_date.asc()).all()

    # Calculate user's monthly savings rate based on monthly income and monthly transaction history
    # Let's use monthly income (User.monthly_income) minus average monthly expense, or monthly income - this month's expenses.
    # We will compute: monthly_income - current month's expenses as the savings rate.
    today = datetime.date.today()
    start_date = datetime.date(today.year, today.month, 1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_date = datetime.date(today.year, today.month, last_day)

    monthly_expenses = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.user_id == g.user.id,
        Transaction.type == 'Expense',
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).scalar() or 0.0

    monthly_savings_rate = max(0.0, g.user.monthly_income - monthly_expenses)

    # Simple Projection Helper logic
    # Calculate years/days remaining, update status dynamically
    for goal in user_goals:
        if goal.current_amount >= goal.target_amount:
            goal.status = 'Completed'
            continue

        days_remaining = (goal.target_date - today).days
        months_remaining = days_remaining / 30.44

        # Calculate needed savings per month
        needed_savings = goal.target_amount - goal.current_amount
        needed_per_month = needed_savings / max(1.0, months_remaining)

        # Check if user savings rate covers it.
        # If savings rate is 0 or less than needed, mark it as 'At Risk'
        if monthly_savings_rate >= needed_per_month:
            goal.status = 'On Track'
        else:
            goal.status = 'At Risk'

    db.session.commit()

    today_str = today.strftime('%Y-%m-%d')

    return render_template(
        'goals.html',
        goals=user_goals,
        monthly_savings_rate=monthly_savings_rate,
        today_str=today_str
    )


@app.route('/goals/add_funds/<int:goal_id>', methods=['POST'])
@login_required
def add_goal_funds(goal_id):
    """Logs a goal contribution transaction, updates current_amount, and redirects."""
    goal = Goal.query.filter_by(id=goal_id, user_id=g.user.id).first_or_404()
    amount_str = request.form.get('amount', '0').strip()
    date_str = request.form.get('date', '').strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Contribution amount must be greater than zero.", "danger")
            return redirect(url_for('goals'))
    except ValueError:
        flash("Invalid contribution amount format.", "danger")
        return redirect(url_for('goals'))

    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date_obj = datetime.date.today()

    # Log Goal Transaction
    gt = GoalTransaction(
        goal_id=goal.id,
        amount=amount,
        date=date_obj
    )
    db.session.add(gt)

    # Update goal current amount
    goal.current_amount += amount

    # Recalculate status
    if goal.current_amount >= goal.target_amount:
        goal.status = 'Completed'

    db.session.commit()
    flash(f"Added {g.user.currency} {amount:.2f} toward '{goal.goal_name}'!", "success")
    return redirect(url_for('goals'))


@app.route('/goals/delete/<int:goal_id>', methods=['POST'])
@login_required
def delete_goal(goal_id):
    """Deletes a financial goal and its transaction logs."""
    goal = Goal.query.filter_by(id=goal_id, user_id=g.user.id).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    flash("Financial goal deleted successfully.", "success")
    return redirect(url_for('goals'))


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
