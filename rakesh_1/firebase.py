import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin with your credentials file
cred = credentials.Certificate("./canteen.json")
firebase_admin.initialize_app(cred)
db_firebase = firestore.client()

def store_user_registration(user):
    doc_ref = db_firebase.collection("users").document(str(user.id))
    doc_ref.set({
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": firestore.SERVER_TIMESTAMP
    })

def log_user_login(user):
    doc_ref = db_firebase.collection("login_logs").document()
    doc_ref.set({
        "user_id": user.id,
        "username": user.username,
        "login_time": firestore.SERVER_TIMESTAMP
    })