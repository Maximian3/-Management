import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

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

    # Подсчет подписок за текущий месяц
    current_month = datetime.now().strftime('%Y-%m')

    monthly_subscriptions = sum(
        subscription['amount'] for subscription in subscriptions
        if subscription['next_payment'].startswith(current_month)
    )

    total_expenses += total_subscriptions

    # Округляем до двух знаков после запятой
    total_expenses2 = round(total_expenses, 2)

    # Рассчитываем остаток (доход минус расходы)
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

    return render_template('index.html', expenses=expenses, chart=img_base64, monthly_subscriptions=monthly_subscriptions, total_expenses=total_expenses,total_expenses2=total_expenses2, expense_count=expense_count, total_incomes=total_incomes, balance=balance)


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
    incomes = conn.execute('SELECT * FROM incomes').fetchall()
    conn.close()


    # Calculating the total amount of income
    total_incomes = sum(income['amount'] for income in incomes)
    
    # Summarizing income by sources
    sources = {}
    for income in incomes:
        if income['source'] in sources:
            sources[income['source']] += income['amount']
        else:
            sources[income['source']] = income['amount']

    # Creating a schedule
    fig, ax = plt.subplots()
    ax.pie(sources.values(), labels=sources.keys(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # So that the graph is round

    # Saving a graph to the buffer
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)

    # Convert to base64 for display in HTML
    img_base64 = base64.b64encode(img.read()).decode('utf-8')
    plt.close(fig)

    return render_template('incomes.html', incomes=incomes, chart=img_base64, total_incomes=total_incomes )


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
    
    # Подсчет общей суммы подписок и распределение по категориям
    names = [sub['name'] for sub in subscriptions]
    amounts = [sub['amount'] for sub in subscriptions]

    # Подсчет подписок за текущий месяц
    current_month = datetime.now().strftime('%Y-%m')
    
    monthly_subscriptions = sum(
        subscription['amount'] for subscription in subscriptions
        if subscription['next_payment'].startswith(current_month)
    )
    conn.close()
    
    # Построение графика
    if amounts:  # Проверяем, есть ли подписки
        fig, ax = plt.subplots()
        ax.pie(amounts, labels=names, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Чтобы график был круглым
        
        # Сохранение графика в буфер
        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)

        # Конвертация в base64 для отображения в HTML
        img_base64 = base64.b64encode(img.read()).decode('utf-8')
        plt.close(fig)
    else:
        img_base64 = None  # Если подписок нет, график не строим

    return render_template('subscriptions.html', subscriptions=subscriptions, chart=img_base64, monthly_subscriptions=monthly_subscriptions)





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




# Страница для редактирования подписки
@app.route('/edit_subscription/<int:id>', methods=['GET', 'POST'])
def edit_subscription(id):
    conn = get_db_connection()
    
    # Получение данных подписки по id
    subscription = conn.execute('SELECT * FROM subscriptions WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        # Получение новых данных из формы
        name = request.form['name']
        amount = request.form['amount']
        next_payment = request.form['next_payment']

        # Обновление подписки в базе данных
        conn.execute('UPDATE subscriptions SET name = ?, amount = ?, next_payment = ? WHERE id = ?',
                     (name, amount, next_payment, id))
        conn.commit()
        conn.close()
        return redirect(url_for('subscriptions'))  # Перенаправление на страницу подписок

    conn.close()

    # Отправка данных для редактирования в шаблон
    return render_template('edit_subscription.html', subscription=subscription)

@app.route('/edit_expense/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    conn = get_db_connection()
    
    # Получение данных расхода по id
    expense = conn.execute('SELECT * FROM expenses WHERE id = ?', (id,)).fetchone()

    if expense is None:
        return 'Expense not found', 404  # Если расход не найден, возвращаем ошибку

    if request.method == 'POST':
        # Получение новых данных из формы
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        # Обновление расхода в базе данных
        conn.execute('UPDATE expenses SET amount = ?, category = ?, date = ? WHERE id = ?',
                     (amount, category, date, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))  # Перенаправление на главную страницу или 'expenses'

    conn.close()

    # Отправка данных для редактирования в шаблон
    return render_template('edit_expense.html', expense=expense)


@app.route('/edit_income/<int:id>', methods=['GET', 'POST'])
def edit_income(id):
    conn = get_db_connection()
    
    # Получение данных дохода по id
    income = conn.execute('SELECT * FROM incomes WHERE id = ?', (id,)).fetchone()

    if income is None:
        return 'Income not found', 404  # Если доход не найден, возвращаем ошибку

    if request.method == 'POST':
        # Получение новых данных из формы
        source = request.form['source']
        amount = request.form['amount']
        date = request.form['date']

        # Обновление дохода в базе данных
        conn.execute('UPDATE incomes SET source = ?, amount = ?, date = ? WHERE id = ?',
                     (source, amount, date, id))
        conn.commit()
        conn.close()
        return redirect(url_for('incomes'))  # Перенаправление на страницу доходов

    conn.close()

    # Отправка данных для редактирования в шаблон
    return render_template('edit_income.html', income=income)

# Deleting a subscription
@app.route('/delete_subscription/<int:id>', methods=['POST'])
def delete_subscription(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM subscriptions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('subscriptions'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
