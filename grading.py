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
    # This prompt forces strict mapping to prevent personality-based hallucinations
    prompt = f"""
    You are a Senior Industrial & Systems Engineering (ISE) Auditor. 
    Analyze the technical design text and rate it 0-100 for these EXACT metrics:
    
    1. s_val: SAFETY (Crash safety, thermal runaway, risk mitigation)
    2. r_val: RELIABILITY (MTBF, structural integrity, maintenance)
    3. e_val: ECONOMY (Production cost, MSRP, margins, ROI)
    4. m_val: MANUFACTURABILITY (Assembly, parts commonality, scalability)
    5. v_val: ENVIRONMENT (Sustainability, recycling, carbon footprint)
    6. h_val: HUMAN FACTORS (Ergonomics, user interface, visibility)
    7. l_val: LIFECYCLE (Long-term support, parts replacement)

    Return ONLY a JSON object. No prose.
    Design Text: {text[:10000]}
    """
    response = model.generate_content(prompt)
    clean_json = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_json)

def calculate_weighted_score(scores):
    # THE PERFECTED FORMULA: Score = C_safety * sum(w_i * x_i)
    weights = {{
        "s": 0.25, "r": 0.20, "e": 0.15, 
        "m": 0.10, "v": 0.10, "h": 0.10, "l": 0.10
    }}
    
    # THE KILL SWITCH: If Safety < 70, the design is an automatic failure
    if scores['s_val'] < 70:
        return 0, "REJECTED (CRITICAL SAFETY FAILURE)"
    
    total = sum(scores[f"{{k}}_val"] * w for k, w in weights.items())
    
    if total >= 85: status = "OPTIMAL"
    elif total >= 75: status = "MARGINAL"
    else: status = "REJECTED"
    return round(total, 2), status

# --- 4. UI LOOP ---
if not user_api_key:
    st.warning("👈 Enter your Gemini API Key in the sidebar to unlock the auditor.")
    st.stop()

try:
    genai.configure(api_key=user_api_key)
    # Self-healing model discovery
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    primary_model_name = next((m for m in available_models if "flash" in m.lower()), available_models[0])
    model = genai.GenerativeModel(primary_model_name)
except Exception:
    st.error("Invalid API Key. Please verify your credentials.")
    st.stop()

uploaded_file = st.file_uploader("Upload Design PDF", type="pdf")

if uploaded_file:
    if st.button("Run Extreme Grading Audit"):
        with st.spinner(f"Auditing via {{primary_model_name}}..."):
            try:
                # A. Extract
                raw_text = extract_text_from_pdf(uploaded_file)
                # B. Score (Strict Engineering Mapping)
                scores = get_ise_scores(raw_text, model)
                # C. Math (Weighted Utility + Kill Switch)
                final_score, status = calculate_weighted_score(scores)
                
                # D. Display Results
                st.divider()
                col1, col2 = st.columns(2)
                col1.metric("Final Design Score", f"{{final_score}}/100")
                col2.subheader(f"Status: {{status}}")
                
                st.write("### Component Breakdown")
                st.table([scores])
                
                # E. Final Memo
                # Branching logic for personas based on ISE status
                persona = "Brutal Auditor" if "REJECTED" in status else "Collaborative Architect"
                memo_prompt = f"Persona: {{persona}}. Score: {{final_score}}. Status: {{status}}. Scores: {{scores}}. Write a technical audit memo."
                st.markdown("### 📝 Final Audit Memo")
                st.write(model.generate_content(memo_prompt).text)
                
            except Exception as e:
                st.error(f"Audit Failed: {{e}}")
