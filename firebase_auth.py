import streamlit as st
from firebase_admin import auth as admin_auth, credentials, initialize_app, _apps
import pyrebase
import requests

# ✅ Firebase Admin SDK Init (Safe, delayed execution)
@st.cache_resource
def init_firebase():
    if not _apps:
        cred = credentials.Certificate("firebase_credentials.json")
        initialize_app(cred)

# ✅ Pyrebase config
firebaseConfig = {
    "apiKey": "AIzaSyD7gGVxzSNgWcw_kODl9v0Eej1GNZ3sPIM",
    "authDomain": "klse-prediction.firebaseapp.com",
    "projectId": "klse-prediction",
    "storageBucket": "klse-prediction.appspot.com",
    "messagingSenderId": "859647468132",
    "appId": "1:859647468132:web:2a63a8938e63dc26c5f571",
    "measurementId": "G-0JWY4RS2HZ",
    "databaseURL": ""
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth_pyre = firebase.auth()

# ✅ Login user with verification check
def login_user(email, password):
    try:
        user = auth_pyre.sign_in_with_email_and_password(email, password)

        # Check email verification using Firebase Identity Toolkit
        api_key = firebaseConfig["apiKey"]
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"idToken": user['idToken']}
        resp = requests.post(url, json=payload, headers=headers)
        info = resp.json()

        if not info['users'][0]['emailVerified']:
            return False, "Email not verified", user
        else:
            st.session_state["user"] = user
            st.session_state["email"] = email
            return True, "Login successful", None
    except Exception:
        return False, "Login failed. Check email or password.", None

# ✅ Register user and send verification email
def register_user(email, password):
    try:
        user = auth_pyre.create_user_with_email_and_password(email, password)
        auth_pyre.send_email_verification(user['idToken'])
        return True, "Registration successful. Please verify your email before logging in."
    except Exception as e:
        error_msg = str(e)
        if "EMAIL_EXISTS" in error_msg:
            return False, "Email already exists. Please log in instead."
        elif "WEAK_PASSWORD" in error_msg:
            return False, "Password should be at least 6 characters."
        elif "INVALID_EMAIL" in error_msg:
            return False, "Invalid email format."
        else:
            return False, "Registration failed: " + error_msg

# ✅ Resend verification email
def resend_verification(user):
    try:
        auth_pyre.send_email_verification(user['idToken'])
        return True, "Verification email resent. Please check your inbox."
    except Exception:
        return False, "Failed to resend verification email."

# ✅ Logout
def logout_user():
    if "user" in st.session_state:
        del st.session_state["user"]
        st.success("Successfully logged out.")
        st.rerun()

# ✅ Check login status
def ensure_login():
    return "user" in st.session_state
