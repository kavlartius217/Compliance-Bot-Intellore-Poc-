__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import streamlit as st
import os
from datetime import datetime
import pandas as pd # For potential future use

# --- Dependency Imports ---
try:
    from langchain_groq import ChatGroq
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.schema import AIMessage, HumanMessage, SystemMessage
    from crewai import Agent, Task, Process, Crew
    from crewai_tools import SerperDevTool
    # from langchain_openai import ChatOpenAI # Uncomment if using OpenAI for CrewAI
except ImportError as e:
    st.error(f"""
        **Error loading libraries.** Please install required packages:
        ```bash
        pip install streamlit langchain_community langchain_google_genai langchain_openai langchain_groq crewai crewai_tools 'crewai[tools]' pandas
        ```
        **Details:** {e}
        """)
    st.stop()

# --- Constants ---
# Exactly as in the original script
COMPLIANCE_QUESTIONS = [
    "1. What is the type of your company? (Private / Public / Listed / Unlisted / Government / OPC / Section 8 / Dormant / Small)",
    "2. Is your company listed on a stock exchange? (Yes / No)",
    "3. Is your company a Small Company under the Companies Act? (Yes / No / Not Sure)",
    "4. Is your company a One Person Company (OPC)? (Yes / No)",
    "5. Is your company a Section 8 (Not-for-profit) Company? (Yes / No)",
    "6. Is your company a Holding or Subsidiary of another company? (Yes / No)",
    "7. What is your company’s Paid-up Share Capital? (in ₹ Crores)",
    "8. What is your company’s Turnover? (in ₹ Crores)",
    "9. What is your company’s Net Profit (Profit Before Tax)? (in ₹ Crores)",
    "10. What is the total amount of your borrowings from banks or public financial institutions? (in ₹ Crores)",
    "11. Do you have any public deposits outstanding? (Yes / No)",
    "12. Are there any debentures issued and outstanding? (Yes / No)",
    "13. How many shareholders / debenture holders / other security holders does your company have?",
    "14. Do you already maintain e-form records electronically under section 120? (Yes / No)",
    "15. Does your company already file financials in XBRL format? (Yes / No / Not Sure)",
    "16. What is the total number of employees in your company?"
]
REPORT_FILENAME = "compliance_report.md" # CrewAI will generate this

# --- Page Config ---
st.set_page_config(page_title="Compliance Bot Mark II", layout="wide", initial_sidebar_state="collapsed")
st.title("🤖 Compliance Bot Mark II")
st.markdown("Answer the questions sequentially to generate a compliance report based on the Companies Act, 2013.")

# --- API Key Setup ---
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    serper_api_key = st.secrets["SERPER_API_KEY"]
    # openai_api_key = st.secrets.get("OPENAI_API_KEY") # Optional

    os.environ['GROQ_API_KEY'] = groq_api_key
    os.environ['SERPER_API_KEY'] = serper_api_key
    # if openai_api_key:
    #     os.environ['OPENAI_API_KEY'] = openai_api_key

except KeyError as e:
    st.error(f"🛑 **Missing API Key:** '{e}' not found in st.secrets.")
    st.info("Please add the required API keys to your `.streamlit/secrets.toml` file.")
    st.stop()
except Exception as e:
    st.error(f"An unexpected error occurred during API key setup: {e}")
    st.stop()

# --- LLM and Tool Initialization ---
# Use @st.cache_resource to prevent re-initialization on every interaction
@st.cache_resource
def get_qna_chain():
    try:
        # Original Q&A Bot LLM and Prompt
        llm_gemma = ChatGroq(model='gemma2-9b-it', temperature=0)
        prompt_1 = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are an Interviewer"),
            SystemMessage(content="You have a set of questions: {compliance_questions}. Ask them sequentially, one at a time."),
            SystemMessage(content="Only ask the next unanswered question from {compliance_questions}."),
            SystemMessage(content="Do not repeat any question already present in chat history."),
            SystemMessage(content="Ask only the question itself, without any additional text."),
            SystemMessage(content="Never answer the questions yourself"),
            SystemMessage(content="After questions are over say Thank You"),
            MessagesPlaceholder(variable_name="chat_history"), # History comes first now
            HumanMessage(content="{answer}") # User answer is the last input
        ])
        chain = prompt_1 | llm_gemma
        return chain
    except Exception as e:
        st.error(f"Failed to initialize Q&A Chain. Check Groq API key/model. Error: {e}")
        st.stop()

