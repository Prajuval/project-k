from flask import Flask, render_template, request, redirect, url_for, flash, session
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Temporary user storage (replace with database in production)
users = {}

@app.route('/')
def index():
    if 'username' in session:
        return render_template('user_dashboard.html', username=session['username'])
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in users and users[username]['password'] == password:
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')  # 'student' or 'teacher'
        # Process the registration including storing user details along with role
        # For example, update the users dictionary:
        if username in users:
            flash('Username already exists.', 'error')
        else:
            users[username] = {'email': email, 'password': password, 'role': role}
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/menu')
def menu():
    menu_items = {
        'breakfast': [
            {'name': 'Masala Dosa', 'price': 40, 'description': 'Crispy rice crepe with spiced potato filling', 'image': '🥞'},
            {'name': 'Poha', 'price': 30, 'description': 'Flattened rice with peanuts and herbs', 'image': '🍚'},
            {'name': 'Sandwich', 'price': 35, 'description': 'Grilled vegetable sandwich', 'image': '🥪'}
        ],
        'lunch': [
            {'name': 'Thali', 'price': 80, 'description': 'Complete meal with roti, rice, dal, and sabzi', 'image': '🍱'},
            {'name': 'Pulao', 'price': 60, 'description': 'Vegetable rice pilaf', 'image': '🍚'},
            {'name': 'Chole Bhature', 'price': 70, 'description': 'Spiced chickpeas with fried bread', 'image': '🥘'}
        ],
        'snacks': [
            {'name': 'Samosa', 'price': 15, 'description': 'Crispy pastry with spiced potato filling', 'image': '🔺'},
            {'name': 'Vada Pav', 'price': 25, 'description': 'Spiced potato patty in a bun', 'image': '🍔'},
            {'name': 'Maggi', 'price': 30, 'description': 'Instant noodles with vegetables', 'image': '🍜'}
        ]
    }
    return render_template('menu.html', menu_items=menu_items)

@app.route('/orders')
def orders():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Example orders data (replace with database query in production)
    user_orders = {
        'pending': [
            {'id': 1, 'items': ['Masala Dosa', 'Samosa'], 'total': 55, 'status': 'pending', 'time': '10:30 AM'},
            {'id': 2, 'items': ['Thali'], 'total': 80, 'status': 'pending', 'time': '12:30 PM'}
        ],
        'completed': [
            {'id': 3, 'items': ['Vada Pav', 'Maggi'], 'total': 55, 'status': 'completed', 'time': 'Yesterday'},
            {'id': 4, 'items': ['Pulao'], 'total': 60, 'status': 'completed', 'time': '2 days ago'}
        ]
    }
    
    return render_template('orders.html', orders=user_orders)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        booking_datetime = request.form.get('booking_datetime')
        # You would collect the cart data (from session/localStorage or database)
        # and add booking_datetime to the order details.
        # For now, we flash a message and redirect to orders.
        flash(f'Order prebooked for {booking_datetime}', 'success')
        return redirect(url_for('orders'))
    
    return render_template('checkout.html')

if __name__ == '__main__':
    app.run(debug=True)