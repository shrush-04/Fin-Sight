FinSight – Personal Finance & Investment Intelligence Platform


Project Overview

FinSight is a full-stack personal finance management web application built as
part of an internship/project-based learning assignment. It helps users track
income and expenses, manage budgets, monitor investments, plan financial
goals, and get intelligent insights into their overall financial health —
all from a single, easy-to-use dashboard.

The project is being built in 4 milestones over 8 weeks, with each
milestone adding a new layer of functionality on top of the previous one.

Modules to Be Implemented

1. User Authentication & Profile Management
2. Expense & Budget Management
3. Investment Portfolio Tracking (Milestone 2)
4. Financial Goal Planning (Milestone 2)
5. Analytics & Intelligence Engine
6. Dashboard & Reporting
7. Notification & Alert System


Flow of the application

1.User Registration/Login
        │
        ▼
2.Profile Setup (income, currency, preferences)
        │
        ▼
3.Data Entry (add income & expense transactions, categorize them)
        │
        ▼
Budget Management (set limits per category, monitor utilization)
        │
        ▼
   ┌────┴─────┐
   ▼          ▼
Investment   Goal
Tracking     Planning
   │          │
   └────┬─────┘
        ▼
Analytics & Intelligence Engine
(spending analysis, health score, recommendations)
        │
        ▼
Dashboards & Reports  ──►  Alerts & Notifications
        │
        ▼
Export & Sharing (PDF / Excel)
        │
        ▼
Continuous Monitoring & Improvement (feedback loop back to dashboard)


---

Milestone 2 Features
────────────────────

1. Investment Portfolio Tracking (/investments)
   - Add/Remove investment holdings across asset types: Stocks, Mutual Funds, ETFs, Bonds, Gold, Cash, and Others.
   - Live asset allocation summary displayed in a responsive donut chart.
   - Interactive line chart depicting historical portfolio performance over time using portfolio snapshots.
   - Easily update the current value of holdings to automatically calculate absolute/percentage returns.
   - Dashboard integration: Net Worth calculation (lifetime savings + current value of holdings) shown on a new summary card.

2. Financial Goal Planning (/goals)
   - Set financial goals specifying names, categories, target amounts, and future target dates.
   - Automatic goal projection tracking (On Track / At Risk) calculated dynamically using the user's monthly savings rate.
   - Contribute money toward goals via the "Add Funds" contribution action.
   - Track progress visually using sleek, colored status bars and badges.
   - Dashboard integration: Number of active goals shown on a dedicated summary card.


---

Upload Receipt (OCR) Feature
─────────────────────────────

FinSight lets users scan expense receipts or UPI payment screenshots to
automatically extract transaction details using Tesseract OCR.

Flow:
  1. On the Transactions page, click "Upload Receipt".
  2. Choose a JPEG or PNG image (or drag & drop it).
  3. Click "Scan Receipt" — the app runs OCR on the image and extracts:
       • Amount (₹/Rs/INR patterns, "Total", "Amount Paid")
       • Merchant / Payee name (from "Paid to" or first text line)
       • Date (dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd formats)
       • GST / CGST / SGST amounts (displayed as info only)
  4. The extracted fields appear in an editable review form alongside a
     thumbnail of the receipt for cross-checking.
  5. Category is auto-guessed from the merchant name using keyword rules
     (e.g. "Swiggy" → Food & Dining; "Uber" → Transportation).
  6. Edit any field, then click "Confirm & Save" to record the transaction.

Manual entry is still available via "Add Transaction" — both options work
side by side. OCR extraction is a best-effort guess; always review the
fields before saving.


Dependencies (pip)
──────────────────

Install Python dependencies with:

    pip install -r requirements.txt

Key packages added for OCR:
  • pytesseract >= 0.3.13  — Python wrapper for Tesseract OCR
  • Pillow >= 10.0.0       — Image handling library


Tesseract OCR Engine — Required System Installation
────────────────────────────────────────────────────

pytesseract is only a Python wrapper; the actual Tesseract OCR engine
must be installed separately on the host machine.