@st.cache_resource
def get_crewai_tools():
    try:
        search_tool = SerperDevTool()
        # Explicitly define CrewAI LLM if needed (Optional)
        # crew_llm = ChatGroq(model='mixtral-8x7b-32768', temperature=0.2)
        # crew_llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        return search_tool #, crew_llm
    except Exception as e:
        st.error(f"Failed to initialize CrewAI Tools. Check Serper API key. Error: {e}")
        st.stop()

qna_chain = get_qna_chain()
search_tool = get_crewai_tools() #, crew_llm = get_crewai_tools()

# --- CrewAI Agent and Task Definition (Exact copy from original - unchanged) ---
def create_compliance_agent(tool): # , llm_instance=None):
    return Agent(
        role="Regulatory Compliance Analyst",
        goal="To analyze company details and generate a comprehensive markdown report of applicable compliance obligations under the Companies Act, 2013.",
        backstory=(
            "You are a top-tier regulatory compliance analyst specializing in Indian corporate law. "
            "You are highly skilled at interpreting company-specific information to determine which sections of the Companies Act, 2013 apply. "
            "You always rely on official government sources and use the Ministry of Corporate Affairs website (https://www.mca.gov.in) as your only source of truth. "
            "You use search tools to find relevant thresholds, forms, and deadlines, and present your findings in a clear, tabular markdown report "
            "suitable for audit or legal review."
        ),
        tools=[tool],
        memory=True,
        verbose=False,
        allow_delegation=False
        # llm=llm_instance
    )

def create_compliance_task(agent, company_data, report_date):
    return Task(
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
        ),
        agent=agent,
        context={"data": company_data, "date": report_date}, # Pass context here
        output_file=REPORT_FILENAME
    )

# --- Streamlit Session State Management ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [] # Stores Langchain message objects
if "qa_finished" not in st.session_state:
    st.session_state.qa_finished = False
if "analysis_triggered" not in st.session_state:
    st.session_state.analysis_triggered = False
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "report_content" not in st.session_state:
    st.session_state.report_content = None
if "crew_result_raw" not in st.session_state:
    st.session_state.crew_result_raw = None


# --- Helper function to reset ---
def reset_app():
    st.session_state.chat_history = []
    st.session_state.qa_finished = False
    st.session_state.analysis_triggered = False
    st.session_state.analysis_done = False
    st.session_state.report_content = None
    st.session_state.crew_result_raw = None
    if os.path.exists(REPORT_FILENAME):
        try: os.remove(REPORT_FILENAME)
        except OSError as e: st.warning(f"Could not delete report file: {e}")
    st.rerun()

# --- Function to get next bot question using the chain (revised) ---
def get_bot_response(user_answer):
    """Invokes the LangChain chain to get the next response (question or 'Thank You')."""
    if not st.session_state.qa_finished:
        try:
            # Prepare history: Ensure it's a list of BaseMessage objects
            history_for_chain = [msg for msg in st.session_state.chat_history if isinstance(msg, (AIMessage, HumanMessage, SystemMessage))]

            response = qna_chain.invoke({
                "answer": user_answer,
                "compliance_questions": COMPLIANCE_QUESTIONS,
                "chat_history": history_for_chain # Pass the prepared history
            })
            return response.content
        except Exception as e:
            st.error(f"Error invoking Q&A chain: {e}")
            st.exception(e) # Show traceback for debugging
            return None
    return None

# --- Render Chat History ---
# This loop runs on every interaction and displays the current history
for i, msg in enumerate(st.session_state.chat_history):
    if isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)
    elif isinstance(msg, HumanMessage):
        # Don't display the initial dummy "Start" message
        if msg.content != "Start":
            with st.chat_message("user"):
                st.markdown(msg.content)

# --- Main App Logic ---

