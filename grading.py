import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import json
import re

# --- 1. APP CONFIG ---
st.set_page_config(page_title="ISE Technical Auditor", page_icon="🏗️", layout="wide")
st.title("🏗️ Autonomous ISE Design Auditor")

# --- 2. PEER LOGIN ---
with st.sidebar:
    st.header("🔑 Authentication")
    user_api_key = st.text_input("Enter Gemini API Key", type="password")
    st.divider()
    st.info("Logic: 70% Safety Floor. Scores are independent; Status is holistic.")

# --- 3. CORE LOGIC ---
def extract_text_from_pdf(uploaded_file):
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join([page.get_text() for page in doc])

def get_ise_scores(text, model):
    prompt = f"""
    You are a Technical Design Auditor. Analyze this physical product/machine design.
    Rate the following 7 engineering metrics from 0 to 100 based ONLY on the provided text.
    
    REQUIRED JSON KEYS:
    1. "safety_rating": (Risk of failure, thermal/mechanical safety)
    2. "reliability_rating": (Structural integrity, MTBF, durability)
    3. "economy_rating": (Unit cost, MSRP, production budget)
    4. "manufacturability_rating": (Ease of assembly, COTS parts)
    5. "environment_rating": (Recyclability, carbon footprint)
    6. "human_factors_rating": (User ergonomics, visibility, UI)
    7. "lifecycle_rating": (Maintenance, longevity, parts replacement)

    Return ONLY a JSON object.
    Text: {text[:10000]}
    """
    response = model.generate_content(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("AI failed to generate technical JSON scores.")

def calculate_weighted_score(scores):
    weights = {
        "safety_rating": 0.25, "reliability_rating": 0.20, "economy_rating": 0.15, 
        "manufacturability_rating": 0.10, "environment_rating": 0.10, 
        "human_factors_rating": 0.10, "lifecycle_rating": 0.10
    }
    
    # Calculate the raw weighted total
    raw_total = sum(scores[k] * w for k, w in weights.items())
    
    # THE KILL SWITCH: Only affects the final verdict/status, not the component scores
    if scores['safety_rating'] < 70:
        return 0, "REJECTED (CRITICAL SAFETY FAILURE)"
    
    if raw_total >= 85: status = "OPTIMAL DESIGN"
    elif raw_total >= 75: status = "MARGINAL DESIGN"
    else: status = "REJECTED DESIGN"
    return round(raw_total, 2), status

# --- 4. UI LOOP ---
if not user_api_key:
    st.warning("👈 Enter API Key in the sidebar.")
    st.stop()

try:
    genai.configure(api_key=user_api_key)
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    primary_model_name = next((m for m in available_models if "flash" in m.lower()), available_models[0])
    model = genai.GenerativeModel(primary_model_name)
except Exception as e:
    st.error(f"Auth Error: {e}")
    st.stop()

uploaded_file = st.file_uploader("Upload Design PDF", type="pdf")

if uploaded_file:
    if st.button("Execute Technical Audit"):
        with st.spinner("Analyzing Technical Specifications..."):
            try:
                raw_text = extract_text_from_pdf(uploaded_file)
                scores = get_ise_scores(raw_text, model)
                final_score, status = calculate_weighted_score(scores)
                
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Weighted Utility Score", f"{final_score}/100")
                with col2:
                    st.subheader(f"Verdict: {status}")
                
                st.write("### 📊 Raw Component Ratings")
                st.table([scores])
                
                memo_prompt = f"""
                You are a Senior Systems Architect. Analyze the following design scores: {scores}.
                Final Verdict: {status} (Final Score: {final_score}).

                STRICT GUIDELINES FOR THE REPORT:
                1. DO NOT define or explain what the categories mean (e.g., don't explain what 'Safety' is). 
                2. For EVERY category in the scores, provide a specific engineering recommendation for improvement.
                3. Your recommendations MUST be based on the technical flaws or gaps identified in the provided design text. 
                4. If a score is high, explain the specific technical win from the text.
                5. If a score is low, identify the specific failure point or missing specification in the design.
                6. No 'To/From' headers. No performance review language.
                
                Design Text: {raw_text[:8000]}
                """
                
                st.divider()
                st.write("### 📝 Engineering Audit & Recommendations")
                st.write(model.generate_content(memo_prompt).text)
                
            except Exception as e:
                st.error(f"Error: {e}")
