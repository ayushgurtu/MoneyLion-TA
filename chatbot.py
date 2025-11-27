import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import os
from typing import Optional, Tuple, List, Dict, Any
import json
import io
from dotenv import load_dotenv
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv()

# Import agentic AI utilities
from scripts.utils import TransactionQueryAgent


# Database path
DB_PATH = "database/transactions.db"

# Page configuration
st.set_page_config(
    page_title="Transaction Query Assistant (Agentic AI)",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'agent_memory' not in st.session_state:
    st.session_state.agent_memory = []
if 'execution_log' not in st.session_state:
    st.session_state.execution_log = []
if 'llm_chat_history' not in st.session_state:
    st.session_state.llm_chat_history = InMemoryChatMessageHistory()


def get_db_connection():
    """Create and return a database connection."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Please ensure the database exists.")
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def get_table_schema() -> str:
    """Get the schema of the transactions table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(transactions)")
    columns = cursor.fetchall()
    conn.close()
    
    schema = "Table: transactions\n"
    schema += "Columns:\n"
    for col in columns:
        schema += f"  - {col[1]} ({col[2]})\n"
    
    # Add sample data for context
    conn = get_db_connection()
    sample = pd.read_sql_query("SELECT * FROM transactions LIMIT 3", conn)
    conn.close()
    
    schema += "\nSample data:\n"
    schema += sample.to_string()
    
    return schema


def get_unique_bank_ids() -> List[int]:
    """Get unique bank_id values from the database."""
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT DISTINCT bank_id FROM transactions ORDER BY bank_id", conn)
        conn.close()
        return sorted(df['bank_id'].tolist())
    except Exception as e:
        return []


def get_account_ids_by_bank_ids(bank_ids: List[int]) -> List[int]:
    """Get unique account_id values filtered by bank_ids."""
    if not bank_ids:
        return []
    try:
        conn = get_db_connection()
        bank_ids_str = ','.join(map(str, bank_ids))
        query = f"SELECT DISTINCT account_id FROM transactions WHERE bank_id IN ({bank_ids_str}) ORDER BY account_id"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return sorted(df['account_id'].tolist())
    except Exception as e:
        return []


def check_spelling(question: str, api_key: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Check spelling in the user's question using LLM and suggest corrections.
    
    Args:
        question: The user's input question
        api_key: Groq API key (optional, will use env var if not provided)
        
    Returns:
        Tuple of (corrected_question, list_of_suggestions)
        - corrected_question: Question with corrected spelling (original if no errors found)
        - list_of_suggestions: List of suggested corrections for misspelled words
    """
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        # If API key is not available, return original question
        return question, []
    
    try:
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a spelling and grammar checker. Analyze the user's question and identify spelling errors. Return a JSON response with corrected text and individual corrections."),
            ("human", """Check the spelling in the following question and provide corrections if needed.

            Original Question: {question}

            Instructions:
            - Check for spelling errors in the question
            - If there are NO spelling errors, return the original question unchanged
            - If there ARE spelling errors, provide the corrected question and list the corrections
            - Focus only on spelling, not grammar or meaning changes
            - Preserve the original structure and capitalization

            Return your response in the following JSON format:
            {{
                "has_errors": true/false,
                "corrected_question": "corrected version of the question",
                "corrections": [
                    {{"original": "misspeled", "corrected": "misspelled"}},
                    {{"original": "recieve", "corrected": "receive"}}
                ]
            }}

            If there are no spelling errors, set "has_errors" to false and return the original question in "corrected_question" with an empty "corrections" array.

            JSON Response:""")
        ])
        
        chain = prompt_template | llm
        response = chain.invoke({"question": question})
        
        # Parse JSON response
        try:
            result_text = response.content.strip()
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            elif result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()
            
            result = json.loads(result_text)
            
            corrected_question = result.get("corrected_question", question)
            corrections = result.get("corrections", [])
            
            # Format suggestions list
            suggestions = []
            if result.get("has_errors", False) and corrections:
                for correction in corrections:
                    original = correction.get("original", "")
                    corrected = correction.get("corrected", "")
                    if original and corrected:
                        suggestions.append(f"'{original}' → '{corrected}'")
            
            return corrected_question, suggestions
            
        except (json.JSONDecodeError, KeyError) as e:
            # If JSON parsing fails, return original question
            return question, []
            
    except Exception as e:
        # If LLM call fails, return original question
        return question, []


# ==================== MAIN APPLICATION ====================

def main():
    # Sidebar for configuration
    with st.sidebar:
        api_key = os.getenv("GROQ_API_KEY")
        
        st.header("🏦 Bank & Account Details")
        
        # Get unique bank IDs
        unique_bank_ids = get_unique_bank_ids()
        
        # Initialize session state for tracking bank IDs
        if 'prev_selected_bank_ids' not in st.session_state:
            st.session_state.prev_selected_bank_ids = []
        
        selected_bank_ids = st.multiselect(
            "Bank IDs *",
            options=unique_bank_ids,
            default=[],
            key="bank_ids_multiselect",
            help="Select your bank IDs"
        )
        
        # Clear account IDs if bank IDs changed
        bank_ids_changed = set(selected_bank_ids) != set(st.session_state.prev_selected_bank_ids)
        if bank_ids_changed:
            st.session_state.prev_selected_bank_ids = selected_bank_ids
            # Clear account IDs widget state when bank IDs change
            if 'account_ids_multiselect' in st.session_state:
                st.session_state.account_ids_multiselect = []
        
        # Account IDs selection
        selected_account_ids = []
        if selected_bank_ids:
            # Get account IDs filtered by selected bank IDs
            available_account_ids = get_account_ids_by_bank_ids(selected_bank_ids)
            
            if available_account_ids:
                # Filter out any invalid account IDs from session state (not in available list)
                if 'account_ids_multiselect' in st.session_state:
                    # Keep only valid account IDs that are in the available list
                    valid_selected = [acc_id for acc_id in st.session_state.account_ids_multiselect 
                                     if acc_id in available_account_ids]
                    st.session_state.account_ids_multiselect = valid_selected
                else:
                    # Initialize to empty list if not exists
                    st.session_state.account_ids_multiselect = []
                
                selected_account_ids = st.multiselect(
                    "Account IDs *",
                    options=available_account_ids,
                    key="account_ids_multiselect",
                    help="Select your account IDs from the selected banks"
                )
            else:
                st.info("ℹ️ No account IDs found for the selected bank IDs.")
                # Clear account IDs if none available
                if 'account_ids_multiselect' in st.session_state:
                    st.session_state.account_ids_multiselect = []
        else:
            # Clear account IDs if bank IDs are cleared
            if 'account_ids_multiselect' in st.session_state:
                st.session_state.account_ids_multiselect = []
        
        st.divider()

        st.header("📅 Date Configuration")
        
        selected_date = st.date_input(
            "Current date",
            value=datetime.now().date(),
            min_value=date(1900, 1, 1),
            max_value=datetime.now().date(),
            help="Select the current date for the transactions"
        )
    
    # Main content area - Chatbot Interface
    st.title("🤖 Transaction Query Assistant")
    st.markdown("Ask questions about your bank transactions.")
    
    # Container for chat messages
    chat_container = st.container()
    
    with chat_container:
        # Display chat messages
        for message in st.session_state.conversation_history:
            # User message
            with st.chat_message("user"):
                st.write(message["question"])
            
            # Assistant message
            with st.chat_message("assistant"):
                answer = message["answer"]
                
                # Check if the answer is CSV data
                if answer.startswith("CSV_DATA:"):
                    # Extract the intro text, preview CSV, and full CSV
                    parts = answer.split("CSV_PREVIEW:\n", 1)
                    intro_text = parts[0].replace("CSV_DATA:", "").strip()
                    
                    if len(parts) > 1:
                        csv_parts = parts[1].split("CSV_FULL:\n", 1)
                        csv_preview = csv_parts[0].strip() if len(csv_parts) > 0 else ""
                        csv_full = csv_parts[1].strip() if len(csv_parts) > 1 else csv_preview
                    else:
                        # Fallback if format is different
                        csv_preview = parts[1].strip() if len(parts) > 1 else ""
                        csv_full = csv_preview
                    
                    # Display intro text
                    st.markdown(intro_text)
                    
                    # Parse preview CSV to DataFrame for display (first 100 rows)
                    csv_df = pd.read_csv(io.StringIO(csv_preview)) if csv_preview else pd.DataFrame()
                    
                    # Display the data as a table
                    st.dataframe(csv_df, use_container_width=True)
                    
                    # Provide download button for FULL CSV (all rows)
                    csv_bytes = csv_full.encode('utf-8')
                    message_idx = st.session_state.conversation_history.index(message)
                    timestamp_str = message.get('timestamp', datetime.now().strftime('%Y%m%d_%H%M%S')).replace(' ', '_').replace(':', '-')
                    st.download_button(
                        label="📥 Download CSV (All Records)",
                        data=csv_bytes,
                        file_name=f"transactions_{timestamp_str}.csv",
                        mime="text/csv",
                        key=f"download_csv_history_{message_idx}"
                    )
                else:
                    st.write(answer)
                
                # Show additional details in expanders
                if message.get("sql") and message["sql"] != "Agent-generated (multi-step)":
                    with st.expander("🔍 View SQL Query"):
                        st.code(message["sql"], language="sql")
                
                # Show agent steps if available (always show for agentic mode)
                intermediate_steps = message.get("intermediate_steps", [])
                if intermediate_steps and len(intermediate_steps) > 0:
                    with st.expander("📋 View Agent Steps", expanded=False):
                        for i, step in enumerate(intermediate_steps, 1):
                            if isinstance(step, dict):
                                st.markdown(f"**Step {i}: {step.get('action', 'unknown')}**")
                                st.text(f"Thought: {step.get('thought', '')}")
                                st.text(f"Result: {step.get('result', '')[:300]}...")
                            else:
                                st.text(f"Step {i}: {str(step)[:200]}...")
                
                # Show execution log if available
                if st.session_state.execution_log:
                    with st.expander("🔍 View Agent Execution Log"):
                        # Show the most recent logs (last 10 entries)
                        for log_entry in st.session_state.execution_log[-10:]:
                            st.text(f"[{log_entry['step']}] {log_entry['output'][:200]}")
                
                # Show timestamp
                st.caption(f"• {message.get('timestamp', '')}")
    
    # Initialize flag to hide examples if not exists
    if "hide_examples" not in st.session_state:
        st.session_state.hide_examples = False
    
    # Check chat input FIRST to get prompt value early and hide examples before rendering them
    prompt = st.chat_input("Ask about your transactions...")
    
    # Check if example question was selected
    if "example_question" in st.session_state and st.session_state.example_question:
        prompt = st.session_state.example_question
        del st.session_state.example_question
        st.session_state.hide_examples = True
    
    # Hide examples immediately if user has entered a prompt
    if prompt:
        st.session_state.hide_examples = True
    
    # Example questions above chat input
    if not st.session_state.conversation_history and not st.session_state.hide_examples:
        st.markdown("### 💡 Example Questions")
        st.markdown("Click on any question below to get started:")
        
        example_questions = [
            "How much did I spend last week?",
            "What is the amount I have spent on Uber in the last 5 months?",
            "How much money did I receive from amazon last month?",
        ]
        
        # Display example questions in columns
        cols = st.columns(2)
        for idx, question in enumerate(example_questions):
            with cols[idx % 2]:
                if st.button(f"💬 {question}", key=f"example_{idx}", use_container_width=True):
                    st.session_state.example_question = question
                    st.session_state.hide_examples = True
                    st.rerun()
    
    if prompt:
        # Validate mandatory fields
        if not selected_bank_ids:
            with st.chat_message("assistant"):
                st.error("❌ Please select at least one Bank ID before submitting your question.")
            st.stop()
        
        if not selected_account_ids:
            with st.chat_message("assistant"):
                st.error("❌ Please select at least one Account ID before submitting your question.")
            st.stop()
        
        # Check spelling and correct internally
        if api_key:
            corrected_prompt, _ = check_spelling(prompt, api_key)
            # Use corrected prompt automatically if different from original
            if corrected_prompt != prompt:
                prompt = corrected_prompt 
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            with st.spinner("Processing your question..."):
                
                if not api_key:
                    message_placeholder.error("❌ GROQ_API_KEY Required. Please set it in your .env file.")
                else:
                    # Create execution log callback
                    def log_callback(log_entry: Dict):
                        st.session_state.execution_log.append(log_entry)
                    
                    agent = TransactionQueryAgent(
                        api_key=api_key,
                        bank_ids=selected_bank_ids,
                        account_ids=selected_account_ids,
                        current_date=selected_date.strftime('%Y-%m-%d'),
                        schema_getter=get_table_schema,
                        db_connection_getter=get_db_connection,
                        chat_history=st.session_state.llm_chat_history,
                        execution_log_callback=log_callback
                    )
                    
                    # Get context from conversation history
                    context = st.session_state.conversation_history[-5:] if st.session_state.conversation_history else []
                    
                    result = agent.process_question(prompt, context)
                    
                    if result["success"]:
                        answer = result["answer"]
                        
                        # Check if the answer is CSV data
                        if answer.startswith("CSV_DATA:"):
                            # Extract the intro text, preview CSV, and full CSV
                            parts = answer.split("CSV_PREVIEW:\n", 1)
                            intro_text = parts[0].replace("CSV_DATA:", "").strip()
                            
                            if len(parts) > 1:
                                csv_parts = parts[1].split("CSV_FULL:\n", 1)
                                csv_preview = csv_parts[0].strip() if len(csv_parts) > 0 else ""
                                csv_full = csv_parts[1].strip() if len(csv_parts) > 1 else csv_preview
                            else:
                                # Fallback if format is different
                                csv_preview = parts[1].strip() if len(parts) > 1 else ""
                                csv_full = csv_preview
                            
                            # Display intro text
                            message_placeholder.markdown(intro_text)
                            
                            # Parse preview CSV to DataFrame for display (first 100 rows)
                            csv_df = pd.read_csv(io.StringIO(csv_preview)) if csv_preview else pd.DataFrame()
                            
                            # Display the data as a table
                            st.dataframe(csv_df, use_container_width=True)
                            
                            # Provide download button for FULL CSV (all rows)
                            csv_bytes = csv_full.encode('utf-8')
                            st.download_button(
                                label="📥 Download CSV (All Records)",
                                data=csv_bytes,
                                file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                key=f"download_csv_{len(st.session_state.conversation_history)}"
                            )
                        else:
                            # Regular text answer - escape markdown and preserve formatting
                            message_placeholder.markdown(answer.replace("$", "\\$"))
                        
                        # Show additional details in expanders
                        if result.get("sql_used"):
                            with st.expander("🔍 View SQL Query"):
                                st.code(result["sql_used"], language="sql")
                        
                        # Show agent steps
                        intermediate_steps = result.get("intermediate_steps", [])
                        if intermediate_steps and len(intermediate_steps) > 0:
                            with st.expander("📋 View Agent Steps", expanded=False):
                                for i, step in enumerate(intermediate_steps, 1):
                                    if isinstance(step, dict):
                                        st.markdown(f"**Step {i}: {step.get('action', 'unknown')}**")
                                        st.text(f"Thought: {step.get('thought', '')}")
                                        st.text(f"Result: {step.get('result', '')[:300]}...")
                                    else:
                                        st.text(f"Step {i}: {str(step)[:200]}...")
                        
                        if st.session_state.execution_log:
                            with st.expander("🔍 View Agent Execution Log"):
                                for log_entry in st.session_state.execution_log[-10:]:
                                    st.text(f"[{log_entry['step']}] {log_entry['output'][:200]}")
                        
                        st.caption(f"• {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # Add to conversation history
                        st.session_state.conversation_history.append({
                            "question": prompt,
                            "answer": answer,
                            "sql": result.get("sql_used", "Agent-generated (multi-step)"),
                            "intermediate_steps": result.get("intermediate_steps", []),  # Store agent steps
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "mode": "agentic"
                        })
                        
                        # Hide examples after successful question processing
                        st.session_state.hide_examples = True
                        
                        # Trigger rerun to ensure new message is visible
                        st.rerun()
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        if error_msg.startswith("ERROR: "):
                            error_msg = error_msg[7:] 
                        elif error_msg.startswith("ERROR:"):
                            error_msg = error_msg[6:] 
                        message_placeholder.error(f"❌ {error_msg}")
    
    # Clear history button in sidebar
    if st.session_state.conversation_history:
        with st.sidebar:
            st.divider()
            if st.button("🗑️ Clear Chat History", type="secondary"):
                st.session_state.conversation_history = []
                st.session_state.execution_log = []
                st.session_state.llm_chat_history.clear()
                st.session_state.hide_examples = False
                st.rerun()


if __name__ == "__main__":
    main()

