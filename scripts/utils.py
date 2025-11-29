import pandas as pd
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Tuple
import json
import re
import os
import hashlib
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

"""
Utility functions and classes for Agentic AI transaction query system.

This module contains all agentic AI-related functionality including:
- Tool functions for SQL generation, query execution, query refinement, result analysis, and calculations
- TransactionQueryAgent class for orchestrating agentic workflows
"""

# ==================== CACHE UTILITY FUNCTIONS ====================

def get_cache_key(question: str, bank_ids: List[int], account_ids: List[int], 
                  current_date: Optional[str] = None, cache_type: str = "sql") -> str:
    """Generate a cache key from question and parameters."""
    # Normalize inputs
    question_lower = question.lower().strip()
    bank_ids_sorted = tuple(sorted(bank_ids))
    account_ids_sorted = tuple(sorted(account_ids))
    date_str = current_date or "none"
    
    # Create a unique key
    key_string = f"{cache_type}:{question_lower}:{bank_ids_sorted}:{account_ids_sorted}:{date_str}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_query_cache_key(query: str) -> str:
    """Generate a cache key for a SQL query."""
    # Normalize query
    query_normalized = ' '.join(query.split()).upper()
    key_string = f"query:{query_normalized}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_from_cache(cache_key: str, cache_dict: Optional[Dict[str, Any]]) -> Optional[Any]:
    """Retrieve value from cache if it exists."""
    if cache_dict is None:
        return None
    return cache_dict.get(cache_key)

def set_cache(cache_key: str, value: Any, cache_dict: Optional[Dict[str, Any]], max_size: int = 100):
    """Store value in cache with size limit."""
    if cache_dict is None:
        return
    
    # Remove oldest entry if cache is full (FIFO)
    if len(cache_dict) >= max_size:
        # Remove the first (oldest) entry
        oldest_key = next(iter(cache_dict))
        del cache_dict[oldest_key]
    
    cache_dict[cache_key] = value

# ==================== HELPER FUNCTIONS ====================

def validate_sql_query(
    sql_query: str,
    question: str,
    execution_log_callback: Optional[Callable] = None,
    step_name: str = "sql_validation"
) -> Tuple[bool, str]:
    """
    Validate SQL query for security. Returns (is_valid, error_message).
    If valid, error_message is empty string.
    """
    sql_validation_error_msg = "ERROR: I apologize, but I'm unable to process your question. Please rephrase it as a question about viewing or analyzing your transaction data."
    
    sql_upper = sql_query.upper().strip()
    
    # List of dangerous SQL operations that should be blocked
    dangerous_operations = [
        'DROP', 'DELETE', 'UPDATE', 'ALTER', 'CREATE', 'INSERT', 
        'TRUNCATE', 'EXEC', 'EXECUTE', 'REPLACE', 'ATTACH', 'DETACH',
        'VACUUM', 'PRAGMA', 'COMMIT', 'BEGIN', 'TRANSACTION', 'ROLLBACK'
    ]
    
    # Check if query starts with SELECT
    if not sql_upper.startswith('SELECT'):
        if execution_log_callback:
            execution_log_callback({
                "step": step_name,
                "input": question,
                "output": sql_validation_error_msg,
                "timestamp": datetime.now().isoformat()
            })
        return False, sql_validation_error_msg
    
    # Check for dangerous operations anywhere in the query
    for operation in dangerous_operations:
        pattern = r'\b' + re.escape(operation) + r'\b'
        if re.search(pattern, sql_upper):
            if execution_log_callback:
                execution_log_callback({
                    "step": step_name,
                    "input": question,
                    "output": sql_validation_error_msg,
                    "timestamp": datetime.now().isoformat()
                })
            return False, sql_validation_error_msg
    
    return True, ""

# ==================== TOOL FUNCTIONS ====================

