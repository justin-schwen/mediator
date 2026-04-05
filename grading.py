import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import json

# --- 1. APP CONFIG ---
st.set_page_config(page_title="ISE Design Mediator", page_icon="🏗️")
st.title("🏗️ Autonomous ISE Design Mediator")

# --- 2. PEER LOGIN (API KEY INPUT) ---
with st.sidebar:
    st.header("🔑 Authentication")
    user_api_key = st.text_input("Enter your Gemini API Key", type="password", help="Get your key at aistudio.google.com")
    st.divider()
    st.info("Formula: 25% Safety (70% Floor) + Weighted ISE Metrics")

# --- 3. CORE LOGIC ---
def extract_text_from_pdf(uploaded_file):
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join([page.get_text() for page in doc])

def get_ise_scores(text, model):
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
    # THE PERFECTED FORMULA: Score = C_safety * sum(w_i * x_i)
    weights = {"s": 0.25, "r": 0.20, "e": 0.15, "m": 0.10, "v": 0.10, "h": 0.10, "l": 0.10}
    
    if scores['s_val'] < 70:
        return 0, "REJECTED (CRITICAL SAFETY FAILURE)"
    
    total = sum(scores[f"{k}_val"] * w for k, w in weights.items())
    
    if total >= 85: status = "OPTIMAL"
    elif total >= 75: status = "MARGINAL"
    else: status = "REJECTED"
    return round(total, 2), status

# --- 4. UI LOOP ---
if not user_api_key:
    st.warning("👈 Please enter your Gemini API Key in the sidebar to unlock the auditor.")
    st.stop()

# Configure the AI using the USER'S key
try:
    genai.configure(api_key=user_api_key)
    # Just grab the first available flash model for the user
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    primary_model_name = next((m for m in available_models if "flash" in m.lower()), available_models[0])
    model = genai.GenerativeModel(primary_model_name)
except Exception as e:
    st.error("Invalid API Key or Connection Error. Please check your credentials.")
    st.stop()

uploaded_file = st.file_uploader("Upload Design PDF", type="pdf")

if uploaded_file:
    if st.button("Run Audit"):
        with st.spinner(f"Auditing via {primary_model_name}..."):
            try:
                raw_text = extract_text_from_pdf(uploaded_file)
                scores = get_ise_scores(raw_text, model)
                final_score, status = calculate_weighted_score(scores)
                
                st.divider()
                col1, col2 = st.columns(2)
                col1.metric("Final ISE Score", f"{final_score}/100")
                col2.subheader(f"Status: {status}")
                
                st.write("### Qualitative Metric Breakdown")
                st.json(scores)
                
                persona = "Brutal Auditor" if "REJECTED" in status else "Collaborative Architect"
                memo_prompt = f"Persona: {persona}. Score: {final_score}. Status: {status}. Scores: {scores}. Write the audit memo."
                st.markdown("### 📝 Final Audit Memo")
                st.write(model.generate_content(memo_prompt).text)
                
            except Exception as e:
                st.error(f"Audit Failed: {e}")
