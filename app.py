"""
app.py  ─  Streamlit Dashboard for Smart Farming AI Agent
──────────────────────────────────────────────────────────
Farmer-friendly UI with:
  - Farm profile sidebar
  - Today's weather + 7-day forecast
  - Irrigation schedule card
  - Pest alert card
  - Mandi price trend chart
  - Chat box with image upload + voice input
  - Hindi / English language toggle

Run with:   python -m streamlit run frontend/app.py
Backend must be running on http://localhost:8000
"""

import base64

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Voice input is optional: the app must still work if the library
# (or a microphone / PyAudio) is not available.
try:
    import speech_recognition as sr
except Exception:  # pragma: no cover
    sr = None

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="🌾 Smart Farming AI",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000"

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
    /* Big, readable font for farmers */
    .main { font-size: 16px; }
    h1 { font-size: 2rem !important; color: #2d5a27; }
    h2 { font-size: 1.5rem !important; color: #2d5a27; }
    h3 { font-size: 1.2rem !important; }

    /* Metric cards */
    .metric-card {
        background: #f0f7ee;
        color: #1b1b1b;
        border-radius: 12px;
        padding: 16px;
        border-left: 4px solid #4caf50;
        margin-bottom: 10px;
    }
    .alert-card {
        background: #fff3e0;
        color: #1b1b1b;
        border-radius: 12px;
        padding: 16px;
        border-left: 4px solid #ff9800;
        margin-bottom: 10px;
    }
    .chat-user {
        background: #e8f5e9;
        color: #1b1b1b;
        border-radius: 12px;
        padding: 10px 14px;
        margin: 5px 0;
        text-align: right;
    }
    .chat-bot {
        background: #f3f4f6;
        color: #1b1b1b;
        border-radius: 12px;
        padding: 10px 14px;
        margin: 5px 0;
    }
    /* Large buttons */
    .stButton > button {
        font-size: 16px !important;
        padding: 10px 24px !important;
        border-radius: 8px !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ── Session state initialisation ──────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None
if "market_data" not in st.session_state:
    st.session_state.market_data = None
if "data_attempted" not in st.session_state:
    st.session_state.data_attempted = False
if "language" not in st.session_state:
    st.session_state.language = "en"
if "clear_input" not in st.session_state:
    st.session_state.clear_input = False


# ── Helper functions ──────────────────────────────────────────────────────────

def t(en_text: str, hi_text: str) -> str:
    """Return the text in the current language."""
    return hi_text if st.session_state.language == "hi" else en_text


def fetch_weather(lat: float, lon: float) -> dict | None:
    try:
        r = requests.get(
            f"{API_BASE}/api/weather", params={"lat": lat, "lon": lon}, timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_market(crop: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/api/market/{crop.lower()}", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def send_chat(
    query: str,
    profile: dict,
    image_b64: str | None = None,
) -> dict | None:
    payload = {
        "query": query,
        "language": st.session_state.language,
        "image_base64": image_b64,
        "history": st.session_state.chat_history[-6:],  # last 3 turns
        **profile,
    }
    try:
        r = requests.post(f"{API_BASE}/api/chat", json=payload, timeout=60)
        if r.status_code == 200:
            return r.json()
        return {
            "merged_answer": f"Error {r.status_code}: {r.text}",
            "agent_responses": [],
        }
    except requests.exceptions.ConnectionError:
        return {
            "merged_answer": (
                "⚠️ Cannot connect to the backend server.\n\n"
                "Please start the backend first:\n"
                "python -m uvicorn backend.main:app --reload --port 8000"
            ),
            "agent_responses": [],
        }
    except Exception as e:
        return {"merged_answer": f"Request failed: {e}", "agent_responses": []}


def voice_to_text() -> str | None:
    """Capture microphone input and return transcribed text."""
    if sr is None:
        st.warning(t("Voice input is not available.", "आवाज़ से पूछना उपलब्ध नहीं है।"))
        return None

    recogniser = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.info(t("🎤 Listening… speak now", "🎤 सुन रहा हूँ… बोलिए"))
            audio = recogniser.listen(source, timeout=5, phrase_time_limit=10)
        lang_code = "hi-IN" if st.session_state.language == "hi" else "en-IN"
        return recogniser.recognize_google(audio, language=lang_code)
    except sr.WaitTimeoutError:
        st.warning(t("No speech detected.", "कोई आवाज नहीं मिली।"))
    except sr.UnknownValueError:
        st.warning(t("Could not understand the audio.", "आवाज समझ नहीं आई।"))
    except Exception as e:
        # Most common cause: PyAudio / microphone not available
        st.warning(f"Voice input error: {e}")
    return None


# ── Sidebar: Farm Profile ─────────────────────────────────────────────────────

def render_sidebar() -> dict:
    # Language toggle first, so the rest of the sidebar uses the chosen language
    lang = st.sidebar.radio(
        "Language / भाषा",
        options=["English", "हिंदी"],
        horizontal=True,
    )
    st.session_state.language = "hi" if lang == "हिंदी" else "en"

    st.sidebar.title(t("🌾 My Farm Profile", "🌾 मेरा खेत प्रोफाइल"))
    st.sidebar.markdown("---")

    name = st.sidebar.text_input(t("Your Name", "आपका नाम"), value="Ramesh Kumar")
    location = st.sidebar.text_input(
        t("Village / City", "गाँव / शहर"), value="Ludhiana, Punjab"
    )

    col1, col2 = st.sidebar.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=30.9010, format="%.4f", key="lat")
    with col2:
        lon = st.number_input("Longitude", value=75.8573, format="%.4f", key="lon")

    land = st.sidebar.number_input(
        t("Land Size (acres)", "जमीन (एकड़)"),
        min_value=0.5,
        max_value=500.0,
        value=5.0,
        step=0.5,
    )

    soil = st.sidebar.selectbox(
        t("Soil Type", "मिट्टी का प्रकार"),
        options=["alluvial", "black", "red", "laterite", "sandy", "clay", "loamy"],
        index=0,
        format_func=lambda x: x.title(),
    )

    crop = st.sidebar.selectbox(
        t("Current Crop", "मौजूदा फसल"),
        options=["wheat", "rice", "tomato", "cotton", "maize", "mustard", "potato", "onion"],
        format_func=lambda x: x.title(),
    )

    season = st.sidebar.selectbox(
        t("Season", "मौसम"),
        options=["rabi", "kharif", "zaid"],
        format_func=lambda x: x.title(),
    )

    if st.sidebar.button(
        t("🔄 Refresh Weather & Market", "🔄 मौसम और बाज़ार अपडेट करें"),
        use_container_width=True,
    ):
        with st.spinner(t("Fetching data…", "डेटा ला रहे हैं…")):
            st.session_state.weather_data = fetch_weather(lat, lon)
            st.session_state.market_data = fetch_market(crop)
            st.session_state.data_attempted = True

    return dict(
        name=name,
        location=location,
        latitude=lat,
        longitude=lon,
        land_size_acres=land,
        soil_type=soil,
        current_crop=crop,
        season=season,
    )


# ── Weather card ──────────────────────────────────────────────────────────────

def render_weather_card(weather: dict):
    st.markdown(
        f"""
    <div class="metric-card">
    <b>🌡️ {t("Today's Weather", "आज का मौसम")}</b><br>
    🌡️ {weather.get('current_temp_c', '-')}°C &nbsp;|&nbsp;
    💧 {weather.get('current_humidity_pct', '-')}% {t("Humidity", "नमी")}
    </div>
    """,
        unsafe_allow_html=True,
    )

    # 7-day forecast chart
    forecast = weather.get("forecast", [])
    if forecast:
        df = pd.DataFrame(forecast)
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["precipitation_mm"],
                name=t("Rain (mm)", "बारिश (मिमी)"),
                marker_color="#4fc3f7",
                yaxis="y2",
                opacity=0.6,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["temp_max_c"],
                name=t("Max Temp °C", "अधिकतम तापमान"),
                line=dict(color="#ef5350", width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["temp_min_c"],
                name=t("Min Temp °C", "न्यूनतम तापमान"),
                line=dict(color="#42a5f5", width=2, dash="dot"),
            )
        )
        fig.update_layout(
            title=t("7-Day Weather Forecast", "7 दिन का मौसम"),
            height=280,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h"),
            yaxis2=dict(overlaying="y", side="right", title="Rain mm"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Irrigation advice
    if weather.get("irrigation_advice"):
        st.markdown(
            f"""
        <div class="metric-card">
        💧 <b>{t("Irrigation Advice", "सिंचाई सलाह")}</b><br>
        {weather['irrigation_advice'][:400]}
        </div>
        """,
            unsafe_allow_html=True,
        )


# ── Market chart ──────────────────────────────────────────────────────────────

def render_market_card(market: dict, crop: str):
    trend = market.get("trend", "stable")
    trend_icon = {"rising": "📈", "stable": "➡️", "falling": "📉"}.get(trend, "➡️")
    avg = market.get("avg_modal_price", 0)
    change = market.get("change_pct_4wk", 0)

    st.markdown(
        f"""
    <div class="{'metric-card' if trend != 'falling' else 'alert-card'}">
    {trend_icon} <b>{crop.title()} {t("Price Trend", "भाव")}</b>:
    {trend.upper()} ({change:+.1f}% / 4wk)<br>
    💰 {t("Avg Modal Price", "औसत मोडल भाव")}: ₹{avg:.0f}/quintal
    </div>
    """,
        unsafe_allow_html=True,
    )

    prices = market.get("prices", [])
    if prices:
        df = pd.DataFrame(prices)
        fig = px.bar(
            df,
            x="market",
            y="modal_price_inr",
            error_y=df["max_price_inr"] - df["modal_price_inr"],
            error_y_minus=df["modal_price_inr"] - df["min_price_inr"],
            labels={"modal_price_inr": "₹/quintal", "market": "Market"},
            title=t(f"{crop.title()} Prices by Market", f"{crop.title()} मंडी भाव"),
            color_discrete_sequence=["#4caf50"],
            height=250,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)


# ── Chat box ──────────────────────────────────────────────────────────────────

def render_chat(profile: dict):
    st.subheader(t("💬 Ask Your Farming Question", "💬 अपना सवाल पूछें"))

    # Clear the text box after a message was sent
    # (must happen BEFORE the text_input widget is created)
    if st.session_state.clear_input:
        st.session_state.chat_input = ""
        st.session_state.clear_input = False

    # Display history
    for msg in st.session_state.chat_history:
        role_class = "chat-user" if msg["role"] == "user" else "chat-bot"
        icon = "👨‍🌾" if msg["role"] == "user" else "🤖"
        content_html = str(msg["content"]).replace("\n", "<br>")
        st.markdown(
            f'<div class="{role_class}">{icon} {content_html}</div>',
            unsafe_allow_html=True,
        )

    # Input row
    col_text, col_voice, col_send = st.columns([6, 1, 1])

    with col_text:
        user_input = st.text_input(
            t("Type your question…", "अपना सवाल लिखें…"),
            key="chat_input",
            label_visibility="collapsed",
            placeholder=t(
                "e.g. My wheat leaves have yellow stripes, what should I do?",
                "जैसे: मेरे गेहूं की पत्तियों पर पीली धारियाँ हैं, क्या करूँ?",
            ),
        )

    send_clicked = False

    with col_voice:
        if st.button("🎤", help=t("Voice input", "आवाज से पूछें")):
            spoken = voice_to_text()
            if spoken:
                user_input = spoken
                send_clicked = True
                st.success(f"🎤 {spoken}")

    with col_send:
        if st.button(t("Send ▶", "भेजें ▶"), type="primary"):
            send_clicked = True

    # Image upload
    uploaded_image = st.file_uploader(
        t("📷 Upload leaf photo (optional)", "📷 पत्ती की फोटो अपलोड करें (वैकल्पिक)"),
        type=["jpg", "jpeg", "png"],
        help=t(
            "Take a clear photo of the affected leaf for pest/disease detection.",
            "कीट/रोग पहचान के लिए प्रभावित पत्ती की स्पष्ट फोटो लें।",
        ),
    )

    image_b64 = None
    if uploaded_image:
        st.image(
            uploaded_image,
            caption=t("Uploaded Leaf", "अपलोड की गई पत्ती"),
            width=200,
        )
        image_b64 = base64.b64encode(uploaded_image.getvalue()).decode("utf-8")

    # Quick question buttons
    st.markdown(f"**{t('Quick Questions:', 'त्वरित सवाल:')}**")
    qcols = st.columns(3)
    quick_questions = [
        t("How do I irrigate wheat this week?", "इस हफ्ते गेहूं की सिंचाई कैसे करूँ?"),
        t("What pests affect rice in monsoon?", "मानसून में धान में कौन से कीट लगते हैं?"),
        t("When should I sell my crop?", "फसल कब बेचनी चाहिए?"),
    ]
    for i, qcol in enumerate(qcols):
        if qcol.button(quick_questions[i], use_container_width=True, key=f"quick_{i}"):
            user_input = quick_questions[i]
            send_clicked = True

    # Process send: only when a button was pressed
    if send_clicked and user_input and user_input.strip():
        with st.spinner(t("🤔 Thinking…", "🤔 सोच रहा हूँ…")):
            st.session_state.chat_history.append(
                {"role": "user", "content": user_input}
            )

            response = send_chat(user_input, profile, image_b64)
            bot_reply = (
                response.get("merged_answer", "No response.") if response else "Error."
            )

            st.session_state.chat_history.append(
                {"role": "assistant", "content": bot_reply}
            )
            st.session_state.last_agent_responses = (
                response.get("agent_responses", []) if response else []
            )

        st.session_state.clear_input = True
        st.rerun()

    # Agent details of the latest answer (kept after rerun)
    agent_responses = st.session_state.get("last_agent_responses", [])
    if agent_responses:
        with st.expander(t("🔍 Agent Details", "🔍 एजेंट विवरण")):
            for ar in agent_responses:
                st.markdown(
                    f"**{ar.get('agent_name', 'Agent')}** "
                    f"(confidence: {ar.get('confidence', 0):.0%})"
                )
                if ar.get("disclaimer"):
                    st.warning(ar["disclaimer"])
                if ar.get("sources"):
                    st.markdown("**Sources:**")
                    for src in ar["sources"]:
                        st.markdown(
                            f"  📄 *{src.get('document', '')}* — {src.get('snippet', '')}"
                        )


# ── Main layout ───────────────────────────────────────────────────────────────

def main():
    # Sidebar returns the farmer profile dict
    profile = render_sidebar()

    # Header
    st.title(t("🌾 Smart Farming AI Dashboard", "🌾 स्मार्ट खेती AI डैशबोर्ड"))
    st.markdown(
        t(
            f"Welcome, **{profile['name']}** | 📍 {profile['location']} | "
            f"🌱 {profile['current_crop'].title()} | 🗓️ {profile['season'].title()} Season",
            f"नमस्ते, **{profile['name']}** | 📍 {profile['location']} | "
            f"🌱 {profile['current_crop'].title()} | 🗓️ {profile['season'].title()} मौसम",
        )
    )

    # Auto-load weather/market once (not on every rerun, even if the backend is down)
    if not st.session_state.data_attempted:
        with st.spinner(t("Loading weather…", "मौसम लोड हो रहा है…")):
            st.session_state.weather_data = fetch_weather(
                profile["latitude"], profile["longitude"]
            )
            st.session_state.market_data = fetch_market(profile["current_crop"])
            st.session_state.data_attempted = True

    # ── Main grid ────────────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        # Weather
        st.subheader(t("🌤️ Weather & Irrigation", "🌤️ मौसम और सिंचाई"))
        if st.session_state.weather_data:
            render_weather_card(st.session_state.weather_data)
        else:
            st.info(
                t(
                    "Click 'Refresh Weather & Market' in the sidebar to load weather.",
                    "मौसम लोड करने के लिए साइडबार में 'मौसम और बाज़ार अपडेट' बटन दबाएं।",
                )
            )

        # Market
        st.subheader(t("💰 Mandi Price Trends", "💰 मंडी भाव"))
        if st.session_state.market_data:
            render_market_card(st.session_state.market_data, profile["current_crop"])
        else:
            st.info(t("Market data not loaded yet.", "मंडी डेटा अभी लोड नहीं हुआ।"))

    with col_right:
        # Pest alert banner
        st.subheader(t("🐛 Pest & Disease Alert", "🐛 कीट और रोग अलर्ट"))
        st.markdown(
            """
        <div class="alert-card">
        ⚠️ <b>Seasonal Alert:</b><br>
        Watch for <b>aphids</b> on wheat in cool, humid weather.<br>
        Check leaves daily. Use neem oil spray as first defense.<br>
        <i>Upload a leaf photo in the chat to get AI diagnosis.</i>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Farm summary
        st.subheader(t("🗒️ Farm Summary", "🗒️ खेत सारांश"))
        summary_data = {
            t("Crop", "फसल"): profile["current_crop"].title(),
            t("Land", "जमीन"): f"{profile['land_size_acres']} acres",
            t("Soil", "मिट्टी"): profile["soil_type"].title(),
            t("Season", "मौसम"): profile["season"].title(),
            t("Location", "स्थान"): profile["location"],
        }
        for k, v in summary_data.items():
            st.markdown(f"**{k}:** {v}")

        st.markdown("---")
        # Government scheme reminder
        st.markdown(
            """
        <div class="metric-card">
        📞 <b>Kisan Helpline:</b> 1800-180-1551 (Free)<br>
        🌐 <b>PM-KISAN:</b> pmkisan.gov.in<br>
        📱 <b>eNAM:</b> enam.gov.in (live prices)
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── Chat section ─────────────────────────────────────────────────────────
    st.markdown("---")
    render_chat(profile)

    # Footer
    st.markdown(
        "<br><center><small style='color:gray'>"
        "Smart Farming AI — Powered by IBM Granite on watsonx.ai | "
        "Hackathon Prototype 2026 | For guidance only — consult local KVK for decisions"
        "</small></center>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()