def tool_generate_sql(
    question: str,
    schema: str,
    api_key: str,
    bank_ids: Optional[List[int]] = None,
    account_ids: Optional[List[int]] = None,
    current_date: Optional[str] = None,
    chat_history: Optional[InMemoryChatMessageHistory] = None,
    execution_log_callback: Optional[Callable] = None,
    sql_cache: Optional[Dict[str, str]] = None
) -> str:
    """
    Tool: Generate SQL query from natural language question.
    """
    # Validate mandatory parameters
    if not bank_ids or len(bank_ids) == 0:
        return f"ERROR: bank_ids is required and must contain at least one ID"
    if not account_ids or len(account_ids) == 0:
        return f"ERROR: account_ids is required and must contain at least one ID"
    
    # Check cache first
    if sql_cache is not None:
        cache_key = get_cache_key(question, bank_ids, account_ids, current_date, "sql")
        cached_sql = get_from_cache(cache_key, sql_cache)
        if cached_sql:
            if execution_log_callback:
                execution_log_callback({
                    "step": "generate_sql",
                    "input": question,
                    "output": f"[CACHED] {cached_sql[:100]}...",
                    "timestamp": datetime.now().isoformat()
                })
            return cached_sql
    
    try:
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1
        )
        
        # Use current_date if provided, otherwise use 'now'
        if current_date:
            date_ref = f"'{current_date}'"
            date_ref_sql = f"DATE('{current_date}')"
            datetime_ref_sql = f"datetime('{current_date}')"
        else:
            date_ref = "'now'"
            date_ref_sql = "DATE('now')"
            datetime_ref_sql = "datetime('now')"
        
        # Build filter clauses for bank_id and account_id (mandatory fields)
        bank_ids_str = ','.join(map(str, bank_ids))
        account_ids_str = ','.join(map(str, account_ids))
        bank_filter = f"AND bank_id IN ({bank_ids_str})"
        account_filter = f"AND account_id IN ({account_ids_str})"
        filter_examples = f"\n                        - MANDATORY filter by bank_id: bank_id IN ({bank_ids_str})\n                        - MANDATORY filter by account_id: account_id IN ({account_ids_str})"
        
        # Build prompt with date variables formatted
        current_date_ref_text = 'today (use DATE(\'now\'))' if not current_date else current_date
        
        prompt_text = f"""You are a SQL expert. Given a database schema and a natural language question, generate a SQL query to answer it.

                        Database Schema:
                        {{schema}}

                        Important Notes:
                        - Use ONLY SQLite date/time functions: DATE(), datetime(), strftime()
                        - Current date reference: {current_date_ref_text}
                        - For "today": {date_ref_sql}
                        - For "yesterday": DATE({date_ref}, '-1 day')
                        - For "last 7 days": datetime({date_ref}, '-7 days') to {datetime_ref_sql}
                        - For "last N months": DATE({date_ref}, '-N months')
                        - transaction_date is stored as DATETIME ('YYYY-MM-DD HH:MM:SS')
                        - Use DATE(transaction_date) when comparing only dates.
                        - Use LIKE or LOWER() for case-insensitive merchant/description/category matching
                        - Return ONLY the SQL query, no markdown, no explanations

                        Amount Rules (IMPORTANT):
                        - For money spent / debited → amounts are NEGATIVE → use SUM(amount) with `amount < 0`
                        - For money received / credited → amounts are POSITIVE → use SUM(amount) with `amount > 0`

                        Here are a few examples:

                        Example 1:
                        Question: What is the total amount I spent in the last 7 days?
                        SQL: SELECT SUM(amount) FROM transactions
                            WHERE amount < 0
                            AND transaction_date BETWEEN datetime({date_ref}, '-7 days') AND {datetime_ref_sql}
                            ORDER BY transaction_date;

                        Example 2:
                        Question: Show all Amazon transactions from last month.
                        SQL: SELECT * FROM transactions
                            WHERE LOWER(merchant) LIKE '%amazon%'
                            AND transaction_date >= DATE({date_ref}, '-1 month')
                            AND DATE(transaction_date) < DATE({date_ref})
                            ORDER BY transaction_date;

                        Example 3:
                        Question: How much did I spend yesterday on food?
                        SQL: SELECT SUM(amount) FROM transactions
                            WHERE amount < 0
                            AND LOWER(category) LIKE '%food%'
                            AND DATE(transaction_date) = DATE({date_ref}, '-1 day')
                            AND DATE(transaction_date) < DATE({date_ref})
                            ORDER BY transaction_date;

                        Example 4:
                        Question: How much money did I receive from amazon last month?
                        SQL: SELECT SUM(amount) FROM transactions
                            WHERE amount > 0
                            AND LOWER(merchant) LIKE '%amazon%'
                            AND transaction_date >= DATE({date_ref}, '-1 month')
                            AND DATE(transaction_date) < DATE({date_ref})
                            ORDER BY transaction_date;

                        Example 5:
                        Question: What is my total spending on groceries from Walmart?
                        SQL: SELECT SUM(amount) FROM transactions
                            WHERE amount < 0
                            AND LOWER(merchant) LIKE '%walmart%'
                            AND LOWER(category) LIKE '%groceries%'
                            AND DATE(transaction_date) <= DATE({date_ref})
                            ORDER BY transaction_date;
                        
                        Example 6:
                        Question: Which merchant am I spending the most money on?.
                        SQL: SELECT merchant, SUM(amount) AS total_spent FROM transactions 
                            WHERE amount < 0
                            GROUP BY merchant
                            ORDER BY total_spent
                            LIMIT 1;
                        
                        Example 7:
                        Question: Which merchant am I receiving the most money from?.
                        SQL: SELECT merchant, SUM(amount) AS total_received FROM transactions 
                            WHERE amount > 0
                            GROUP BY merchant
                            ORDER BY total_received DESC
                            LIMIT 1;

                        Now, given the following question, generate ONLY the SQL query, nothing else. Do not include markdown formatting, just the raw SQL query.:

                        Question: {{question}}"""
        
        # Build messages with chat history
        messages = []
        
        # Add system message
        messages.append(("system", "You are a SQL expert. Generate only SQL queries without any explanation or markdown formatting."))
        
        # Add chat history if available
        if chat_history:
            history_messages = chat_history.messages[-10:]
            for msg in history_messages:
                if isinstance(msg, HumanMessage):
                    messages.append(("human", f"Previous question: {msg.content}"))
                elif isinstance(msg, AIMessage):
                    messages.append(("assistant", f"Previous answer: {msg.content[:200]}..."))
        
        # Add current prompt
        messages.append(("human", prompt_text))
        
        prompt_template = ChatPromptTemplate.from_messages(messages)
        chain = prompt_template | llm
        response = chain.invoke({
            "schema": schema, 
            "question": question
        })
        
        raw_sql_output = response.content.strip()
        # Remove markdown code blocks if present
        sql_query = re.sub(r'^```(?:sql)?\s*', '', raw_sql_output, flags=re.MULTILINE)
        sql_query = re.sub(r'\s*```$', '', sql_query, flags=re.MULTILINE)
        sql_query = sql_query.strip()
        
        # ALWAYS add bank_id and account_id filters to the query
        bank_ids_str = ','.join(map(str, bank_ids))
        account_ids_str = ','.join(map(str, account_ids))
        
        if "bank_id" not in sql_query.lower():
            if "WHERE" in sql_query.upper():
                sql_query = sql_query + f" AND bank_id IN ({bank_ids_str})"
            else:
                sql_query = sql_query + f" WHERE bank_id IN ({bank_ids_str})"
        else:
            # Extract bank_id values from the query
            # Pattern 1: bank_id IN (1,2,3) or bank_id in (1,2,3)
            bank_id_match = re.search(
                r'bank_id\s+IN\s*\(([^)]+)\)',
                sql_query,
                flags=re.IGNORECASE
            )
            # Pattern 2: bank_id IN 1,2,3 or bank_id in 1,2,3 (without parentheses)
            if not bank_id_match:
                bank_id_match = re.search(
                    r'bank_id\s+IN\s+([0-9,\s]+)(?:\s|AND|OR|$|;|\))',
                    sql_query,
                    flags=re.IGNORECASE
                )
            # Pattern 3: bank_id = 1
            if not bank_id_match:
                bank_id_match = re.search(
                    r'bank_id\s*=\s*(\d+)(?:\s|AND|OR|$|;|\))',
                    sql_query,
                    flags=re.IGNORECASE
                )
            
            if bank_id_match:
                # Parse the bank IDs from the query
                query_bank_ids_str = bank_id_match.group(1)
                # Extract numeric IDs (handle both comma-separated and whitespace)
                query_bank_ids = set()
                for id_str in re.split(r'[,\s]+', query_bank_ids_str):
                    id_str = id_str.strip()
                    if id_str and id_str.isdigit():
                        query_bank_ids.add(int(id_str))
                
                # Check if query bank IDs are a subset of allowed bank IDs
                allowed_bank_ids_set = set(bank_ids)
                if not query_bank_ids.issubset(allowed_bank_ids_set):
                    error_msg = "ERROR: I apologize, but I'm unable to process your question. Please rephrase it as a question about viewing or analyzing your transaction data."
                    if execution_log_callback:
                        execution_log_callback({
                            "step": "generate_sql",
                            "input": question,
                            "output": f"The query contains bank_id values that are not in the allowed bank IDs. Allowed: {sorted(allowed_bank_ids_set)}, Found in query: {sorted(query_bank_ids)}",
                            "timestamp": datetime.now().isoformat()
                        })
                    return error_msg
                # If it's a valid subset, keep the query as is (don't replace)
            else:
                # If pattern doesn't match but bank_id is mentioned, add the filter
                if "WHERE" in sql_query.upper():
                    sql_query = sql_query + f" AND bank_id IN ({bank_ids_str})"
                else:
                    sql_query = sql_query + f" WHERE bank_id IN ({bank_ids_str})"
        
        if "account_id" not in sql_query.lower():
            if "WHERE" in sql_query.upper():
                sql_query = sql_query + f" AND account_id IN ({account_ids_str})"
            else:
                sql_query = sql_query + f" WHERE account_id IN ({account_ids_str})"
        else:
            # Extract account_id values from the query
            # Pattern 1: account_id IN (1,2,3) or account_id in (1,2,3)
            account_id_match = re.search(
                r'account_id\s+IN\s*\(([^)]+)\)',
                sql_query,
                flags=re.IGNORECASE
            )
            # Pattern 2: account_id IN 1,2,3 or account_id in 1,2,3 (without parentheses)
            if not account_id_match:
                account_id_match = re.search(
                    r'account_id\s+IN\s+([0-9,\s]+)(?:\s|AND|OR|$|;|\))',
                    sql_query,
                    flags=re.IGNORECASE
                )
            # Pattern 3: account_id = 1
            if not account_id_match:
                account_id_match = re.search(
                    r'account_id\s*=\s*(\d+)(?:\s|AND|OR|$|;|\))',
                    sql_query,
                    flags=re.IGNORECASE
                )
            
            if account_id_match:
                # Parse the account IDs from the query
                query_account_ids_str = account_id_match.group(1)
                # Extract numeric IDs (handle both comma-separated and whitespace)
                query_account_ids = set()
                for id_str in re.split(r'[,\s]+', query_account_ids_str):
                    id_str = id_str.strip()
                    if id_str and id_str.isdigit():
                        query_account_ids.add(int(id_str))
                
                # Check if query account IDs are a subset of allowed account IDs
                allowed_account_ids_set = set(account_ids)
                if not query_account_ids.issubset(allowed_account_ids_set):
                    error_msg = "ERROR: I apologize, but I'm unable to process your question. Please rephrase it as a question about viewing or analyzing your transaction data."
                    if execution_log_callback:
                        execution_log_callback({
                            "step": "generate_sql",
                            "input": question,
                            "output": f"The query contains account_id values that are not in the allowed account IDs. Allowed: {sorted(allowed_account_ids_set)}, Found in query: {sorted(query_account_ids)}",
                            "timestamp": datetime.now().isoformat()
                        })
                    return error_msg
                # If it's a valid subset, keep the query as is (don't replace)
            else:
                # If pattern doesn't match but account_id is mentioned, add the filter
                if "WHERE" in sql_query.upper():
                    sql_query = sql_query + f" AND account_id IN ({account_ids_str})"
                else:
                    sql_query = sql_query + f" WHERE account_id IN ({account_ids_str})"
        
        # Validate SQL query for dangerous operations
        is_valid, error_msg = validate_sql_query(
            sql_query,
            question,
            execution_log_callback,
            "generate_sql"
        )
        if not is_valid:
            return error_msg
        
        # Store raw LLM output in chat_history
        if chat_history:
            # Add raw SQL output
            if not chat_history.messages or not isinstance(chat_history.messages[-1], HumanMessage):
                chat_history.add_user_message(question)
            chat_history.add_ai_message(raw_sql_output)
        
        # Store in cache
        if sql_cache is not None:
            cache_key = get_cache_key(question, bank_ids, account_ids, current_date, "sql")
            set_cache(cache_key, sql_query, sql_cache)
        
        # Log execution
        if execution_log_callback:
            execution_log_callback({
                "step": "generate_sql",
                "input": question,
                "output": sql_query,
                "timestamp": datetime.now().isoformat()
            })
        
        return sql_query
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        if execution_log_callback:
            execution_log_callback({
                "step": "generate_sql",
                "input": question,
                "output": error_msg,
                "timestamp": datetime.now().isoformat()
            })
        return error_msg


