# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import datetime
from functools import wraps
from firebase import store_user_registration, log_user_login

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///canteen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow()}

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')  # 'student', 'teacher', or 'admin'
    orders = db.relationship('Order', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))  # breakfast, lunch, snack, etc.
    available = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(200))
    
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    pickup_date = db.Column(db.DateTime, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, completed, cancelled
    unique_code = db.Column(db.String(10), unique=True, nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")
    
    def generate_unique_code(self):
        return secrets.token_hex(5).upper()

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    food_item_id = db.Column(db.Integer, db.ForeignKey('food_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Float, nullable=False)
    food_item = db.relationship('FoodItem')

# Helper functions
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You need to be an admin to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        
        # Basic validation
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        # Log registration only for non-admin users
        if new_user.role != 'admin':
            store_user_registration(new_user)
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            # Log login event in Firebase only for non-admin users
            if user.role != 'admin':
                log_user_login(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Different dashboard view based on user role
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        # Get recent orders for the current user
        recent_orders = Order.query.filter_by(user_id=current_user.id)\
            .order_by(Order.order_date.desc())\
            .limit(5)\
            .all()
        
        # Get active orders (pending or paid)
        active_orders = Order.query.filter_by(user_id=current_user.id)\
            .filter(Order.status.in_(['pending', 'paid']))\
            .order_by(Order.pickup_date)\
            .all()
        
        return render_template('user_dashboard.html', 
                             recent_orders=recent_orders,
                             active_orders=active_orders)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    # Fetch all pending and paid orders
    pending_orders = Order.query.filter_by(status='pending').all()
    paid_orders = Order.query.filter_by(status='paid').all()
    
    # Ensure categories are fetched from the database
    categories = {}
    food_items = FoodItem.query.all()

    for food in food_items:
        if food.category not in categories:
            categories[food.category] = []
        categories[food.category].append(food)

    return render_template(
        'admin_dashboard.html',
        pending_orders=pending_orders,
        paid_orders=paid_orders,
        categories=categories  # Pass categories to the template
    )

@app.route('/menu')
def menu():
    categories = db.session.query(FoodItem.category).distinct().all()
    categories = [category[0] for category in categories]
    
    food_items = {}
    for category in categories:
        food_items[category] = FoodItem.query.filter_by(category=category, available=True).all()
    
    return render_template('menu.html', categories=categories, food_items=food_items)

@app.route('/cart')
@login_required
def cart():
    if 'cart' not in session:
        session['cart'] = []
    
    cart_items = []
    total = 0
    
    for item in session['cart']:
        food_item = FoodItem.query.get(item['food_id'])
        subtotal = food_item.price * item['quantity']
        cart_items.append({
            'food_item': food_item,
            'quantity': item['quantity'],
            'subtotal': subtotal
        })
        total += subtotal
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add_to_cart/<int:food_id>', methods=['POST'])
@login_required
def add_to_cart(food_id):
    if 'cart' not in session:
        session['cart'] = []
    
    quantity = int(request.form.get('quantity', 1))
    
    # Check if item already in cart
    for item in session['cart']:
        if item['food_id'] == food_id:
            item['quantity'] += quantity
            session.modified = True
            flash('Cart updated!', 'success')
            return redirect(url_for('menu'))
    
    # If not in cart, add it
    session['cart'].append({'food_id': food_id, 'quantity': quantity})
    session.modified = True
    
    flash('Item added to cart!', 'success')
    return redirect(url_for('menu'))

@app.route('/remove_from_cart/<int:index>')
@login_required
def remove_from_cart(index):
    if 'cart' in session and 0 <= index < len(session['cart']):
        session['cart'].pop(index)
        session.modified = True
    
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if 'cart' not in session or not session['cart']:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('menu'))
    
    # Calculate cart items and total
    cart_items = []
    total = 0.0
    
    for item in session['cart']:
        food_item = FoodItem.query.get(item['food_id'])
        if food_item:
            subtotal = food_item.price * item['quantity']
            cart_items.append({
                'food_item': food_item,
                'quantity': item['quantity'],
                'subtotal': subtotal
            })
            total += subtotal

    if request.method == 'POST':
        pickup_date = request.form.get('pickup_date')
        pickup_time = request.form.get('pickup_time')
        
        if not pickup_date or not pickup_time:
            flash('Please select both pickup date and time', 'danger')
            return render_template('checkout.html', cart_items=cart_items, total=total)
        
        # Combine date and time
        pickup_datetime = datetime.datetime.strptime(
            f"{pickup_date} {pickup_time}", 
            "%Y-%m-%d %H:%M"
        )
        
        # Create new order
        new_order = Order(
            user_id=current_user.id,
            pickup_date=pickup_datetime,
            total_amount=total,
            status='pending',
            unique_code=secrets.token_hex(5).upper()
        )
        
        # Add order items
        for item in cart_items:
            order_item = OrderItem(
                food_item_id=item['food_item'].id,
                quantity=item['quantity'],
                subtotal=item['subtotal']
            )
            new_order.items.append(order_item)
        
        try:
            db.session.add(new_order)
            db.session.commit()
            session.pop('cart', None)  # Clear the cart
            flash('Order placed successfully!', 'success')
            return redirect(url_for('payment', order_id=new_order.id))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while placing your order. Please try again.', 'danger')
            return render_template('checkout.html', cart_items=cart_items, total=total)
    
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/payment/<int:order_id>', methods=['GET', 'POST'])
@login_required
def payment(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Ensure user owns this order
    if order.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # In a real application, integrate with a payment gateway
        # For this demo, we'll just mark it as paid
        order.status = 'paid'
        db.session.commit()
        
        flash('Payment successful! Your order code is: ' + order.unique_code, 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))
    
    return render_template('payment.html', order=order)

@app.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Ensure user owns this order or is admin
    if order.user_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('order_details.html', order=order)

@app.route('/order_confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Ensure user owns this order
    if order.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('order_confirmation.html', order=order)

@app.route('/admin/manage_menu', methods=['GET'])
@login_required
@admin_required
def manage_menu():
    # Get all food items
    food_items = FoodItem.query.all()
    # Group food items by category
    categories = {}
    for item in food_items:
        if item.category not in categories:
            categories[item.category] = []
        categories[item.category].append(item)
    
    return render_template('admin/manage_menu.html', categories=categories)

@app.route('/admin/add_food', methods=['GET', 'POST'])
@login_required
@admin_required
def add_food():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        category = request.form.get('category')
        available = 'available' in request.form
        image_url = request.form.get('image_url')
        
        new_food = FoodItem(
            name=name,
            description=description,
            price=price,
            category=category,
            available=available,
            image_url=image_url
        )
        
        db.session.add(new_food)
        db.session.commit()
        
        flash('Food item added successfully!', 'success')
        return redirect(url_for('manage_menu'))
    
    return render_template('add_food.html')

@app.route('/admin/edit_food/<int:food_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_food(food_id):
    food_item = FoodItem.query.get_or_404(food_id)
    
    if request.method == 'POST':
        food_item.name = request.form.get('name')
        food_item.description = request.form.get('description')
        food_item.price = float(request.form.get('price'))
        food_item.category = request.form.get('category')
        food_item.available = 'available' in request.form
        food_item.image_url = request.form.get('image_url')
        
        db.session.commit()
        
        flash('Food item updated successfully!', 'success')
        return redirect(url_for('manage_menu'))
    
    return render_template('edit_food.html', food_item=food_item)

@app.route('/admin/delete_food/<int:food_id>')
@login_required
@admin_required
def delete_food(food_id):
    food_item = FoodItem.query.get_or_404(food_id)
    
    db.session.delete(food_item)
    db.session.commit()
    
    flash('Food item deleted successfully!', 'success')
    return redirect(url_for('manage_menu'))

@app.route('/admin/manage_orders')
@login_required
@admin_required
def manage_orders():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    return render_template('manage_orders.html', orders=orders)

@app.route('/admin/update_order_status/<int:order_id>/<status>')
@login_required
@admin_required
def update_order_status(order_id, status):
    order = Order.query.get_or_404(order_id)
    
    if status in ['pending', 'paid', 'completed', 'cancelled']:
        order.status = status
        db.session.commit()
        flash('Order status updated successfully!', 'success')
    else:
        flash('Invalid status', 'danger')
    
    return redirect(url_for('manage_orders'))

@app.route('/admin/delete_order/<int:order_id>')
@login_required
@admin_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    db.session.delete(order)
    db.session.commit()
    
    flash('Order deleted successfully!', 'success')
    return redirect(url_for('manage_orders'))

# Initialize the database
with app.app_context():
    db.create_all()
    
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@example.com', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)