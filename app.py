import os
import sqlite3
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from datetime import datetime
from flask import send_file
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session



app = Flask(__name__)

app.secret_key = 'Console1331'  # To protect sessions

SECRET_PASSWORD = "Console!"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Example of checking username and password
        if username == "Maximus" and password == SECRET_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error_message = "Incorrect username or password"
            return render_template('login.html', error_message=error_message)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear the entire session
    return redirect(url_for('login'))


@app.before_request
def check_login():
    # We set that the session is not permanent (not saved in cookies)
    session.permanent = False
    
    if 'logged_in' not in session and request.endpoint not in ['login', 'static']:
        return redirect(url_for('login'))



# Initializing the database
def init_db():
    conn = sqlite3.connect('budget.db')
    cursor = conn.cursor()
    
    # Create an expense table (if it doesn't already exist)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL
    )''')
    
    # Create a subscription table (if it doesn't already exist)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        next_payment TEXT NOT NULL
    )''')
    
    # Create an income table (if it doesn't already exist)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL
    )''')

    conn.commit()
    conn.close()



# Getting a connection to the database
def get_db_connection():
    conn = sqlite3.connect('budget.db')
    conn.row_factory = sqlite3.Row
    return conn

# Home page
@app.route('/')
def index():
    conn = get_db_connection()
    expenses = conn.execute('SELECT * FROM expenses').fetchall()
    
    subscriptions = conn.execute('SELECT * FROM subscriptions').fetchall()


    # Receiving all incomes
    incomes = conn.execute('SELECT amount FROM incomes').fetchall()

    # Calculating the total amount of income
    total_incomes = sum(income['amount'] for income in incomes)

    # We calculate the total amount of expenses
    total_expenses = sum(expense['amount'] for expense in expenses)
    

    subscriptions = conn.execute('SELECT * FROM subscriptions').fetchall()

    total_subscriptions = sum(subscription['amount'] for subscription in subscriptions)

    # Counting subscriptions for the current month
    current_month = datetime.now().strftime('%Y-%m')

    monthly_subscriptions = sum(
        subscription['amount'] for subscription in subscriptions
        if subscription['next_payment'].startswith(current_month)
    )

    total_expenses += total_subscriptions

    # Round to two decimal places "round( 2)
    total_expenses2 = round(total_expenses, 2)

    # We calculate the remainder (income minus expenses)
    balance = round(total_incomes - total_expenses, 2)


    # Counting the number of records
    expense_count = len(expenses)
    
    
    conn.close()

    # Summarizing expenses by category
    categories = {}
    for expense in expenses:
        if expense['category'] in categories:
            categories[expense['category']] += expense['amount']
        else:
            categories[expense['category']] = expense['amount']

    if total_subscriptions > 0:
        categories['Subscriptions'] = total_subscriptions

    # Creating a schedule
    fig, ax = plt.subplots()
    ax.pie(categories.values(), labels=categories.keys(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # So that the graph is round

    # Saving a graph to the buffer
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)

    # Convert to base64 for display in HTML
    img_base64 = base64.b64encode(img.read()).decode('utf-8')
    plt.close(fig)

    return render_template('index.html', expenses=expenses, chart=img_base64, monthly_subscriptions=monthly_subscriptions, total_expenses=total_expenses, expense_count=expense_count, total_incomes=total_incomes, balance=balance, total_expenses2=total_expenses2)


# Adding an expense
@app.route('/add_expense', methods=['POST'])
def add_expense():
    amount = request.form['amount']
    category = request.form['category']
    date = request.form['date']

    conn = get_db_connection()
    conn.execute('INSERT INTO expenses (amount, category, date) VALUES (?, ?, ?)', (amount, category, date))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Delete expense
@app.route('/delete_expense/<int:id>', methods=['POST'])
def delete_expense(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM expenses WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/incomes')
def incomes():
    conn = get_db_connection()
    
    # Loading data
    incomes = [dict(row) for row in conn.execute('SELECT * FROM incomes').fetchall()]
    conn.close()

    # We check if there is income
    if not incomes:
        return render_template('incomes.html', incomes=[], chart=None, total_incomes=0, current_month_incomes=0)

    # Create a DataFrame
    incomes_df = pd.DataFrame(incomes)

    # Convert date to format "datetime"
    incomes_df['date'] = pd.to_datetime(incomes_df['date'])

    # Determine the current month
    current_month = datetime.now().strftime('%Y-%m')

    # Filtering income for the current month
    current_month_incomes = incomes_df[incomes_df['date'].dt.strftime('%Y-%m') == current_month]['amount'].sum()

    # Total income
    total_incomes = incomes_df['amount'].sum()

    # Summarizing income by sources
    sources = incomes_df.groupby('source')['amount'].sum().to_dict()

    # We construct a graph of income distribution by sources
    fig, ax = plt.subplots(figsize=(9, 6))
    if sources:
        ax.pie(sources.values(), labels=sources.keys(), autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Pie chart
    else:
        ax.text(0.5, 0.5, 'No Data Available', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=14)

    # Save the graph to the buffer
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)

    # Convert in base64 to display in HTML
    img_base64 = base64.b64encode(img.read()).decode('utf-8')
    plt.close(fig)

    return render_template(
        'incomes.html',
        incomes=incomes,
        chart=img_base64,
        total_incomes=total_incomes,
        current_month_incomes=current_month_incomes
    )

# Add Income Page
@app.route('/add_income', methods=['POST'])
def add_income():
    source = request.form['source']
    amount = request.form['amount']
    date = request.form['date']

    conn = get_db_connection()
    conn.execute('INSERT INTO incomes (source, amount, date) VALUES (?, ?, ?)',
                 (source, amount, date))
    conn.commit()
    conn.close()

    return redirect(url_for('incomes'))

# Income Removal Page
@app.route('/delete_income/<int:id>', methods=['POST'])
def delete_income(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM incomes WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('incomes'))

@app.route('/subscriptions')
def subscriptions():
    conn = get_db_connection()
    subscriptions = conn.execute('SELECT * FROM subscriptions').fetchall()
    
    # Calculating the total amount of subscriptions and distributing them by category
    names = [sub['name'] for sub in subscriptions]
    amounts = [sub['amount'] for sub in subscriptions]

    # Counting subscriptions for the current month
    current_month = datetime.now().strftime('%Y-%m')
    
    monthly_subscriptions = sum(
        subscription['amount'] for subscription in subscriptions
        if subscription['next_payment'].startswith(current_month)
    )
    conn.close()
    
     # Calculating total subscriptions
    total_subscriptions = sum(subscription['amount'] for subscription in subscriptions)

    # Построение графика
    if amounts:  # Checking if there are subscriptions
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.pie(amounts, labels=names, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # To make the graph round
        
        # Saving a graph to the buffer
        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)

        # Convert to base64 for display in HTML
        img_base64 = base64.b64encode(img.read()).decode('utf-8')
        plt.close(fig)
    else:
        img_base64 = None  # If there are no subscriptions, we do not create a schedule

    return render_template('subscriptions.html', subscriptions=subscriptions, chart=img_base64, monthly_subscriptions=monthly_subscriptions,total_subscriptions=total_subscriptions)



# Adding a subscription
@app.route('/add_subscription', methods=['POST'])
def add_subscription():
    name = request.form['name']
    amount = request.form['amount']
    next_payment = request.form['next_payment']

    conn = get_db_connection()
    conn.execute('INSERT INTO subscriptions (name, amount, next_payment) VALUES (?, ?, ?)', (name, amount, next_payment))
    conn.commit()
    conn.close()
    return redirect(url_for('subscriptions'))



# Subscription editing page
@app.route('/edit_subscription/<int:id>', methods=['GET', 'POST'])
def edit_subscription(id):
    conn = get_db_connection()
    
    # Getting subscription data by id
    subscription = conn.execute('SELECT * FROM subscriptions WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        # Getting new data from a form
        name = request.form['name']
        amount = request.form['amount']
        next_payment = request.form['next_payment']

        # Updating a subscription in the database
        conn.execute('UPDATE subscriptions SET name = ?, amount = ?, next_payment = ? WHERE id = ?',
                     (name, amount, next_payment, id))
        conn.commit()
        conn.close()
        return redirect(url_for('subscriptions'))  # Redirect to subscriptions page

    conn.close()

    # Sending data for editing to a template
    return render_template('edit_subscription.html', subscription=subscription)

@app.route('/edit_expense/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    conn = get_db_connection()
    
    # Getting consumption data by id
    expense = conn.execute('SELECT * FROM expenses WHERE id = ?', (id,)).fetchone()

    if expense is None:
        return 'Expense not found', 404  # If the expense is not found, return an error

    if request.method == 'POST':
        # Getting new data from a form
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        # Updating the expense in the database
        conn.execute('UPDATE expenses SET amount = ?, category = ?, date = ? WHERE id = ?',
                     (amount, category, date, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))  # Redirect to home page or 'expenses'

    conn.close()

    # Sending data for editing to a template
    return render_template('edit_expense.html', expense=expense)


@app.route('/edit_income/<int:id>', methods=['GET', 'POST'])
def edit_income(id):
    conn = get_db_connection()
    
    # Getting income data by id
    income = conn.execute('SELECT * FROM incomes WHERE id = ?', (id,)).fetchone()

    if income is None:
        return 'Income not found', 404  # If income is not found, return an error

    if request.method == 'POST':
        # Getting new data from a form
        source = request.form['source']
        amount = request.form['amount']
        date = request.form['date']

        # Updating income in the database
        conn.execute('UPDATE incomes SET source = ?, amount = ?, date = ? WHERE id = ?',
                     (source, amount, date, id))
        conn.commit()
        conn.close()
        return redirect(url_for('incomes'))  # Redirect to income page

    conn.close()

    # Sending data for editing to a template
    return render_template('edit_income.html', income=income)

# Deleting a subscription
@app.route('/delete_subscription/<int:id>', methods=['POST'])
def delete_subscription(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM subscriptions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('subscriptions'))


@app.route('/reports')
def reports():
    conn = get_db_connection()
    
    # Getting data from the database
    expenses = conn.execute('SELECT amount, category, date FROM expenses').fetchall()
    subscriptions = conn.execute('SELECT amount, next_payment FROM subscriptions').fetchall()
    incomes = conn.execute('SELECT amount, date FROM incomes').fetchall()
    
    conn.close()

    # Converting data to DataFrame
    expenses_df = pd.DataFrame(expenses, columns=['amount', 'category', 'date'])
    subscriptions_df = pd.DataFrame(subscriptions, columns=['amount', 'next_payment'])
    incomes_df = pd.DataFrame(incomes, columns=['amount', 'date'])

    # Converting data to datetime
    expenses_df['date'] = pd.to_datetime(expenses_df['date'], errors='coerce')
    subscriptions_df['next_payment'] = pd.to_datetime(subscriptions_df['next_payment'], errors='coerce')
    incomes_df['date'] = pd.to_datetime(incomes_df['date'], errors='coerce')

    # Determine the current month
    current_month = datetime.now().strftime('%Y-%m')

    # Filtering data for the current month
    current_month_expenses = expenses_df[expenses_df['date'].dt.strftime('%Y-%m') == current_month]['amount'].sum()
    current_month_subscriptions = subscriptions_df[subscriptions_df['next_payment'].dt.strftime('%Y-%m') == current_month]['amount'].sum()
    current_month_incomes = incomes_df[incomes_df['date'].dt.strftime('%Y-%m') == current_month]['amount'].sum()

    # Total expenses for the current month
    current_month_total_expenses = round(current_month_expenses + current_month_subscriptions, 2)

    # Total subscription costs for all time (for reporting)
    total_subscriptions = round(subscriptions_df['amount'].sum(), 2)

    # Balance for the current month
    current_month_balance = round(current_month_incomes - current_month_total_expenses, 2)

    
    # Grouping expenses and subscriptions by month
    expenses_df['month'] = expenses_df['date'].dt.to_period('M')
    subscriptions_df['month'] = subscriptions_df['next_payment'].dt.to_period('M')
    incomes_df['month'] = incomes_df['date'].dt.to_period('M')

    monthly_expenses = expenses_df.groupby('month')['amount'].sum()
    # test monthly_subscriptions = subscriptions_df.groupby('month')['amount'].sum()
    monthly_subscriptions = round(subscriptions_df.groupby('month')['amount'].sum(), 2)
    monthly_incomes = incomes_df.groupby('month')['amount'].sum()


    # Summarizing expenses and subscriptions
    total_monthly_expenses = monthly_expenses.add(monthly_subscriptions, fill_value=0)

    # We calculate the balance for the current month taking into account the grouping
    current_month_balance = round(
        monthly_incomes.get(current_month, 0) - total_monthly_expenses.get(current_month, 0), 2
    )

    # Create a schedule of income and expenses
    fig, ax = plt.subplots(figsize=(9, 6))
    total_monthly_expenses.sort_index().plot(ax=ax, label='Expenses', marker='o', color='red')
    monthly_incomes.sort_index().plot(ax=ax, label='Incomes', marker='o', color='green')

    ax.set_title('Monthly Income and Expenses', fontsize=16)
    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Amount', fontsize=12)
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.6)

    # Save the graph to the buffer
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64_2 = base64.b64encode(img.read()).decode('utf-8')
    plt.close(fig)

    # Total income and expenses
    total_incomes = incomes_df['amount'].sum()
    total_expenses = expenses_df['amount'].sum()
    
    # Final balance
    balance = round(total_incomes - (total_expenses + total_subscriptions), 2)

    # Create a schedule of expenses by category
    fig, ax = plt.subplots(figsize=(9, 6))
    if not expenses_df.empty:
        expenses_by_category = expenses_df.groupby('category')['amount'].sum()
        ax.bar(expenses_by_category.index, expenses_by_category.values, color='skyblue')
        ax.set_title('Expenses by Category', fontsize=16)
        ax.set_xlabel('Category', fontsize=12)
        ax.set_ylabel('Total Amount', fontsize=10)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
    else:
        ax.text(0.5, 0.5, 'No Data Available', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=14)

    # Save the graph to the buffer
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.read()).decode('utf-8')
    plt.close(fig)

    return render_template(
        'reports.html',
        chart=img_base64,  # Expense chart by category
        chart2=img_base64_2,  # Income and Expenses Chart by Month
        total_incomes=total_incomes,
        total_expenses=round(total_expenses + total_subscriptions, 2),
        balance=balance,
        current_month_balance=current_month_balance,
        current_month_total_expenses=current_month_total_expenses,
        current_month_incomes=current_month_incomes,
        total_subscriptions=total_subscriptions,
        monthly_subscriptions=monthly_subscriptions,
        current_month_subscriptions=current_month_subscriptions
    )



@app.route('/export/<format>')
def export_data(format):
    conn = get_db_connection()
    
    # Select all data from tables
    expenses = conn.execute('SELECT id, amount, category, date FROM expenses').fetchall()
    incomes = conn.execute('SELECT id, amount, source, date FROM incomes').fetchall()
    subscriptions = conn.execute('SELECT id, amount, name, next_payment FROM subscriptions').fetchall()
    
    # Closing the connection
    conn.close()
    
    # Prepare a DataFrame for each table
    expenses_df = pd.DataFrame(expenses, columns=['id', 'amount', 'category', 'date'])
    incomes_df = pd.DataFrame(incomes, columns=['id', 'amount', 'source', 'date'])
    subscriptions_df = pd.DataFrame(subscriptions, columns=['id', 'amount', 'name', 'next_payment'])
    
    if expenses_df.empty and incomes_df.empty and subscriptions_df.empty:
        return "No data available to export", 400

    output = BytesIO()

    if format == 'csv':
        # Combine all DataFrames into one for export to CSV
        all_data = pd.concat([expenses_df, incomes_df, subscriptions_df], keys=['Expenses', 'Incomes', 'Subscriptions'])
        all_data.to_csv(output, index=False)
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='financial_data.csv')
        
    elif format == 'excel':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Write each DataFrame to a separate Excel sheet
            expenses_df.to_excel(writer, index=False, sheet_name='Expenses')
            incomes_df.to_excel(writer, index=False, sheet_name='Incomes')
            subscriptions_df.to_excel(writer, index=False, sheet_name='Subscriptions')
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='financial_data.xlsx')
    else:
        return "Invalid format", 400


@app.route('/import', methods=['POST'])
def import_data():
    file = request.files.get('file')

    if not file:
        return "No file uploaded", 400

    try:
        if file.filename.endswith('.csv'):
            data = pd.read_csv(file)
            print(data.columns)  # Print column names for debugging

            # Filter rows by the presence of data in certain columns
            expenses_data = data[data['category'].notna() & data['amount'].notna() & data['date'].notna() & data['source'].isna() & data['name'].isna()]
            incomes_data = data[data['source'].notna() & data['amount'].notna() & data['date'].notna()]
            subscriptions_data = data[data['name'].notna() & data['amount'].notna() & data['next_payment'].notna()]

        elif file.filename.endswith('.xlsx'):
            data = pd.read_excel(file, sheet_name=None)
        else:
            return "Unsupported file format", 400

        conn = get_db_connection()

        # Deleting old data
        conn.execute('DELETE FROM expenses')
        conn.execute('DELETE FROM incomes')
        conn.execute('DELETE FROM subscriptions')

        # Inserting expenses
        for _, row in expenses_data.iterrows():
            conn.execute(
                'INSERT INTO expenses (amount, category, date) VALUES (?, ?, ?)',
                (row['amount'], row['category'], row['date'])
            )

        # Inserting Income
        for _, row in incomes_data.iterrows():
            conn.execute(
                'INSERT INTO incomes (amount, source, date) VALUES (?, ?, ?)',
                (row['amount'], row['source'], row['date'])
            )

        # Inserting subscriptions
        for _, row in subscriptions_data.iterrows():
            conn.execute(
                'INSERT INTO subscriptions (amount, name, next_payment) VALUES (?, ?, ?)',
                (row['amount'], row['name'], row['next_payment'])
            )

        conn.commit()
        conn.close()

        return redirect(url_for('reports'))

    except Exception as e:
        return f"Error processing file: {e}", 400





if __name__ == '__main__':
    init_db()
    app.run(debug=True)