Windows:
  1. Download and run the installer from:
         https://github.com/UB-Mannheim/tesseract/wiki
     (choose the latest stable .exe, e.g. tesseract-ocr-w64-setup-5.x.x.exe)
  2. During installation, note the install path (default:
         C:\Program Files\Tesseract-OCR\tesseract.exe)
  3. If the app cannot find Tesseract automatically, set the path in
     finsight/app.py near the top of the file:

         pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

     Uncomment and adjust the example line already present in app.py.

Linux / macOS:
  • Ubuntu/Debian:  sudo apt install tesseract-ocr
  • macOS (Homebrew): brew install tesseract

After installing, verify with:
    tesseract --version

If Tesseract is not installed, the "Upload Receipt" button will still
appear but will return a clear error message rather than crashing the app.


---

Milestone 3 Features
────────────────────

1. Spending Pattern Analysis (/analytics)
   - Fetches and groups transaction history for the last 3-6 months.
   - Interactive, grouped-bar chart powered by Chart.js displaying category-wise monthly trends.
   - Identifies and highlights month-over-month category budget increases or decreases via color-coded badges on the Analytics dashboard.

2. Financial Health Score (0-100)
   Evaluates user financial stability across 4 weighted factors (25% each):
   - **Savings Rate (25%)**: Calculates `(Income - Expenses) / Income` for the current month. Earns full points (25) if >= 20%; scales down linearly otherwise.
   - **Category Budget Discipline (25%)**: Assesses adherence to set category budgets. Calculates the overrun ratio for each budget and averages them.
   - **Investment Activity (25%)**: Assesses the portfolio state. Grants a base score of 10 points for having active investments, and up to 15 points based on the current month's investment rate (target 15% of income).
   - **Overall Budget Adherence (25%)**: Compares total spending against total monthly budgeted amount, penalizing overruns linearly.
   
   Visualized as an animated circular ring progress indicator labeled as:
   - 80 - 100: **Excellent** (Success color)
   - 60 - 79: **Good** (Info/slate blue color)
   - 40 - 59: **Needs Attention** (Warning color)
   - Below 40: **At Risk** (Danger color)

3. Personalized Recommendations
   Generates real-time, rule-based recommendations:
   - Over-budget categories: Advises a specific percentage cut.
   - Discretionary spend: If Food, Entertainment, and Others exceed 40% of total spend, suggests a 15% cut.
   - Low savings rate: If below 20%, warns the user and suggests budget revisions.
   - Low investment rate: If below 15%, calculates the specific shortfall amount and recommends increasing contributions.

4. Alert & Notification System
   Adds a `Notification` model to store persistent alerts (Budget, Investment, Goal, System). Automatically triggered on:
   - Category budget exceeding 80% utilization (Warning) or 100% utilization (Exceeded).
   - Financial Goal successfully completed.
   - Investment allocation falling notably below 10% target rate.
   - Manual generation of Monthly Summary via the "Generate Monthly Summary" button.
   Includes a notification bell in the navigation bar with an unread badge and dropdown list for quick inspection. Clicking a notification marks it read asynchronously.

5. Self-Reported CIBIL Score Tracking (/profile)
   - **Manual Bureau Entry**: Since live credit bureau integration is restricted by TransUnion CIBIL/RBI regulations to licensed lending institutions, this feature allows users to self-report and update their credit score (300-900 range).
   - **Meter/Gauge Display**: Renders the latest score in a color-coded horizontal linear scale:
     - 300 - 549: **Poor** (Red)
     - 550 - 699: **Fair** (Orange/Amber)
     - 700 - 749: **Good** (Yellow)
     - 750 - 900: **Excellent** (Green)
   - **Historical Charting**: Plots credit score trends over time if multiple score updates are logged by the user.
   - **Health Score Rebalancing**:
     - If the user has logged at least one CIBIL score, the Financial Health Score dynamically scales to include it as a 5th factor. Each factor contributes up to 20% (Savings Rate, Budget Discipline, Investment Activity, Overall Budget Adherence, CIBIL score).
     - The 300-900 score range is normalized to a 0-100 score value: `cibil_normalized = ((score - 300) / 600) * 100` before contributing to the health score.
     - If no CIBIL score is logged, the system gracefully falls back to the original 4-factor configuration (25% weight each) without penalizing the user.