"""
Part 4 — minimal web interface (one page, two tabs).

Run:
    export GEMINI_API_KEY=AIza...
    streamlit run streamlit_app.py

Requires lead_model.pkl to exist for the "Lead Scoring" tab — run
train.py first (see part3-ml/train.py) and copy lead_model.pkl next
to this file.

No styling on purpose — the brief says "no styling points".
"""

import streamlit as st
import joblib
import pandas as pd
import os

from rag import Retriever, answer_question

st.title("MGC Sales Assistant")

tab1, tab2 = st.tabs(["Document Assistant", "Lead Scoring"])

# ---------------------------------------------------------------
# Tab 1: Document Assistant (Part 1)
# ---------------------------------------------------------------
with tab1:
    st.caption("Ask a question about price, payment plans, or booking policy.")

    if "retriever" not in st.session_state:
        st.session_state.retriever = Retriever()

    question = st.text_input("Ask a question:")

    if st.button("Ask") and question.strip():
        with st.spinner("Checking the documents..."):
            try:
                answer, retrieved, evidence = answer_question(question, st.session_state.retriever)
            except RuntimeError as e:
                st.error(str(e))
            else:
                st.subheader("Answer")
                st.write(answer)
                st.caption(f"Evidence: {evidence}")

                if retrieved:
                    st.subheader("Sources")
                    seen = set()
                    for r in retrieved:
                        cite = r.chunk.citation()
                        if cite in seen:
                            continue
                        seen.add(cite)
                        st.markdown(f"- {cite}  _(similarity {r.score:.2f})_")

                    with st.expander("Retrieved context (for transparency)"):
                        for r in retrieved:
                            st.markdown(f"**{r.chunk.citation()}**")
                            st.text(r.chunk.text)

# ---------------------------------------------------------------
# Tab 2: Lead Scoring (Part 3 model + Part 4 bonus)
# ---------------------------------------------------------------
with tab2:
    st.caption("Enter a lead's details to see its likelihood of converting.")

    MODEL_PATH = "lead_model.pkl"
    if not os.path.exists(MODEL_PATH):
        st.error(
            "lead_model.pkl not found. Run train.py first (in part3-ml/), "
            "then copy lead_model.pkl into this folder."
        )
    else:
        model = joblib.load(MODEL_PATH)

        col1, col2 = st.columns(2)
        with col1:
            source = st.selectbox("Source", [
                "Billboard", "Expo Stall", "Facebook Ads", "Google Search",
                "Instagram", "Property Portal", "Referral", "Walk-in", "WhatsApp Campaign",
            ])
            city = st.selectbox("City", [
                "islamabad", "rawalpindi", "lahore", "karachi", "peshawar",
                "faisalabad", "multan", "gujranwala", "abbottabad",
            ])
            area = st.text_input("Area", "Bahria Town")
            property_type = st.selectbox("Property type", [
                "Apartment", "Commercial Shop", "Farmhouse", "Penthouse", "Plot", "Villa",
            ])
            budget_pkr_lac = st.number_input("Budget (PKR lac)", min_value=0.0, value=150.0)
            bedrooms = st.number_input("Bedrooms (0 if not applicable)", min_value=0, value=2)

        with col2:
            first_response_minutes = st.number_input("First response time (minutes)", min_value=0.0, value=30.0)
            calls_made = st.number_input("Calls made", min_value=0, value=2)
            total_call_seconds = st.number_input("Total call seconds", min_value=0, value=120)
            whatsapp_replies = st.number_input("WhatsApp replies", min_value=0, value=1)
            site_visits = st.number_input("Site visits", min_value=0, value=0)
            agent_experience_years = st.number_input("Agent experience (years)", min_value=0.0, value=2.0)

        col3, col4, col5 = st.columns(3)
        with col3:
            is_overseas = st.checkbox("Overseas buyer")
        with col4:
            referred_by_existing_client = st.checkbox("Referred by existing client")
        with col5:
            has_financing_approved = st.checkbox("Financing approved")

        if st.button("Get Score"):
            row = pd.DataFrame([{
                "source": source,
                "city": city,
                "area": area,
                "property_type": property_type,
                "budget_pkr_lac": budget_pkr_lac,
                "bedrooms": bedrooms,
                "first_response_minutes": first_response_minutes,
                "calls_made": calls_made,
                "total_call_seconds": total_call_seconds,
                "whatsapp_replies": whatsapp_replies,
                "site_visits": site_visits,
                "agent_experience_years": agent_experience_years,
                "is_overseas": int(is_overseas),
                "referred_by_existing_client": int(referred_by_existing_client),
                "has_financing_approved": int(has_financing_approved),
            }])
            score = model.predict_proba(row)[0, 1]
            st.subheader(f"Conversion likelihood: {score:.1%}")
            st.progress(min(score, 1.0))
