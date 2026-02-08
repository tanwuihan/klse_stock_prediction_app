import streamlit as st
from firebase_auth import logout_user
import streamlit.components.v1 as components

# ✅ Must be the first Streamlit command
st.set_page_config(page_title="KLSE Stock Predictor", layout="centered")

# ✅ Sidebar content
st.sidebar.title("📊 KLSE App")

# ✅ Show logout button only if logged in
if "user" in st.session_state:
    st.sidebar.markdown(f"**👤 {st.session_state['user']['email']}**")
    if st.sidebar.button("🚪 Logout"):
        logout_user()

# ✅ Custom CSS for fade-in animations
st.markdown("""
<style>
@keyframes fadeInUp {
  from { opacity: 0; transform: translate3d(0, 30px, 0); }
  to { opacity: 1; transform: none; }
}
.fade-in {
  animation: fadeInUp 1s ease forwards;
  opacity: 0;
}
.fade-in-delay-1 { animation-delay: 0.3s; }
.fade-in-delay-2 { animation-delay: 0.6s; }
.fade-in-delay-3 { animation-delay: 0.9s; }
.fade-in-delay-4 { animation-delay: 1.2s; }
</style>
""", unsafe_allow_html=True)

# ✅ Main content with fade-in effect
st.markdown('<h1 class="fade-in">📈 KLSE Stock Prediction System</h1>', unsafe_allow_html=True)

st.markdown("""
<div class="fade-in fade-in-delay-1">
Welcome to the <b>KLSE Stock Prediction App</b> 🎉  
</div>

<div class="fade-in fade-in-delay-2">
This system helps you:
</div>

<ul class="fade-in fade-in-delay-2">
<li>🔮 <b>Predict future stock prices</b> using AI models (Prophet, XGBoost, LSTM).</li>
<li>🚀 <b>Identify the most spiking stocks</b> in KLSE today.</li>
<li>🧾 <b>Summarize company financial reports</b> into clear insights.</li>
<li>🤖 <b>Ask the FAQ chatbot</b> for guidance and stock advice.</li>
</ul>
""", unsafe_allow_html=True)

# ✅ Footer
if "user" in st.session_state:
    st.success(f"✅ You are logged in as {st.session_state['user']['email']}.")
else:
    st.info("ℹ️ You are not logged in. Please use the sidebar to Login or Register.")
