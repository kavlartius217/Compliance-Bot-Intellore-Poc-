__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import streamlit as st
import os
from datetime import date
import pandas as pd

# Title and description
st.set_page_config(page_title="Compliance Bot MARK III", layout="wide")
st.title("Compliance Bot MARK III")
st.markdown("### Indian Companies Act Compliance Assistant")

# Handle API secrets from st.secrets
with st.sidebar:
    st.header("API Configuration")
    
    # Check for existing secrets and set environment variables
    api_keys_configured = True
    
    # OpenAI API Key
    if "openai_api_key" in st.secrets:
        openai_api_key = st.secrets["openai_api_key"]
        os.environ['OPENAI_API_KEY'] = openai_api_key
        st.success("✅ OpenAI API key configured from secrets")
    else:
        openai_api_key = st.text_input("OpenAI API Key", type="password", help="Enter your OpenAI API key")
        api_keys_configured = False
    
    # Serper API Key
    if "serper_api_key" in st.secrets:
        serper_api_key = st.secrets["serper_api_key"]
        os.environ['SERPER_API_KEY'] = serper_api_key
        st.success("✅ Serper API key configured from secrets")
    else:
        serper_api_key = st.text_input("Serper API Key", type="password", help="Enter your Serper API key")
        api_keys_configured = False
    
    # Groq API Key
    if "groq_api_key" in st.secrets:
        groq_api_key = st.secrets["groq_api_key"]
        st.success("✅ Groq API key configured from secrets")
    else:
        groq_api_key = st.text_input("Groq API Key", type="password", help="Enter your Groq API key")
        api_keys_configured = False
    
    # Only show the save button if any keys need to be manually entered
    if not api_keys_configured:
        if st.button("Save API Keys"):
            if openai_api_key:
                os.environ['OPENAI_API_KEY'] = openai_api_key
            if serper_api_key:
                os.environ['SERPER_API_KEY'] = serper_api_key
            st.success("API keys saved for this session")
            st.info("For persistent storage, add these keys to your .streamlit/secrets.toml file")
    
    st.markdown("""
    ### Configure API Keys in secrets.toml
    ```toml
    # .streamlit/secrets.toml
    openai_api_key = "your-openai-api-key"
    serper_api_key = "your-serper-api-key"
    groq_api_key = "your-groq-api-key"
    ```
    """)

# Define compliance questions
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

# Main content area
st.header("Company Information")
st.write("Please provide the following information about your company to generate a compliance report.")

# Initialize session state for storing answers
if 'compliance_answers' not in st.session_state:
    st.session_state.compliance_answers = [{"question": q, "answer": ""} for q in compliance_questions]
    st.session_state.report_generated = False
    st.session_state.compliance_report = ""

# Create a form for the questions
with st.form("compliance_form"):
    for i, qa in enumerate(st.session_state.compliance_answers):
        # Extract question number and text
        q_parts = qa["question"].split(". ", 1)
        if len(q_parts) > 1:
            q_num, q_text = q_parts
        else:
            q_num, q_text = "", qa["question"]
        
        # Create different input types based on question
        if "Yes / No" in q_text:
            st.session_state.compliance_answers[i]["answer"] = st.radio(
                qa["question"],
                options=["Yes", "No", "Not applicable"],
                index=None,
                key=f"question_{i}"
            )
        elif "Crores" in q_text:
            st.session_state.compliance_answers[i]["answer"] = st.number_input(
                qa["question"],
                min_value=0.0,
                format="%.2f",
                key=f"question_{i}"
            )
        elif i == 0:  # Company type question
            st.session_state.compliance_answers[i]["answer"] = st.selectbox(
                qa["question"],
                options=["Private", "Public", "Listed", "Unlisted", "Government", "OPC", "Section 8", "Dormant", "Small"],
                index=None,
                key=f"question_{i}"
            )
        elif "Yes / No / Not Sure" in q_text:
            st.session_state.compliance_answers[i]["answer"] = st.radio(
                qa["question"],
                options=["Yes", "No", "Not Sure"],
                index=None,
                key=f"question_{i}"
            )
        else:
            st.session_state.compliance_answers[i]["answer"] = st.text_input(
                qa["question"],
                key=f"question_{i}"
            )
    
    # Date selection for compliance calculation
    report_date = st.date_input("Select date for compliance calculation", date.today())
    
    # Submit button
    submit_button = st.form_submit_button("Generate Compliance Report")

# Process form submission
if submit_button:
    # Check if API keys are available (either from secrets or manually entered)
    api_keys_available = True
    missing_keys = []
    
    if not os.environ.get('OPENAI_API_KEY') and "openai_api_key" not in st.secrets:
        api_keys_available = False
        missing_keys.append("OpenAI API Key")
    
    if not os.environ.get('SERPER_API_KEY') and "serper_api_key" not in st.secrets:
        api_keys_available = False
        missing_keys.append("Serper API Key")
    
    if "groq_api_key" not in st.secrets and not groq_api_key:
        api_keys_available = False
        missing_keys.append("Groq API Key")
    
    if not api_keys_available:
        st.error(f"Missing API keys: {', '.join(missing_keys)}. Please configure them in the sidebar or in your secrets.toml file.")
    else:
        with st.spinner("Generating compliance report... This might take a few minutes."):
            try:
                # Import required libraries here to avoid loading them until needed
                from crewai_tools import SerperDevTool
                from crewai import Agent, Task, Process, Crew, LLM
                
                # Initialize tools
                search_tool = SerperDevTool()
                
                # Initialize LLM with API key from secrets or manually entered
                llm_deepseek = LLM(
                    model="groq/deepseek-r1-distill-llama-70b",
                    api_key=st.secrets.get("groq_api_key", groq_api_key)
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
                    agent=compliance_agent
                )
                
                # Create crew
                crew = Crew(
                    agents=[compliance_agent],
                    tasks=[compliance_lookup_task],
                    process=Process.sequential
                )
                
                # Convert date to string format
                date_str = report_date.strftime("%d-%m-%Y")
                
                # Run the crew
                result = crew.kickoff({"data": st.session_state.compliance_answers, "date": date_str})
                
                # Store the result
                st.session_state.compliance_report = result
                st.session_state.report_generated = True
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

# Display the compliance report if it has been generated
if st.session_state.report_generated and st.session_state.compliance_report:
    st.header("Compliance Report")
    st.markdown(st.session_state.compliance_report)
    
    # Add download button for the report
    report_filename = f"compliance_report_{date.today().strftime('%Y%m%d')}.md"
    st.download_button(
        label="Download Report",
        data=st.session_state.compliance_report,
        file_name=report_filename,
        mime="text/markdown"
    )

# Add footer
st.markdown("---")
st.markdown("Compliance Bot MARK III © 2025 | Built with Streamlit and CrewAI")
