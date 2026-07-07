# FinSight - Personal Finance Platform

FinSight is a clean, minimal personal finance web application built using Python, Flask, and SQLite. It features visual metrics, expense tracking, category budgeting, and portfolio monitoring.

## Key Update
- **Public Landing Page**: The main landing page is now served at the root URL `/` for non-logged-in users.
- **Financial Dashboard**: The authenticated dashboard experience has been moved to `/dashboard`.

## Features
- **Landing Page**: Modern company-style landing page with hero header, live scroll animations, a visual finance SVG graphic, counts animation, feature cards, and visual call-to-action sections.
- **Dashboard**: High-level telemetry of month-to-date income, expenses, savings progress, category breakdown doughnut charts, and recent transaction history.
- **Expenses**: Complete ledger to view, filter (by type, category, or month), edit, delete, and add new transactions.
- **Budgets**: Configure spending limits for custom expense categories and monitor visual limits.
- **Profile**: Customize user information and display currency settings.

## Running the Project
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Navigate to the code directory:
   ```bash
   cd finsight
   ```
3. Run the development server:
   ```bash
   python app.py
   ```
4. Access the site in your browser at `http://127.0.0.1:5000/`.
