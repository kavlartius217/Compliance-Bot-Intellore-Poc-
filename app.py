__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import streamlit as st
import os
import pandas as pd
from datetime import datetime
import subprocess
import sys

# Set page configuration
st.set_page_config(
    page_title="Compliance Bot MARK III",
    page_icon="📋",
    layout="wide",
)

# Add CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2563EB;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #EFF6FF;
        border-left: 5px solid #2563EB;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

# Header
st.markdown("<h1 class='main-header'>Compliance Bot MARK III</h1>", unsafe_allow_html=True)

# Sidebar for API keys
with st.sidebar:
    st.header("API Configuration")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    serper_api_key = st.text_input("Serper API Key", type="password")
    groq_api_key = st.text_input("Groq API Key", type="password")
    
    if st.button("Save API Keys"):
        if openai_api_key:
            os.environ['OPENAI_API_KEY'] = openai_api_key
            st.success("OpenAI API Key saved!")
        if serper_api_key:
            os.environ['SERPER_API_KEY'] = serper_api_key
            st.success("Serper API Key saved!")
        if groq_api_key:
            os.environ['GROQ_API_KEY'] = groq_api_key
            st.success("Groq API Key saved!")

# Installation section
st.markdown("<h2 class='sub-header'>Installation</h2>", unsafe_allow_html=True)

if 'installation_done' not in st.session_state:
    st.session_state.installation_done = False

