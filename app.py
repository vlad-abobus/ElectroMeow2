from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Ініціалізація бази даних
def init_db():
    if not os.path.exists('database.db'):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Таблиця користувачів
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                address TEXT,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        
        # Таблиця товарів
        cursor.execute('''
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                image_url TEXT
            )
        ''')
        
        # Таблиця замовлень
        cursor.execute('''
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                total_price REAL,
                status TEXT DEFAULT 'new',
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        
        # Додаємо тестові товари
        cursor.executemany('''
            INSERT INTO products (name, description, price, image_url)
            VALUES (?, ?, ?, ?)
        ''', [
            ('USB Флешка MICRODRIVE', '32ГБ, Жовтий, Чорний, Сріблястий', 250, 'https://img.kwcdn.com/product/Fancyalgo/VirtualModelMatting/e3eb64364ee80182ea84fc76dcc224e4.jpg'),
            ('Присоска для телефону', 'Чорна, підійде до будь-якого телефону', 80, 'https://img.kwcdn.com/product/fancy/7f31d388-7840-4614-a193-6af7aa7489cc.jpg')
        ])
        
        # Додаємо адміна
        cursor.execute('''
            INSERT INTO users (username, email, phone, address, password, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'Admin', 
            'admin@example.com', 
            '+380000000000', 
            'Адмінська адреса', 
            generate_password_hash('admin2325'), 
            1
        ))
        
        conn.commit()
        conn.close()

init_db()

# Функція для підключення до БД
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Головна сторінка
@app.route('/')
def index():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    db.close()
    return render_template('index.html', products=products)

# Реєстрація
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        password = generate_password_hash(request.form['password'])
        
        try:
            db = get_db()
            db.execute('''
                INSERT INTO users (username, email, phone, address, password)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, phone, address, password))
            db.commit()
            db.close()
            
            session['user_email'] = email
            flash('Реєстрація успішна!', 'success')
            return redirect(url_for('profile'))
        except sqlite3.IntegrityError:
            flash('Користувач з таким email вже існує', 'error')
        
    return render_template('register.html')

# Вхід в акаунт
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_email'] = user['email']
            flash('Ви успішно увійшли в систему', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Невірний email або пароль', 'error')
    
    return render_template('login.html')

# Вихід з акаунту
@app.route('/logout')
def logout():
    session.pop('user_email', None)
    flash('Ви вийшли з системи', 'success')
    return redirect(url_for('index'))

# Профіль
@app.route('/profile')
def profile():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (session['user_email'],)).fetchone()
    db.close()
    
    if not user:
        return redirect(url_for('login'))
    
    return render_template('profile.html', user=user)

# Редагування профілю
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (session['user_email'],)).fetchone()
    
    if request.method == 'POST':
        username = request.form['name']
        phone = request.form['phone']
        address = request.form['address']
        
        db.execute('''
            UPDATE users 
            SET username = ?, phone = ?, address = ?
            WHERE email = ?
        ''', (username, phone, address, session['user_email']))
        db.commit()
        db.close()
        
        flash('Профіль успішно оновлено', 'success')
        return redirect(url_for('profile'))
    
    db.close()
    return render_template('edit_profile.html', user=user)

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (session['user_email'],)).fetchone()
    
    if not user:
        flash('Користувача не знайдено. Увійдіть або зареєструйтесь знову.', 'error')
        db.close()
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity', 1))
        
        product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        
        if product:
            total_price = product['price'] * quantity + 80  # +80 грн за доставку
            
            db.execute('''
                INSERT INTO orders (user_id, product_id, quantity, total_price)
                VALUES (?, ?, ?, ?)
            ''', (user['id'], product_id, quantity, total_price))
            db.commit()
            
            flash('Замовлення успішно оформлено!', 'success')
            db.close()
            return redirect(url_for('profile'))

    cart_items = db.execute('''
        SELECT products.*, orders.quantity, orders.total_price, orders.id as order_id
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE user_id = ? AND status = 'new'
    ''', (user['id'],)).fetchall()

    total = sum(item['total_price'] for item in cart_items)
    db.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total)

# Видалення з кошика
@app.route('/remove_from_cart/<int:order_id>')
def remove_from_cart(order_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    db.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    db.commit()
    db.close()
    
    flash('Товар видалено з кошика', 'success')
    return redirect(url_for('cart'))

# Адмін-панель
@app.route('/admin')
def admin():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (session['user_email'],)).fetchone()
    
    if not user or not user['is_admin']:
        flash('Доступ заборонено', 'error')
        return redirect(url_for('profile'))
    
    users = db.execute('SELECT * FROM users').fetchall()
    orders = db.execute('''
        SELECT orders.*, products.name as product_name, users.username 
        FROM orders
        JOIN products ON orders.product_id = products.id
        JOIN users ON orders.user_id = users.id
        ORDER BY order_date DESC
    ''').fetchall()
    
    db.close()
    
    return render_template('users.html', users=users, orders=orders)

# Авторизація адміна
@app.route('/admin_login', methods=['POST'])
def admin_login():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    admin_code = request.form.get('admin_code')
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (session['user_email'],)).fetchone()
    
    if admin_code == 'admin2325':
        db.execute('UPDATE users SET is_admin = 1 WHERE email = ?', (session['user_email'],))
        db.commit()
        db.close()
        return redirect(url_for('admin'))
    else:
        flash('Невірний код адміністратора', 'error')
        return redirect(url_for('profile'))

# Контакти
@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

if __name__ == '__main__':
    app.run(debug=True)
