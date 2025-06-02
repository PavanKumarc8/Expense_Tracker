import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import calendar
import hashlib

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        category TEXT NOT NULL,
        description TEXT DEFAULT '',
        tags TEXT DEFAULT '',
        payment_method TEXT DEFAULT 'Cash',
        recurring BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        budget REAL DEFAULT 0,
        color TEXT DEFAULT '#FF6B6B',
        icon TEXT DEFAULT '💰',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        type TEXT DEFAULT 'Cash'
    )
    ''')
    # Insert default data if empty
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("Food", 300, "#FF6B6B", "🍔"),
            ("Transportation", 150, "#4ECDC4", "🚗"),
            ("Housing", 800, "#45B7D1", "🏠"),
            ("Entertainment", 200, "#96CEB4", "🎬"),
            ("Utilities", 250, "#FFE6A7", "⚡"),
            ("Healthcare", 200, "#D3D3D3", "🏥"),
            ("Shopping", 300, "#FFB6C1", "🛍️"),
            ("Education", 150, "#87CEEB", "📚"),
            ("Others", 100, "#D3D3D3", "💼")
        ]
        cursor.executemany(
            "INSERT INTO categories (name, budget, color, icon) VALUES (?, ?, ?, ?)",
            default_categories
        )
    cursor.execute("SELECT COUNT(*) FROM payment_methods")
    if cursor.fetchone()[0] == 0:
        default_payments = [
            ("Cash", "Cash"),
            ("Credit Card", "Card"),
            ("Debit Card", "Card"),
            ("Bank Transfer", "Digital"),
            ("Mobile Payment", "Digital"),
            ("Check", "Other")
        ]
        cursor.executemany(
            "INSERT INTO payment_methods (name, type) VALUES (?, ?)",
            default_payments
        )
    conn.commit()
    conn.close()

init_db()

# --- Helper Functions ---
def get_categories():
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

def get_payment_methods():
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM payment_methods")
    methods = [row[0] for row in cursor.fetchall()]
    conn.close()
    return methods

def get_user_id(username):
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_expenses(user_id, query=None, params=None):
    conn = sqlite3.connect("expense_tracker.db")
    if query is None:
        query = "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC"
        params = (user_id,)
    else:
        params = (user_id,) + tuple(params) if params else (user_id,)
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def get_recent_expenses(user_id):
    return get_expenses(user_id, "SELECT date, amount, category, description FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 10")

def get_budget_performance(user_id):
    current_month = datetime.now().strftime("%Y-%m")
    conn = sqlite3.connect("expense_tracker.db")
    query = """
    SELECT c.name, c.budget, COALESCE(SUM(e.amount), 0) as spent
    FROM categories c
    LEFT JOIN expenses e ON c.name = e.category AND e.date LIKE ? AND e.user_id = ?
    GROUP BY c.name, c.budget
    """
    df = pd.read_sql(query, conn, params=(f"{current_month}%", user_id))
    conn.close()
    return df

def get_spending_trends(user_id, months=6):
    conn = sqlite3.connect("expense_tracker.db")
    query = """
    SELECT DATE(date, 'start of month') as month, 
           SUM(amount) as total,
           category,
           COUNT(*) as transaction_count
    FROM expenses 
    WHERE user_id = ? AND date >= date('now', '-' || ? || ' months')
    GROUP BY month, category
    ORDER BY month DESC
    """
    df = pd.read_sql(query, conn, params=(user_id, months))
    conn.close()
    return df

def add_expense(user_id, date, amount, category, description, tags, payment_method, recurring):
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO expenses (user_id, date, amount, category, description, tags, payment_method, recurring)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, date, amount, category, description, tags, payment_method, int(recurring))
    )
    conn.commit()
    conn.close()

def delete_expense(user_id, expense_id):
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    conn.commit()
    conn.close()

def update_expense(user_id, expense_id, date, amount, category, description, tags, payment_method, recurring):
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE expenses
        SET date = ?, amount = ?, category = ?, description = ?, tags = ?, payment_method = ?, recurring = ?
        WHERE id = ? AND user_id = ?
        """,
        (date, amount, category, description, tags, payment_method, int(recurring), expense_id, user_id)
    )
    conn.commit()
    conn.close()

# --- Authentication ---
def create_user(username, password):
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(username, password):
    conn = sqlite3.connect("expense_tracker.db")
    cursor = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# --- Streamlit App ---
def main():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    if st.session_state.user is None or st.session_state.user_id is None:
        st.title("Expense Tracker - Login")
        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                user_id = authenticate_user(username, password)
                if user_id:
                    st.session_state.user = username
                    st.session_state.user_id = user_id
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        with tab_register:
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            if st.button("Register"):
                if create_user(new_username, new_password):
                    st.success("User registered successfully!")
                else:
                    st.error("Username already exists")

    else:
        st.title(f"Expense Tracker - {st.session_state.user}")
        if st.button("Logout"):
            st.session_state.user = None
            st.session_state.user_id = None
            st.rerun()

        user_id = st.session_state.user_id

        st.header("Dashboard")
        recent_expenses = get_recent_expenses(user_id)
        st.subheader("Recent Expenses")
        st.dataframe(recent_expenses)

        current_month = datetime.now().strftime("%Y-%m")
        last_month = (datetime.now() - timedelta(days=30)).strftime("%Y-%m")
        df_all = get_expenses(user_id)
        current_total = df_all[df_all["date"].str.startswith(current_month)]["amount"].sum()
        last_total = df_all[df_all["date"].str.startswith(last_month)]["amount"].sum()
        col1, col2 = st.columns(2)
        col1.metric("This Month", f"₹{current_total:.2f}")
        col2.metric("Last Month", f"₹{last_total:.2f}")

        st.subheader("Budget vs Actual")
        budget_df = get_budget_performance(user_id)
        budget_df["remaining"] = budget_df["budget"] - budget_df["spent"]
        budget_df.loc[budget_df["remaining"] < 0, "status"] = "Over"
        budget_df.loc[budget_df["remaining"] >= 0, "status"] = "Good"
        st.dataframe(budget_df[["name", "budget", "spent", "remaining", "status"]])

        st.header("Add Expense")
        with st.form("add_expense"):
            date = st.date_input("Date", value=datetime.now())
            amount = st.number_input("Amount", min_value=0.0, step=0.01)
            category = st.selectbox("Category", get_categories())
            description = st.text_input("Description")
            tags = st.text_input("Tags")
            payment_method = st.selectbox("Payment Method", get_payment_methods())
            recurring = st.checkbox("Recurring")
            if st.form_submit_button("Add Expense"):
                add_expense(
                    user_id,
                    date.strftime("%Y-%m-%d"),
                    amount,
                    category,
                    description,
                    tags,
                    payment_method,
                    recurring
                )
                st.success("Expense added successfully!")
                st.rerun()

        st.header("Expense List")
        with st.expander("Filters"):
            col1, col2 = st.columns(2)
            category_filter = col1.selectbox("Category", [""] + get_categories())
            date_from = col2.date_input("From", value=datetime.now() - timedelta(days=30))
            date_to = col2.date_input("To", value=datetime.now())
            apply_filters = st.button("Apply Filters")

        df = get_expenses(user_id)
        if apply_filters:
            query = "SELECT * FROM expenses WHERE user_id = ?"
            params = []
            if category_filter:
                query += " AND category = ?"
                params.append(category_filter)
            if date_from:
                query += " AND date >= ?"
                params.append(date_from.strftime("%Y-%m-%d"))
            if date_to:
                query += " AND date <= ?"
                params.append(date_to.strftime("%Y-%m-%d"))
            df = get_expenses(user_id, query, params)
        st.dataframe(df)

        st.subheader("Edit/Delete Expense")
        expense_id = st.number_input("Expense ID", min_value=0, step=1)
        if expense_id:
            expense = df[df["id"] == expense_id]
            if not expense.empty:
                expense = expense.iloc[0]
                with st.form("edit_expense"):
                    date = st.date_input("Date", value=datetime.strptime(expense["date"], "%Y-%m-%d"))
                    amount = st.number_input("Amount", value=expense["amount"])
                    category = st.selectbox("Category", get_categories(), index=get_categories().index(expense["category"]))
                    description = st.text_input("Description", value=expense["description"])
                    tags = st.text_input("Tags", value=expense["tags"])
                    payment_method = st.selectbox("Payment Method", get_payment_methods(), index=get_payment_methods().index(expense["payment_method"]))
                    recurring = st.checkbox("Recurring", value=bool(expense["recurring"]))
                    col1, col2 = st.columns(2)
                    if col1.form_submit_button("Save"):
                        update_expense(
                            user_id,
                            expense_id,
                            date.strftime("%Y-%m-%d"),
                            amount,
                            category,
                            description,
                            tags,
                            payment_method,
                            recurring
                        )
                        st.success("Expense updated successfully!")
                        st.rerun()
                    if col2.form_submit_button("Delete"):
                        delete_expense(user_id, expense_id)
                        st.success("Expense deleted successfully!")
                        st.rerun()

        st.header("Reports")
        report_type = st.selectbox("Report Type", ["Category Breakdown", "Trends", "Payment Methods"])
        if report_type == "Category Breakdown":
            current_month = datetime.now().strftime("%B")
            current_year = datetime.now().strftime("%Y")
            month_names = list(calendar.month_name[1:])
            index = month_names.index(current_month) if current_month in month_names else 0
            month = st.selectbox("Month", month_names, index=index)
            year = st.selectbox("Year", [str(y) for y in range(2020, 2031)], index=int(current_year)-2020)
            month_num = list(calendar.month_name).index(month)
            date_start = f"{year}-{month_num:02d}-01"
            date_end = f"{year}-{month_num:02d}-{calendar.monthrange(int(year), month_num)[1]}"
            query = """
            SELECT category, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
            """
            df_report = get_expenses(user_id, query, (date_start, date_end))
            fig = px.bar(df_report, x="category", y="total", title=f"Category Breakdown for {month} {year}")
            st.plotly_chart(fig)
        elif report_type == "Trends":
            trends = get_spending_trends(user_id)
            fig = px.bar(trends, x="month", y="total", color="category", title="Monthly Spending Trends")
            st.plotly_chart(fig)
        elif report_type == "Payment Methods":
            current_month = datetime.now().strftime("%B")
            current_year = datetime.now().strftime("%Y")
            month = st.selectbox("Month", list(calendar.month_name[1:]), index=int(current_month)-1)
            year = st.selectbox("Year", [str(y) for y in range(2020, 2031)], index=int(current_year)-2020)
            month_num = list(calendar.month_name).index(month)
            date_start = f"{year}-{month_num:02d}-01"
            date_end = f"{year}-{month_num:02d}-{calendar.monthrange(int(year), month_num)[1]}"
            query = """
            SELECT payment_method, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY payment_method
            """
            df_report = get_expenses(user_id, query, (date_start, date_end))
            fig = px.pie(df_report, values="total", names="payment_method", title=f"Payment Methods for {month} {year}")
            st.plotly_chart(fig)

if __name__ == "__main__":
    main()