if not st.session_state.installation_done:
    with st.expander("Install Required Packages", expanded=True):
        st.info("The following packages will be installed:")
        st.code("pip install crewai crewai_tools 'crewai[tools]'")
        
        if st.button("Install Packages"):
            # Using subprocess to avoid the distutils error
            try:
                st.write("Installing packages...")
                pip_command = [sys.executable, "-m", "pip", "install", "crewai", "crewai_tools", "crewai[tools]"]
                result = subprocess.run(pip_command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success("Packages installed successfully!")
                    st.session_state.installation_done = True
                else:
                    st.error(f"Installation failed: {result.stderr}")
            except Exception as e:
                st.error(f"An error occurred: {e}")
else:
    st.success("Required packages are installed!")

# Questions and Answers section
st.markdown("<h2 class='sub-header'>Company Information Questionnaire</h2>", unsafe_allow_html=True)

compliance_questions = [
    "1. What is the type of your company? (Private / Public / Listed / Unlisted / Government / OPC / Section 8 / Dormant / Small)",
    "2. Is your company listed on a stock exchange? (Yes / No)",
    "3. Is your company a Small Company under the Companies Act? (Yes / No / Not Sure)",
    "4. Is your company a One Person Company (OPC)? (Yes / No)",
    "5. Is your company a Section 8 (Not-for-profit) Company? (Yes / No)",
    "6. Is your company a Holding or Subsidiary of another company? (Yes / No)",
    "7. What is your company's Paid-up Share Capital? (in ₹ Crores)",
    "8. What is your company's Turnover? (in ₹ Crores)",
    "9. What is your company's Net Profit (Profit Before Tax)? (in ₹ Crores)",
    "10. What is the total amount of your borrowings from banks or public financial institutions? (in ₹ Crores)",
    "11. Do you have any public deposits outstanding? (Yes / No)",
    "12. Are there any debentures issued and outstanding? (Yes / No)",
    "13. How many shareholders / debenture holders / other security holders does your company have?",
    "14. Do you already maintain e-form records electronically under section 120? (Yes / No)",
    "15. Does your company already file financials in XBRL format? (Yes / No / Not Sure)",
    "16. What is the total number of employees in your company?"
]

if 'compliance_answers' not in st.session_state:
    st.session_state.compliance_answers = [{"question": q, "answer": ""} for q in compliance_questions]

with st.form(key="compliance_form"):
    st.markdown("<div class='info-box'>Please answer all questions to generate your compliance report.</div>", unsafe_allow_html=True)
    
    for i, q in enumerate(compliance_questions):
        if "Yes / No" in q or "Yes / No / Not Sure" in q:
            options = [option.strip() for option in q[q.find("(")+1:q.find(")")].split("/")]
            options.insert(0, "")  # Add empty option
            st.session_state.compliance_answers[i]["answer"] = st.selectbox(
                q, 
                options=options,
                key=f"question_{i}"
            )
        elif "in ₹ Crores" in q:
            st.session_state.compliance_answers[i]["answer"] = st.number_input(
                q,
                min_value=0.0,
                format="%.2f",
                key=f"question_{i}"
            )
        else:
            st.session_state.compliance_answers[i]["answer"] = st.text_input(
                q,
                key=f"question_{i}"
            )
    
    date_input = st.date_input("Report reference date", datetime.now())
    submit_button = st.form_submit_button("Generate Compliance Report")

# Generate Report Section
if submit_button:
    # Check if all questions are answered
    unanswered = [q["question"] for q in st.session_state.compliance_answers if not q["answer"]]
    
    if unanswered:
        st.error("Please answer all questions before generating the report.")
        for q in unanswered:
            st.warning(f"Missing answer: {q}")
    else:
        st.markdown("<h2 class='sub-header'>Generating Compliance Report</h2>", unsafe_allow_html=True)
        with st.spinner("Analyzing your company information and generating compliance report..."):
            try:
                # Import required modules
                from crewai import Agent, Task, Process, Crew, LLM
                from crewai_tools import SerperDevTool
                
                # Setup tools
                search_tool = SerperDevTool()
                
                # Setup LLM
                llm_deepseek = LLM(
                    model="groq/deepseek-r1-distill-llama-70b",
                    api_key=groq_api_key
                )
                
                # Create agent
                compliance_agent = Agent(
                    role="Regulatory Compliance Analyst",
                    goal="To analyze company details and generate a comprehensive markdown report of applicable compliance obligations under the Companies Act, 2013.",
                    backstory=(
                        "You are a top-tier regulatory compliance analyst specializing in Indian corporate law. "
                        "You are highly skilled at interpreting company-specific information to determine which sections of the Companies Act, 2013 apply. "
                        "You always rely on official government sources and use the Ministry of Corporate Affairs website (https://www.mca.gov.in) as your only source of truth. "
                        "You use search tools to find relevant thresholds, forms, and deadlines, and present your findings in a clear, tabular markdown report "
                        "suitable for audit or legal review."
                    ),
                    llm=llm_deepseek,
                    tools=[search_tool],
                    memory=True,
                    verbose=True
                )
                
                # Create task
                compliance_lookup_task = Task(
                    description=(
                        "You are provided with structured compliance intake data from a company (see: {data}) "
                        "and the current reference date (see: {date}). "
                        "Your task is to determine which legal compliance obligations apply to the company under the Companies Act, 2013. "
                        "You must use only official sources from the Ministry of Corporate Affairs (https://www.mca.gov.in) to validate all thresholds, conditions, forms, and deadlines."
                    ),
                    expected_output=(
                        "Generate a well-structured **Markdown (.md)** table that includes a full compliance summary for the company. "
                        "You must not just list applicable compliances — also show inapplicable, missing, or error-prone cases to help the user correct them.\n\n"

                        "**The markdown table must contain the following columns:**\n"
                        "- Compliance Area (e.g., CSR Committee, Secretarial Audit)\n"
                        "- Section (e.g., 135(1), 204(1))\n"
                        "- Form (if applicable, e.g., MR-3, MGT-8)\n"
                        "- Applicable (✅/❌)\n"
                        "- Trigger or Reason (e.g., 'Net Profit > ₹5 Cr', or 'Does not meet XBRL condition')\n"
                        "- Legal Deadline (e.g., 'within 180 days of financial year end')\n"
                        "- Due Date (calculated from {date})\n"
                        "- Status/Error (e.g., 'Compliant', 'Missing input: Paid-up Capital', 'Exempted due to Small Company')\n"
                        "- Source (URL from mca.gov.in)\n\n"

                        "**You must handle the following cases:**\n"
                        "- ✅ Clearly applicable compliances with due dates.\n"
                        "- ❌ Inapplicable ones with reasons why they do not apply.\n"
                        "- ⚠️ Missing or invalid inputs (e.g., blank fields, ambiguous entries).\n"
                        "- ❗ Any edge cases, exemptions (e.g., OPC, Section 8 Company), or potential legal risks.\n\n"

                        "🛑 **Important Rules:**\n"
                        "- Use only content found via 'site:mca.gov.in' search queries.\n"
                        "- The table must be a clean, valid markdown table viewable on GitHub.\n"
                        "- For each entry, provide a real MCA.gov.in URL as the source.\n"
                        "- Do not guess thresholds — look them up.\n"
                        "- Ensure all legal deadlines are calculated from the current date ({date}).\n"
                        "- Do not omit entries — even inapplicable ones must be recorded."
                        "- The report generated should be beautifully presented."
                    ),
                    agent=compliance_agent,
                    output_file="compliance.md"
                )
                
                # Create and run crew
                crew = Crew(
                    agents=[compliance_agent],
                    tasks=[compliance_lookup_task],
                    process=Process.sequential
                )
                
                formatted_date = date_input.strftime("%d-%m-%Y")
                result = crew.kickoff({"data": st.session_state.compliance_answers, "date": formatted_date})
                
                # Display the result
                st.markdown("<h2 class='sub-header'>Compliance Report</h2>", unsafe_allow_html=True)
                st.markdown(result)
                
                # Download option
                st.download_button(
                    label="Download Compliance Report",
                    data=result,
                    file_name=f"compliance_report_{formatted_date}.md",
                    mime="text/markdown"
                )
                
            except Exception as e:
                st.error(f"An error occurred during report generation: {str(e)}")
                st.info("Please ensure all API keys are correctly set in the sidebar.")

# Add footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: gray; font-size: 0.8rem;">
        Compliance Bot MARK III © 2025 | Powered by CrewAI and Groq LLM
    </div>
    """, 
    unsafe_allow_html=True
)