def tool_execute_query(
    query: str, 
    bank_ids: Optional[List[int]],
    account_ids: Optional[List[int]],
    get_db_connection_func: Callable,
    execution_log_callback: Optional[Callable] = None,
    query_result_cache: Optional[Dict[str, str]] = None
) -> str:
    """Tool: Execute SQL query and return results as JSON string."""
    try:
        # Validate mandatory parameters
        if not bank_ids or len(bank_ids) == 0:
            return f"ERROR: bank_ids is required and must contain at least one ID"
        if not account_ids or len(account_ids) == 0:
            return f"ERROR: account_ids is required and must contain at least one ID"
        
        # Replace or add bank_id filter first 
        original_query = query
        if bank_ids and len(bank_ids) > 0:
            bank_ids_str = ','.join(map(str, bank_ids))
            if "bank_id" in query.lower():
                query = re.sub(
                    r'bank_id\s+IN\s*\([^)]+\)',
                    f'bank_id IN ({bank_ids_str})',
                    query,
                    flags=re.IGNORECASE
                )
            else:
                # Add bank_id filter
                if "WHERE" in query.upper():
                    query = query + f" AND bank_id IN ({bank_ids_str})"
                else:
                    query = query + f" WHERE bank_id IN ({bank_ids_str})"
        
        # Replace or add account_id filter
        if account_ids and len(account_ids) > 0:
            account_ids_str = ','.join(map(str, account_ids))
            if "account_id" in query.lower():
                query = re.sub(
                    r'account_id\s+IN\s*\([^)]+\)',
                    f'account_id IN ({account_ids_str})',
                    query,
                    flags=re.IGNORECASE
                )
            else:
                # Add account_id filter
                if "WHERE" in query.upper():
                    query = query + f" AND account_id IN ({account_ids_str})"
                else:
                    query = query + f" WHERE account_id IN ({account_ids_str})"
        
        # Check cache after query normalization
        if query_result_cache is not None:
            cache_key = get_query_cache_key(query)
            cached_result = get_from_cache(cache_key, query_result_cache)
            if cached_result:
                if execution_log_callback:
                    execution_log_callback({
                        "step": "execute_query",
                        "input": query[:100] + "..." if len(query) > 100 else query,
                        "output": "[CACHED] Query result retrieved from cache",
                        "timestamp": datetime.now().isoformat()
                    })
                return cached_result
        
        conn = get_db_connection_func()
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Convert to JSON for agent to process
        if df.empty:
            result = {"status": "empty", "message": "I couldn't find any transactions matching your criteria. Please try adjusting your search filters or date range.", "count": 0}
        else:
            # Limit rows for token efficiency
            if len(df) > 100:
                result = {
                    "status": "success",
                    "count": len(df),
                    "rows": df.head(100).to_dict('records'),
                    "message": f"Showing first 100 of {len(df)} rows"
                }
            else:
                result = {
                    "status": "success",
                    "count": len(df),
                    "rows": df.to_dict('records')
                }
        
        log_entry = {
            "step": "execute_query",
            "input": query,
            "output": f"Success: {result['count']} rows",
            "timestamp": datetime.now().isoformat()
        }
        
        if execution_log_callback:
            execution_log_callback(log_entry)
        
        exec_result = json.dumps(result, default=str)
        
        # Store in cache
        if query_result_cache is not None:
            cache_key = get_query_cache_key(query)
            set_cache(cache_key, exec_result, query_result_cache)
        
        return exec_result
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        if execution_log_callback:
            execution_log_callback({
                "step": "execute_query",
                "input": query,
                "output": error_msg,
                "timestamp": datetime.now().isoformat()
            })
        return error_msg


