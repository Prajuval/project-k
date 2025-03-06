from app import app, db, User

with app.app_context():
    # Check if an admin with the username or email already exists
    admin = User.query.filter(
        (User.username == 'youradmin') | (User.email == 'youradmin@example.com')
    ).first()

    if not admin:
        new_admin = User(
            username='youradmin',
            email='youradmin@example.com',
            role='admin'
        )
        new_admin.set_password('12345')
        db.session.add(new_admin)
        db.session.commit()
        print("Admin user created successfully!")
    else:
        print("Admin user already exists.")