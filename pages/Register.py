import streamlit as st
from firebase_auth import register_user

st.set_page_config(page_title="Register", layout="centered")

# Redirect to home if already logged in
if "user" in st.session_state:
    st.switch_page("app.py")

st.title("Register")

email = st.text_input("Email")
password = st.text_input("Password", type="password")
confirm = st.text_input("Confirm Password", type="password")

if st.button("Register"):
    if password != confirm:
        st.error("Passwords do not match")
    else:
        success, message = register_user(email, password)
        if success:
            st.success(message)
            st.info("A verification email has been sent. Please check your inbox before logging in.")
        else:
            st.error(message)

if st.button("Already have an account? Login now"):
    st.switch_page("pages/0_Login.py")