def tool_validate_question_context(
    question: str, 
    api_key: str,
    execution_log_callback: Optional[Callable] = None
) -> str:
    """
    Tool: Validate if the question is related to bank transactions.
    """
    try:
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that determines if questions are related to bank transactions and financial data."),
            ("human", """Determine if the following question is related to bank transactions, financial data, spending, or payment history.

            Question: {question}

            This system can ONLY answer questions about:
            - Bank transaction history
            - Spending amounts and patterns
            - Payment records
            - Financial transactions (deposits, withdrawals, purchases)
            - Merchant/category-based queries
            - Account balances and activity
            - Date/time-based transaction queries

            It CANNOT answer questions about:
            - General knowledge (e.g., presidents, countries, history)
            - Non-financial topics
            - External information not in the transaction database

            Respond with ONLY "YES" if the question is transaction-related, or "NO" if it is not. Do not provide any explanation, just "YES" or "NO"."""),
        ])
        
        chain = prompt_template | llm
        response = chain.invoke({"question": question})
        
        result = response.content.strip().upper()
        
        if result == "YES":
            is_valid = True
            error_message = None
        else:
            is_valid = False
            error_message = """I apologize, but I can only answer questions about your bank transactions and financial data.

                            I can help you with questions about:
                            • Spending amounts and totals (e.g., "How much did I spend last week?")
                            • Transaction history (e.g., "Show me all Amazon transactions")
                            • Category or merchant-based queries (e.g., "What did I spend on groceries?")
                            • Date/time-based queries (e.g., "Transactions from last month")
                            • Payment and financial activity analysis

                            Please ask a question related to your bank transactions."""
        
        result = {
            "valid": is_valid,
            "error": error_message
        }
        
        if execution_log_callback:
            execution_log_callback({
                "step": "validate_question_context",
                "input": question,
                "output": f"Valid: {is_valid}",
                "timestamp": datetime.now().isoformat()
            })
        
        return json.dumps(result)
        
    except Exception as e:
        # On error, allow the question through (fail open)
        result = {
            "valid": True,
            "error": None
        }
        if execution_log_callback:
            execution_log_callback({
                "step": "validate_question_context",
                "input": question,
                "output": f"Error (fail open): {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        return json.dumps(result)


def tool_refine_query(
    original_query: str, 
    error_message: str, 
    question: str, 
    schema: str, 
    api_key: str,
    execution_log_callback: Optional[Callable] = None
) -> str:
    """Tool: Refine a SQL query based on error feedback."""
    try:
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a SQL expert. Fix SQL errors by refining queries."),
            ("human", """A SQL query failed with an error. Please fix it.

            Original Question: {question}

            Original Query:
            {original_query}

            Error Message:
            {error_message}

            Database Schema:
            {schema}

            Please provide a corrected SQL query. Return ONLY the SQL query, no explanations, no markdown.

            Corrected Query:""")
        ])
        
        chain = prompt_template | llm
        response = chain.invoke({
            "question": question,
            "original_query": original_query,
            "error_message": error_message,
            "schema": schema
        })
        
        refined_query = response.content.strip()
        refined_query = re.sub(r'^```(?:sql)?\s*', '', refined_query, flags=re.MULTILINE)
        refined_query = re.sub(r'\s*```$', '', refined_query, flags=re.MULTILINE)
        refined_query = refined_query.strip()
        
        # Validate the refined query for security
        is_valid, error_msg = validate_sql_query(
            refined_query,
            question,
            execution_log_callback,
            "refine_query"
        )
        if not is_valid:
            if execution_log_callback:
                execution_log_callback({
                    "step": "refine_query",
                    "input": f"Error: {error_message}",
                    "output": error_msg,
                    "timestamp": datetime.now().isoformat()
                })
            return error_msg
        
        if execution_log_callback:
            execution_log_callback({
                "step": "refine_query",
                "input": f"Error: {error_message}",
                "output": refined_query,
                "timestamp": datetime.now().isoformat()
            })
        
        return refined_query
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        if execution_log_callback:
            execution_log_callback({
                "step": "refine_query",
                "input": f"Error: {error_message}",
                "output": error_msg,
                "timestamp": datetime.now().isoformat()
            })
        return error_msg


