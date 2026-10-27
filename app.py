"""Streamlit UI for the AutoGen Weather News Agent."""
import asyncio
import os
import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from weather_news import run_weather_news

load_dotenv()
st.set_page_config(page_title="Weather News Agent", page_icon="🌦️", layout="wide")

left, right = st.columns([5, 2])
with left:
    st.title("🌦️ AutoGen Weather News Agent")
    st.caption("Search recent weather-related news and summarize the findings in three short lines.")
with right:
    now = datetime.now().astimezone()
    st.markdown(
        f"<div style='text-align:right;padding-top:18px;color:#64748b'>"
        f"<div style='font-size:0.8rem'>LOCAL DATE &amp; TIME</div>"
        f"<div style='font-size:1.05rem;font-weight:600;color:#0f172a'>{now:%d %b %Y}</div>"
        f"<div style='font-size:0.95rem'>{now:%I:%M:%S %p %Z}</div></div>",
        unsafe_allow_html=True,
    )

st.divider()
with st.container(border=True):
    st.subheader("Search weather news")
    with st.form("weather_news_form"):
        city = st.text_input("City", placeholder="e.g., Chennai")
        submitted = st.form_submit_button("🔎 Search weather news", type="primary")

if submitted:
    city = city.strip()
    if not city:
        st.warning("Please enter a city name.")
    elif not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is missing. Add it to your local .env file, then restart Streamlit.")
    else:
        started = time.perf_counter()
        try:
            with st.spinner(f"Searching news for {city} and asking the agent to summarize it..."):
                events, answer = asyncio.run(run_weather_news(city))
            elapsed = time.perf_counter() - started
            completed = datetime.now().astimezone()

            st.markdown("### Weather news results")
            meta_left, meta_right = st.columns([3, 2])
            with meta_left:
                st.caption(f"📍 **City:** {city}")
                st.caption(f"🕒 **Response generated:** {completed:%d %b %Y, %I:%M:%S %p %Z}")
            with meta_right:
                st.caption(f"⏱️ **Total processing time:** {elapsed:.2f} seconds")
            st.code(answer, language="text")

            with st.expander("🔍 Agent execution trace — tool call and response"):
                if not events:
                    st.info("No AutoGen events were returned.")
                for index, event in enumerate(events, start=1):
                    kind = event.__class__.__name__
                    st.markdown(f"**{index}. {kind}**")
                    content = getattr(event, "content", None)
                    if content is not None:
                        st.code(str(content), language="text")
                    elif kind == "TaskResult":
                        st.code(str(getattr(event, "messages", event)), language="text")
                    else:
                        st.code(str(event), language="text")
        except Exception as exc:
            st.error(f"Agent run failed: {type(exc).__name__}: {exc}")
            st.info("Check your API key, installed packages, internet connection, and model access.")
