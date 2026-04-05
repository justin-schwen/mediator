import streamlit as st
import google.generativeai as genai
import fitz  # This is the PyMuPDF library you just installed
import json

# --- 1. APP CONFIG ---
st.set_page_config(page_title="ISE Design Mediator", page_icon="🏗️")
st.title("🏗️ Autonomous ISE Design Mediator")

with st.sidebar:
    api_key = st.text_input("Enter Gemini API Key", type="password")
    st.info("Formula: 25% Safety (70% Floor) + Weighted ISE Metrics")

# --- 2. CORE LOGIC ---
def extract_text_from_pdf(uploaded_file):
    # Read the file from the Streamlit uploader
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def get_ise_scores(text, model):
    prompt = f"""
    Analyze this engineering design. Return ONLY a JSON object. 
    Metrics (0-100): s_val (Safety), r_val (Reliability), e_val (Economy), 
    m_val (Manufacturability), v_val (Environment), h_val (Human Factors), l_val (Lifecycle).
    Design Text: {text[:8000]}
    """
    response = model.generate_content(prompt)
    clean_json = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_json)

def calculate_weighted_score(scores):
    # THE PERFECTED FORMULA: Score = C(safety) * Sum(wi * xi)
    weights = {"s": 0.25, "r": 0.20, "e": 0.15, "m": 0.10, "v": 0.10, "h": 0.10, "l": 0.10}
    
    # Kill Switch Logic
    if scores['s_val'] < 70:
        return 0, "REJECTED (CRITICAL SAFETY FAILURE)"
    
    total = sum(scores[f"{k}_val"] * w for k, w in weights.items())
    
    if total >= 85: status = "OPTIMAL"
    elif total >= 75: status = "MARGINAL"
    else: status = "REJECTED"
    return round(total, 2), status

# --- 3. UI LOOP ---
uploaded_file = st.file_uploader("Upload Design PDF", type="pdf")

if uploaded_file and api_key:
    genai.configure(api_key=api_key)
        if uploaded_file and api_key:
    genai.configure(api_key=api_key)
    
    # --- START DEBUG BLOCK ---
    # This will print to your Streamlit "Manage App" logs
    st.write("### Checking Available Models...") # This shows it on the website
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            st.write(f"Found: {m.name}") # Use st.write to see it on the screen!
    # --- END DEBUG BLOCK ---

    model = genai.GenerativeModel('gemini-1.5-flash')
    if st.button("Run Audit"):
        with st.spinner("Executing ISE Weighted Utility Analysis..."):
            # A. Extract
            raw_text = extract_text_from_pdf(uploaded_file)
            # B. Score
            scores = get_ise_scores(raw_text, model)
            # C. Math
            final_score, status = calculate_weighted_score(scores)
            
            # D. Display Results
            st.divider()
            st.metric("Final Design Score", f"{final_score}/100", delta=status)
            st.json(scores)
            
            # E. Final Memo
            persona = "Brutal Auditor" if "REJECTED" in status else "Collaborative Architect"
            memo_prompt = f"Persona: {persona}. Score: {final_score}. Status: {status}. Scores: {scores}. Write the audit memo."
            st.markdown("### 📝 Final Audit Memo")
            st.write(model.generate_content(memo_prompt).text)
