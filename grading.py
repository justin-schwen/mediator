import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import json

# --- 1. APP CONFIG ---
st.set_page_config(page_title="ISE Design Mediator", page_icon="🏗️")
st.title("🏗️ Autonomous ISE Design Mediator")

# --- 2. API & MODEL DISCOVERY ---
# This pulls from your Streamlit Secrets
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API Key missing! Add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

# Auto-detect the best available model to avoid 'NotFound' errors
available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
# We prefer Flash for speed, but will take whatever is first if Flash is missing
primary_model_name = next((m for m in available_models if "flash" in m.lower()), available_models[0])
model = genai.GenerativeModel(primary_model_name)

with st.sidebar:
    st.success(f"Connected to: {primary_model_name}")
    st.info("Formula: 25% Safety (70% Floor) + Weighted ISE Metrics")

# --- 3. CORE LOGIC ---
def extract_text_from_pdf(uploaded_file):
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join([page.get_text() for page in doc])

def get_ise_scores(text):
    prompt = f"""
    Analyze this engineering design. Return ONLY a JSON object. 
    Metrics (0-100): s_val (Safety), r_val (Reliability), e_val (Economy), 
    m_val (Manufacturability), v_val (Environment), h_val (Human Factors), l_val (Lifecycle).
    Design Text: {text[:10000]}
    """
    response = model.generate_content(prompt)
    clean_json = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_json)

def calculate_weighted_score(scores):
    # THE PERFECTED FORMULA
    # Score = C_safety * sum(w_i * x_i)
    weights = {"s": 0.25, "r": 0.20, "e": 0.15, "m": 0.10, "v": 0.10, "h": 0.10, "l": 0.10}
    
    # Kill Switch: If Safety is under 70, the design is an automatic failure
    if scores['s_val'] < 70:
        return 0, "REJECTED (CRITICAL SAFETY FAILURE)"
    
    total = sum(scores[f"{k}_val"] * w for k, w in weights.items())
    
    if total >= 85: status = "OPTIMAL"
    elif total >= 75: status = "MARGINAL"
    else: status = "REJECTED"
    return round(total, 2), status

# --- 4. UI LOOP ---
uploaded_file = st.file_uploader("Upload Design PDF", type="pdf")

if uploaded_file:
    if st.button("Run Audit"):
        with st.spinner(f"Auditing with {primary_model_name}..."):
            try:
                # A. Extract
                raw_text = extract_text_from_pdf(uploaded_file)
                # B. Score
                scores = get_ise_scores(raw_text)
                # C. Math
                final_score, status = calculate_weighted_score(scores)
                
                # D. Display Results
                st.divider()
                col1, col2 = st.columns(2)
                col1.metric("Final ISE Score", f"{final_score}/100")
                col2.subheader(f"Status: {status}")
                
                st.write("### Qualitative Metric Breakdown")
                st.json(scores)
                
                # E. Final Memo
                persona = "Brutal Auditor" if "REJECTED" in status else "Collaborative Architect"
                memo_prompt = f"Persona: {persona}. Score: {final_score}. Status: {status}. Scores: {scores}. Write the audit memo."
                st.markdown("### 📝 Final Audit Memo")
                st.write(model.generate_content(memo_prompt).text)
                
            except Exception as e:
                st.error(f"Logic Error: {e}")
                st.write("Debug: Check if your PDF has readable text or if the API limit was hit.")