def tool_analyze_results(
    results_json: str, 
    question: str, 
    api_key: str,
    calculation_result: Optional[str] = None,
    chat_history: Optional[InMemoryChatMessageHistory] = None,
    execution_log_callback: Optional[Callable] = None,
    sql_query: Optional[str] = None,
    db_connection_getter: Optional[Callable] = None,
    bank_ids: Optional[List[int]] = None,
    account_ids: Optional[List[int]] = None
) -> str:
    """Tool: Analyze query results and extract relevant information."""
    try:
        results = json.loads(results_json)
        
        if results.get("status") == "empty":
            return "I couldn't find any transactions matching your criteria. Please try adjusting your search filters or date range."
        
        rows = results.get("rows", [])
        if not rows:
            return "I couldn't find any transaction data to analyze. Please try adjusting your search criteria."
        
        # Use LLM to analyze results
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.3
        )
        
        # Use LLM to detect if question is asking for records/list vs summary
        try:
            detection_llm = ChatGroq(
                groq_api_key=api_key,
                model_name="llama-3.3-70b-versatile",
                temperature=0.1
            )
            
            detection_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a question classifier. Determine if a question is asking to SHOW/LIST/DISPLAY transaction records or asking for a SUMMARY/TOTAL/CALCULATION."),
                ("human", """Classify the following question:

                Question: {question}

                Determine if this question is asking to:
                - SHOW/LIST/DISPLAY transaction records (e.g., "show me transactions", "list all transactions", "display my purchases")
                - OR asking for a SUMMARY/TOTAL/CALCULATION (e.g., "how much", "total spending", "what's my balance")

                Respond with ONLY one word: either "RECORDS" or "SUMMARY".
                """)
            ])
            
            detection_chain = detection_prompt | detection_llm
            detection_response = detection_chain.invoke({"question": question})
            detection_result = detection_response.content.strip().upper()
            
            is_record_list_question = "RECORD" in detection_result
        except Exception as e:
            # On error, default to summary
            is_record_list_question = False
        
        # For record-list questions, convert directly to CSV format
        if is_record_list_question:
            # Get preview rows (first 100) for display
            preview_rows = rows[:100]
            total_count = results.get("count", len(rows))
            
            # Try to get ALL rows for CSV download if SQL query is provided
            all_rows_for_csv = preview_rows  # Default to preview rows
            if sql_query and db_connection_getter and total_count > len(preview_rows):
                try:
                    # Re-execute query to get ALL rows for CSV
                    conn = db_connection_getter()
                    df_all = pd.read_sql_query(sql_query, conn)
                    conn.close()
                    all_rows_for_csv = df_all.to_dict('records')
                except Exception as e:
                    # If re-execution fails, use preview rows
                    all_rows_for_csv = preview_rows
            
            # Convert to DataFrame and generate CSV strings
            try:
                # Preview DataFrame (first 100 rows)
                df_preview = pd.DataFrame(preview_rows)
                csv_preview = df_preview.to_csv(index=False)
                
                # Full DataFrame (all rows)
                df_full = pd.DataFrame(all_rows_for_csv)
                csv_full = df_full.to_csv(index=False)
                
                # Return CSV with special marker prefix
                intro_text = f"Found {total_count} transaction(s). Here is your CSV file:"
                
                return f"CSV_DATA:{intro_text}\nCSV_PREVIEW:\n{csv_preview}\nCSV_FULL:\n{csv_full}"
                
            except Exception as csv_error:
                # If CSV conversion fails, return error message
                return f"ERROR: Failed to generate CSV file: {str(csv_error)}"
        else:
            # Limit to 20 rows for summary questions
            data_rows = rows[:20]
        
        # For summary questions, continue with LLM analysis
        sample_rows = json.dumps(data_rows, default=str)
        
        # Build prompt with optional calculation result
        calculation_context = ""
        if calculation_result and not calculation_result.startswith("ERROR"):
            clean_calc_result = " ".join(calculation_result.split()).strip()
            calculation_context = f"\n\nAdditional Information: The calculation result is {clean_calc_result}. Use this value naturally in your answer."
        
        prompt_text = f"""Analyze these query results and answer the user's question.

                Question: {{question}}

                Results (JSON):
                {{sample_rows}}

                Total rows: {{count}}
                
                {calculation_context}

                Instructions:
                - Answer only what was asked, nothing more
                - Be brief and direct
                - Format currency amounts with dollar signs and proper commas (e.g., $1,234.56)
                - Do not explain the data or provide context
                - Do not add summaries or interpretations beyond what's directly in the results
                - Keep responses minimal and factual
                - Write in plain text with normal spacing - do not remove spaces between words
                - Remove negative sign from amounts
                
                Examples:
                Example 1 (Summary):
                Question: How much did I spend last week?
                Response: You spent $1,234.56 last week.

                Example 2 (Calculation):
                Question: Compare my last month spending with this month?
                Response: You spent $234.56 more this month than last month.

                Now generate the appropriate response:
                """
        
        # Build messages with chat history
        messages = []
        
        # Add system message
        messages.append(("system", "You are a data analyst. Analyze query results and provide insights. Provide natural language summaries for calculation questions."))
        
        # Add chat history if available
        if chat_history:
            history_messages = chat_history.messages[-10:]  # Last 10 messages (5 exchanges)
            for msg in history_messages:
                if isinstance(msg, HumanMessage):
                    messages.append(("human", msg.content))
                elif isinstance(msg, AIMessage):
                    messages.append(("assistant", msg.content))
        
        # Add current prompt
        messages.append(("human", prompt_text))
        
        prompt_template = ChatPromptTemplate.from_messages(messages)
        
        chain = prompt_template | llm
        response = chain.invoke({
            "question": question,
            "sample_rows": sample_rows,
            "count": results.get("count", len(rows))
        })
        
        analysis = response.content.strip()  # Raw LLM output
        
        # Store raw LLM output in chat_history
        if chat_history and not is_record_list_question:
            # Add raw LLM analysis output - this is the LLM's direct response
            chat_history.add_ai_message(analysis)
        
        if execution_log_callback:
            execution_log_callback({
                "step": "analyze_results",
                "input": f"{results.get('count', 0)} rows",
                "output": analysis[:200] + "...",
                "timestamp": datetime.now().isoformat()
            })
        
        return analysis
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        if execution_log_callback:
            execution_log_callback({
                "step": "analyze_results",
                "input": results_json[:100] + "...",
                "output": error_msg,
                "timestamp": datetime.now().isoformat()
            })
        return error_msg