# Phase 1: Q&A Interaction (Corrected Logic)
if not st.session_state.qa_finished and not st.session_state.analysis_done:

    # Initialize Q&A if history is empty
    if not st.session_state.chat_history:
        with st.spinner("Initializing conversation..."):
            # Send a dummy "Start" message to get the first question
            initial_human_message = HumanMessage(content="Start")
            st.session_state.chat_history.append(initial_human_message) # Add to history but don't display
            first_question = get_bot_response("Start")
            if first_question:
                st.session_state.chat_history.append(AIMessage(content=first_question))
            else:
                st.error("Failed to get the first question.")
                # Stop execution or handle error appropriately
        st.rerun() # Rerun to display the first question rendered by the history loop

    # Q&A is ongoing, expect user input
    else:
        user_input = st.chat_input("Your answer...")

        if user_input:
            # 1. Append user's actual response to history
            st.session_state.chat_history.append(HumanMessage(content=user_input))

            # 2. Get the bot's next response (question or "Thank You")
            with st.spinner("Thinking..."):
                bot_response_content = get_bot_response(user_input)

            if bot_response_content:
                # 3. Append bot's response to history
                st.session_state.chat_history.append(AIMessage(content=bot_response_content))

                # 4. Check if Q&A is finished
                if bot_response_content.strip() == "Thank You":
                    st.session_state.qa_finished = True # Mark Q&A as done
            else:
                # Handle error if chain invocation failed during the conversation
                st.warning("Could not get the next response from the bot.")

            # 5. Rerun to display the new user message and the bot's response
            st.rerun()


# Phase 2: Trigger Analysis after Q&A
elif st.session_state.qa_finished and not st.session_state.analysis_triggered and not st.session_state.analysis_done:
    st.success("✅ Q&A Complete!")
    st.info("Ready to analyze compliance based on your answers.")
    if st.button("🚀 Analyze Compliance", type="primary"):
        st.session_state.analysis_triggered = True
        st.rerun()

# Phase 3: Run Analysis (Unchanged from previous correct version)
elif st.session_state.analysis_triggered and not st.session_state.analysis_done:
     with st.spinner("🕵️‍♀️ Analyzing compliance requirements... This may take a few minutes..."):
            try:
                # 1. Format User Details for CrewAI
                details_list = []
                question = ""
                # Iterate through history to pair questions and answers
                for msg in st.session_state.chat_history:
                     if isinstance(msg, AIMessage) and msg.content != "Thank You":
                         question = msg.content # Store the question
                     elif isinstance(msg, HumanMessage) and question and msg.content != "Start":
                         # Pair the stored question with this answer
                         details_list.append(f"- {question.split(' (')[0]}: {msg.content}")
                         question = "" # Reset question after pairing
                formatted_details = "\n".join(details_list)

                current_date_str = datetime.now().strftime("%d-%m-%Y")

                # 2. Create Agent and Task
                compliance_agent = create_compliance_agent(search_tool) #, crew_llm)
                compliance_task = create_compliance_task(compliance_agent, formatted_details, current_date_str)

                # 3. Create and Kickoff Crew
                compliance_crew = Crew(
                    agents=[compliance_agent],
                    tasks=[compliance_task],
                    process=Process.sequential,
                )

                # Delete old report file before running
                if os.path.exists(REPORT_FILENAME):
                     try: os.remove(REPORT_FILENAME)
                     except OSError as e: st.warning(f"Could not delete previous report file '{REPORT_FILENAME}': {e}")

                # Run the Crew
                crew_result = compliance_crew.kickoff()
                st.session_state.crew_result_raw = crew_result

                # 4. Read the generated report
                if os.path.exists(REPORT_FILENAME):
                    with open(REPORT_FILENAME, 'r', encoding='utf-8') as f:
                        st.session_state.report_content = f.read()
                    st.session_state.analysis_done = True
                else:
                    st.error(f"CrewAI finished, but the output file '{REPORT_FILENAME}' was not found.")
                    st.text("Raw Crew Output:")
                    st.text(crew_result)
                    st.session_state.analysis_done = False # Indicate failure


                # 5. Rerun to display results or error
                st.rerun()

            except Exception as e:
                st.error(f"An error occurred during compliance analysis: {e}")
                st.exception(e)
                st.session_state.analysis_triggered = False # Allow retry

# Phase 4: Display Report (Unchanged from previous correct version)
elif st.session_state.analysis_done:
    st.success("✅ Compliance analysis complete!")

    if st.session_state.report_content:
        st.markdown("---")
        st.subheader("Generated Compliance Report")
        st.markdown(st.session_state.report_content, unsafe_allow_html=True)

        st.download_button(
            label="Download Report (.md)",
            data=st.session_state.report_content,
            file_name=REPORT_FILENAME,
            mime="text/markdown",
        )
    else:
         st.error("Analysis was marked as complete, but the report content could not be loaded.")
         st.text("Raw Crew Output (if available):")
         st.text(st.session_state.crew_result_raw)

    if st.button("🔄 Start New Analysis"):
        reset_app()


# Footer (Unchanged)
st.markdown("---")
st.caption("Compliance Bot MKII - Powered by LangChain, Groq, CrewAI, and Streamlit.")
