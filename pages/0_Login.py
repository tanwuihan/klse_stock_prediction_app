import streamlit as st
from firebase_auth import login_user, resend_verification

st.set_page_config(page_title="Login", layout="centered")

# Already logged in → redirect to app
if "user" in st.session_state:
    st.switch_page("app.py")

st.title("Login")

email = st.text_input("Email")
password = st.text_input("Password", type="password")

if st.button("Login"):
    success, message, user_obj = login_user(email, password)
    if success:
        st.success(message)
        st.switch_page("pages/1_Predict.py")
    else:
        st.error(message)
        if user_obj:
            if st.button("Resend verification email"):
                ok, msg = resend_verification(user_obj)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

if st.button("Don't have an account? Register here"):
    st.switch_page("pages/Register.py")