def tool_calculate(
    calculation_request: str, 
    api_key: str,
    execution_log_callback: Optional[Callable] = None
) -> str:
    """Tool: Perform calculations on numeric results."""
    try:
        # Simple calculation handler - can be enhanced
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a calculator. Perform mathematical calculations accurately."),
            ("human", """Perform this calculation and return only the result as a number or percentage:

            {calculation_request}

            Return only the numeric result, no explanations.""")
        ])
        
        chain = prompt_template | llm
        response = chain.invoke({"calculation_request": calculation_request})
        
        result = response.content.strip()
        
        if execution_log_callback:
            execution_log_callback({
                "step": "calculate",
                "input": calculation_request,
                "output": result,
                "timestamp": datetime.now().isoformat()
            })
        
        return result
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        if execution_log_callback:
            execution_log_callback({
                "step": "calculate",
                "input": calculation_request,
                "output": error_msg,
                "timestamp": datetime.now().isoformat()
            })
        return error_msg

# ==================== AGENT ORCHESTRATOR ====================

class TransactionQueryAgent:
    """Agentic AI orchestrator for transaction queries."""
    
    def __init__(
        self, 
        api_key: str, 
        bank_ids: Optional[List[int]] = None,
        account_ids: Optional[List[int]] = None,
        current_date: Optional[str] = None,
        schema_getter: Optional[Callable] = None,
        db_connection_getter: Optional[Callable] = None,
        chat_history: Optional[InMemoryChatMessageHistory] = None,
        execution_log_callback: Optional[Callable] = None,
        sql_cache: Optional[Dict[str, str]] = None,
        query_result_cache: Optional[Dict[str, str]] = None,
        analysis_cache: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the TransactionQueryAgent.
        
        Args:
            api_key: Groq API key for LLM access
            bank_ids: List of bank IDs for filtering queries (REQUIRED - must contain at least one ID)
            account_ids: List of account IDs for filtering queries (REQUIRED - must contain at least one ID)
            current_date: Current date reference in 'YYYY-MM-DD' format (defaults to None, which uses 'now')
            schema_getter: Function to get database schema
            db_connection_getter: Function to get database connection
            chat_history: Optional InMemoryChatMessageHistory for maintaining conversation context
            execution_log_callback: Optional callback for logging execution steps
        """
        # Validate mandatory parameters
        if not bank_ids or len(bank_ids) == 0:
            raise ValueError("bank_ids is required and must contain at least one ID")
        if not account_ids or len(account_ids) == 0:
            raise ValueError("account_ids is required and must contain at least one ID")
        
        self.api_key = api_key
        self.bank_ids = bank_ids
        self.account_ids = account_ids
        self.current_date = current_date
        self.schema_getter = schema_getter
        self.db_connection_getter = db_connection_getter
        self.chat_history = chat_history
        self.execution_log_callback = execution_log_callback
        self.sql_cache = sql_cache
        self.query_result_cache = query_result_cache
        self.analysis_cache = analysis_cache
        self.max_retries = 3
        
        # Get schema if getter provided
        if self.schema_getter:
            self.schema = self.schema_getter()
        else:
            self.schema = ""
    
    def create_tools(self) -> List:
        """Create tools for the agent."""
        if StructuredTool is None:
            return []
        
        tools = [
            StructuredTool.from_function(
                func=lambda q, k=self.api_key, cb=self.execution_log_callback: 
                    tool_validate_question_context(q, k, cb),
                name="validate_question_context",
                description="Validate if a question is related to bank transactions. Input: the user's question as a string. Returns JSON with validation result. Use this BEFORE generating SQL to check if the question is valid."
            ),
            StructuredTool.from_function(
                func=lambda q, s=self.schema, k=self.api_key, bi=self.bank_ids, ai=self.account_ids, cd=self.current_date, ch=self.chat_history, cb=self.execution_log_callback: 
                    tool_generate_sql(q, s, k, bi, ai, cd, ch, cb),
                name="generate_sql",
                description="Generate a SQL query from a natural language question. Input: the user's question as a string. Use this to create SQL queries."
            ),
            StructuredTool.from_function(
                func=lambda q, bi=self.bank_ids, ai=self.account_ids, db_func=self.db_connection_getter, cb=self.execution_log_callback: 
                    tool_execute_query(q, bi, ai, db_func, cb),
                name="execute_query",
                description="Execute a SQL query and get results. Input: SQL query string. Returns JSON with results. Use this after generating SQL."
            ),
            StructuredTool.from_function(
                func=lambda oq, em, q, s=self.schema, k=self.api_key, cb=self.execution_log_callback: 
                    tool_refine_query(oq, em, q, s, k, cb),
                name="refine_query",
                description="Refine a SQL query when it fails. Input: (original_query, error_message, original_question). Use this when execute_query returns an error."
            ),
            StructuredTool.from_function(
                func=lambda rj, q, k=self.api_key, cr=None, ch=self.chat_history, cb=self.execution_log_callback: 
                    tool_analyze_results(rj, q, k, cr, ch, cb),
                name="analyze_results",
                description="Analyze query results to extract insights. Input: (results_json, original_question, optional_calculation_result). Use this to understand query results."
            ),
            StructuredTool.from_function(
                func=lambda cr, k=self.api_key, cb=self.execution_log_callback: 
                    tool_calculate(cr, k, cb),
                name="calculate",
                description="Perform mathematical calculations (percentages, averages, etc.). Input: calculation request as string. Use this for calculations on results."
            )
        ]
        return tools
    
    def _needs_calculation(self, question: str) -> bool:
        """Check if question requires mathematical calculation."""
        calculation_keywords = [
            "percentage", "percent", "%", "average", "avg", "mean", 
            "ratio", "difference", "more than", "less than", "calculate",
            "compare", "comparison", "increase", "decrease", "change",
            "growth", "trend", "per", "rate"
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in calculation_keywords)
    
    def process_question(self, question: str, context: List[Dict] = None) -> Dict[str, Any]:
        """Process a question using agentic AI with manual tool orchestration."""        
        # Ensure schema is available
        if not self.schema and self.schema_getter:
            self.schema = self.schema_getter()
        
        try:
            # Initialize LLM
            llm = ChatGroq(
                groq_api_key=self.api_key,
                model_name="llama-3.3-70b-versatile",
                temperature=0.2
            )
            
            # Build context
            context_str = ""
            if context:
                context_str = "\n\nPrevious conversation:\n"
                for entry in context[-3:]:  # Last 3 entries
                    context_str += f"Q: {entry.get('question', '')}\nA: {entry.get('answer', '')[:100]}...\n"
            
            # Manual agentic loop (since agent framework may not be available)
            max_iterations = 5
            iteration = 0
            current_sql = None
            last_error = None
            intermediate_steps = []
            
            while iteration < max_iterations:
                iteration += 1
                
                if iteration == 1:
                    # Step 0: Validate question context
                    thought = "I need to validate if this question is related to bank transactions."
                    action = "validate_question_context"
                    action_input = question
                    
                    validation_result = tool_validate_question_context(
                        question,
                        self.api_key,
                        self.execution_log_callback
                    )
                    
                    # Parse validation result
                    try:
                        validation_data = json.loads(validation_result)
                        is_valid = validation_data.get("valid", True)
                        error_message = validation_data.get("error")
                        
                        if not is_valid:
                            intermediate_steps.append({
                                "thought": thought,
                                "action": action,
                                "input": action_input,
                                "result": f"Invalid: {error_message}"
                            })
                            return {
                                "success": False,
                                "error": error_message,
                                "intermediate_steps": intermediate_steps,
                                "answer": None
                            }
                    except (json.JSONDecodeError, KeyError) as e:
                        # If parsing fails, allow through
                        pass
                    
                    intermediate_steps.append({
                        "thought": thought,
                        "action": action,
                        "input": action_input,
                        "result": "Valid: Question is transaction-related"
                    })
                    
                    # Store user question in chat_history at the start
                    if self.chat_history and iteration == 1:
                        # Check if already added
                        if not self.chat_history.messages or not isinstance(self.chat_history.messages[-1], HumanMessage):
                            self.chat_history.add_user_message(question)
                    
                    # Step 1: Generate SQL query
                    thought = "I need to generate a SQL query to answer this question."
                    action = "generate_sql"
                    action_input = question
                    
                    sql_result = tool_generate_sql(
                        question, 
                        self.schema, 
                        self.api_key,
                        self.bank_ids,
                        self.account_ids,
                        self.current_date,
                        self.chat_history,
                        self.execution_log_callback,
                        self.sql_cache
                    )
                    if sql_result.startswith("ERROR"):
                        return {
                            "success": False, 
                            "error": sql_result,
                            "intermediate_steps": intermediate_steps,
                            "sql_used": None
                        }
                    
                    current_sql = sql_result
                    intermediate_steps.append({
                        "thought": thought,
                        "action": action,
                        "input": action_input,
                        "result": current_sql[:100] + "..."
                    })
                
                # Step 2: Execute query
                thought = "I need to execute the SQL query and check if it works."
                action = "execute_query"
                action_input = current_sql
                
                exec_result = tool_execute_query(
                    current_sql, 
                    self.bank_ids,
                    self.account_ids,
                    self.db_connection_getter,
                    self.execution_log_callback,
                    self.query_result_cache
                )
                
                if exec_result.startswith("ERROR"):
                    # Step 2a: Refine query if it failed
                    last_error = exec_result
                    thought = f"The query failed with error: {exec_result}. I need to refine it."
                    action = "refine_query"
                    
                    refined_sql = tool_refine_query(
                        current_sql,
                        exec_result,
                        question,
                        self.schema,
                        self.api_key,
                        self.execution_log_callback
                    )
                    
                    if refined_sql.startswith("ERROR"):
                        return {
                            "success": False, 
                            "error": f"Could not refine query: {refined_sql}",
                            "intermediate_steps": intermediate_steps,
                            "sql_used": current_sql
                        }
                    
                    current_sql = refined_sql
                    intermediate_steps.append({
                        "thought": thought,
                        "action": action,
                        "input": f"Error: {exec_result[:100]}...",
                        "result": refined_sql[:100] + "..."
                    })
                    continue
                
                # Step 3: Check if calculation is needed
                exec_result_json = exec_result
                calculation_result = None
                
                if self._needs_calculation(question):
                    thought = "The question requires a mathematical calculation. I'll perform it now."
                    action = "calculate"
                    
                    # Prepare calculation request with context from query results
                    calc_request = f"""Question: {question}

                    Data from query results: {exec_result_json[:500]}

                    Based on the above data and question, perform the requested mathematical calculation. 
                    Extract the relevant numbers from the data and calculate the answer.
                    Return only the numeric result with appropriate units (e.g., $123.45, 25%, etc.), no explanations."""
                    
                    calc_result = tool_calculate(
                        calc_request,
                        self.api_key,
                        self.execution_log_callback
                    )
                    
                    if not calc_result.startswith("ERROR"):
                        calculation_result = calc_result
                        
                        intermediate_steps.append({
                            "thought": thought,
                            "action": action,
                            "input": calc_request[:150] + "...",
                            "result": calc_result
                        })
                    else:
                        # If calculation fails, log it but continue without calculation
                        intermediate_steps.append({
                            "thought": thought,
                            "action": action,
                            "input": calc_request[:150] + "...",
                            "result": f"Calculation failed: {calc_result}"
                        })
                
                # Step 4: Analyze results
                thought = "The query succeeded. Now I need to analyze the results and format the answer."
                action = "analyze_results"
                
                analysis = tool_analyze_results(
                    exec_result_json, 
                    question, 
                    self.api_key,
                    calculation_result,
                    self.chat_history,
                    self.execution_log_callback,
                    sql_query=current_sql,
                    db_connection_getter=self.db_connection_getter,
                    bank_ids=self.bank_ids,
                    account_ids=self.account_ids
                )
                
                intermediate_steps.append({
                    "thought": thought,
                    "action": action,
                    "input": f"Results: {exec_result_json[:100]}..." + (f" | Calculation: {calculation_result}" if calculation_result else ""),
                    "result": analysis[:200] + "..."
                })
                
                # Final answer
                return {
                    "success": True,
                    "answer": analysis,
                    "intermediate_steps": intermediate_steps,
                    "sql_used": current_sql
                }
            
            # Max iterations reached
            return {
                "success": False,
                "error": f"Could not complete query after {max_iterations} iterations. Last error: {last_error}",
                "intermediate_steps": intermediate_steps,
                "sql_used": current_sql if current_sql else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Agent error: {str(e)}",
                "intermediate_steps": [],
                "sql_used": None
            }