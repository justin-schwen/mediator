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
    st.info("https://ai.google.dev/gemini-api/docs/api-key")

# --- 3. CORE LOGIC ---
def extract_text_from_pdf(uploaded_file):
    # Use .getvalue() to avoid file pointer issues in Streamlit
    file_bytes = uploaded_file.getvalue()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = "".join([page.get_text() for page in doc])
    return text.strip()

def get_ise_scores(text, model):
    prompt = f"""
    You are a Senior Systems Engineer. Audit this physical design.
    Rate these 7 metrics from 0-100 based ONLY on the provided specs.
    
    REQUIRED JSON KEYS:
    1. "safety_rating", 2. "reliability_rating", 3. "economy_rating", 
    4. "manufacturability_rating", 5. "environment_rating", 
    6. "human_factors_rating", 7. "lifecycle_rating"

    Return ONLY raw JSON.
    Design Text: {text[:10000]}
    """
    response = model.generate_content(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("AI failed to generate a technical JSON response.")

def calculate_weighted_score(scores):
    weights = {
        "safety_rating": 0.25, "reliability_rating": 0.20, "economy_rating": 0.15, 
        "manufacturability_rating": 0.10, "environment_rating": 0.10, 
        "human_factors_rating": 0.10, "lifecycle_rating": 0.10
    }
    raw_total = sum(scores[k] * w for k, w in weights.items())
    
    # KILL SWITCH
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
    if st.button("Run Engineering Audit"):
        with st.spinner("Analyzing Technical Specifications..."):
            # A. Extract & Check Integrity
            raw_text = extract_text_from_pdf(uploaded_file)
            
            if len(raw_text) < 100:
                st.error("❌ ERROR: PDF is unreadable. This PDF likely contains only images/scans and no text layer. Please use a text-based PDF or OCR the file first.")
                st.stop()
            
            try:
                # B. Score
                scores = get_ise_scores(raw_text, model)
                # C. Math
                final_score, status = calculate_weighted_score(scores)
                
                # D. UI
                st.divider()
                st.metric("Weighted Utility Score", f"{final_score}/100", delta=status)
                st.write("### 📊 Component Ratings")
                st.table([scores])
                
                # E. Specific Memo
                memo_prompt = f"""
                You are a Senior Design Architect. Audit these scores: {scores}.
                Verdict: {status}.
                
                STRICT RULES:
                1. DO NOT define the categories or explain what a score means.
                2. For EVERY score, give a specific recommendation based on the design text.
                3. If a score is low, point out the exact missing detail or technical flaw in the text.
                4. NO performance review headers. NO 'To/From' text.
                
                Design Text: {raw_text[:8000]}
                """
                st.divider()
                st.write("### 📝 Engineering Recommendations")
                st.write(model.generate_content(memo_prompt).text)
                
            except Exception as e:
                st.error(f"Audit Error: {e}")
