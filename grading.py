import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import json
import re

# --- 1. APP CONFIG ---
st.set_page_config(page_title="ISE Technical Auditor", page_icon="🏗️")
st.title("🏗️ Autonomous ISE Design Auditor")

# --- 2. PEER LOGIN ---
with st.sidebar:
    st.header("🔑 Authentication")
    user_api_key = st.text_input("Enter Gemini API Key", type="password")
    st.divider()
    st.info("Formula: 25% Safety (70% Floor) + 75% Weighted ISE Metrics")

# --- 3. CORE LOGIC ---
def extract_text_from_pdf(uploaded_file):
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join([page.get_text() for page in doc])

def get_ise_scores(text, model):
    prompt = f"""
    You are a Senior Systems Engineer. Audit this PHYSICAL PRODUCT/MACHINE design.
    Rate these 7 engineering metrics from 0-100. 
    
    IMPORTANT: This is NOT a performance review of a person. 
    Do not use words like 'empathy', 'humility', or 'collaboration'.
    
    JSON KEYS REQUIRED:
    1. "safety_rating": (Risk of failure, thermal/mechanical safety)
    2. "reliability_rating": (Durability, MTBF, structural integrity)
    3. "economy_rating": (Unit cost, production budget, ROI)
    4. "manufacturability_rating": (Ease of assembly, COTS parts)
    5. "environment_rating": (Carbon footprint, recyclability)
    6. "human_factors_rating": (User ergonomics, visibility, UI)
    7. "lifecycle_rating": (Maintenance, parts availability)

    Return ONLY a raw JSON object.
    Text: {text[:10000]}
    """
    response = model.generate_content(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("AI failed to generate a technical JSON response.")

def calculate_weighted_score(scores):
    # FORMULA: Score = C_safety * sum(w_i * x_i)
    weights = {
        "safety_rating": 0.25, "reliability_rating": 0.20, "economy_rating": 0.15, 
        "manufacturability_rating": 0.10, "environment_rating": 0.10, 
        "human_factors_rating": 0.10, "lifecycle_rating": 0.10
    }
    
    # THE KILL SWITCH
    if scores['safety_rating'] < 70:
        return 0, "CRITICAL SAFETY FAILURE"
    
    total = sum(scores[k] * w for k, w in weights.items())
    
    if total >= 85: status = "OPTIMAL"
    elif total >= 75: status = "MARGINAL"
    else: status = "REJECTED"
    return round(total, 2), status

# --- 4. UI LOOP ---
if not user_api_key:
    st.warning("👈 Enter your Gemini API Key in the sidebar.")
    st.stop()

try:
    genai.configure(api_key=user_api_key)
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    primary_model_name = next((m for m in available_models if "flash" in m.lower()), available_models[0])
    model = genai.GenerativeModel(primary_model_name)
except Exception as e:
    st.error(f"Authentication Error: {e}")
    st.stop()

uploaded_file = st.file_uploader("Upload Design PDF", type="pdf")

if uploaded_file:
    if st.button("Run Engineering Audit"):
        with st.spinner("Analyzing Technical Specifications..."):
            try:
                raw_text = extract_text_from_pdf(uploaded_file)
                scores = get_ise_scores(raw_text, model)
                final_score, status = calculate_weighted_score(scores)
                
                st.divider()
                st.metric("Final ISE Design Score", f"{final_score}/100", delta=status)
                st.write("### Component Scores")
                st.table([scores])
                
                role = "Chief Compliance Officer" if final_score == 0 else "Senior Systems Architect"
                memo_prompt = f"""
                You are a {role}. Write a TECHNICAL AUDIT REPORT for the provided design.
                
                RULES:
                1. DO NOT use a 'To/From/Subject' memo header.
                2. DO NOT mention 'Collaborative Architect' or 'Performance Review'.
                3. Focus ONLY on the engineering scores: {scores}.
                4. Analyze the machine's technical status: {status}.
                5. Use professional engineering terminology.
                """
                
                st.markdown("### 📝 Technical Audit Report")
                st.write(model.generate_content(memo_prompt).text)
                
            except Exception as e:
                st.error(f"Audit Error: {e}")
