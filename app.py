__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
import os
import pandas as pd
from datetime import datetime
from crewai import Agent, Task, Process, Crew
from crewai_tools import SerperDevTool
from crewai import LLM

# Page config
st.set_page_config(
    page_title="Compliance Bot MARK III",
    page_icon="📋",
    layout="wide"
)

# Title and description
st.title("🤖 Compliance Bot MARK III")
st.markdown("""
This application analyzes your company details and generates a comprehensive report 
of applicable compliance obligations under the Companies Act, 2013.
""")

# Sidebar for API keys
with st.sidebar:
    st.header("API Configuration")
    openai_key = st.text_input("OpenAI API Key", type="password", 
                             value=os.environ.get("OPENAI_API_KEY", ""))
    serper_key = st.text_input("Serper API Key", type="password", 
                             value=os.environ.get("SERPER_API_KEY", ""))
    groq_key = st.text_input("GROQ API Key", type="password", 
                           value=os.environ.get("GROQ_API_KEY", ""))
    
    if st.button("Save API Keys"):
        os.environ["OPENAI_API_KEY"] = openai_key
        os.environ["SERPER_API_KEY"] = serper_key
        os.environ["GROQ_API_KEY"] = groq_key
        st.success("API keys saved!")

# Define the compliance questions
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

# Function to run compliance analysis
def run_compliance_analysis(compliance_answers):
    # Initialize tools
    search_tool = SerperDevTool()
    
    # Initialize LLM
    llm_deepseek = LLM(model="groq/deepseek-r1-distill-llama-70b", temperature=0)
    
    # Create compliance agent
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
    
    # Create compliance lookup task
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
        agent=compliance_agent
    )
    
    # Create and run crew
    crew = Crew(
        agents=[compliance_agent],
        tasks=[compliance_lookup_task],
        process=Process.sequential
    )
    
    current_date = datetime.now().strftime("%d-%m-%Y")
    result = crew.kickoff({"data": compliance_answers, "date": current_date})
    return result

# Main form
with st.form("compliance_form"):
    st.subheader("Company Information")
    
    # Create columns for better layout
    col1, col2 = st.columns(2)
    
    # Create a dict to store answers
    compliance_answers = []
    
    # Use appropriate input fields for each question type
    for i, question in enumerate(compliance_questions):
        current_col = col1 if i % 2 == 0 else col2
        
        with current_col:
            if "Yes / No" in question or "Yes / No / Not Sure" in question:
                options = ["Yes", "No"]
                if "Not Sure" in question:
                    options.append("Not Sure")
                answer = st.selectbox(question, options=[""] + options)
            elif "in ₹ Crores" in question:
                answer = st.number_input(question, min_value=0.0, format="%.2f")
            elif any(company_type in question for company_type in ["Private", "Public", "Listed", "Unlisted"]):
                options = ["Private", "Public", "Listed", "Unlisted", "Government", "OPC", "Section 8", "Dormant", "Small"]
                answer = st.selectbox(question, options=[""] + options)
            else:
                answer = st.text_input(question)
            
            if answer:
                compliance_answers.append({"question": question, "answer": str(answer)})
    
    submitted = st.form_submit_button("Generate Compliance Report", type="primary")

# Process the form if submitted
if 'submitted' in locals() and submitted:
    if len(compliance_answers) < len(compliance_questions):
        missing = len(compliance_questions) - len(compliance_answers)
        st.warning(f"Please fill in all {missing} remaining questions to generate a complete report.")
    else:
        with st.spinner("Analyzing compliance requirements... This may take a few minutes."):
            try:
                result = run_compliance_analysis(compliance_answers)
                
                # Display the result
                st.success("Compliance analysis completed!")
                st.markdown("## Compliance Report")
                st.markdown(result)
                
                # Add download button
                st.download_button(
                    label="Download Report as Markdown",
                    data=result,
                    file_name="compliance_report.md",
                    mime="text/markdown"
                )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Please ensure all API keys are correctly set in the sidebar.")

# Footer
st.markdown("---")
st.markdown("Compliance Bot MARK III © 2025")
