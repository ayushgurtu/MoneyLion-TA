# Agentic AI Architecture for Transaction Query System

## Overview

`chatbot.py` implements a **fully agentic AI architecture** for querying bank transactions using natural language. This approach provides robust error handling, multi-step reasoning, intelligent query refinement, and a conversational chatbot interface.

The system uses LangChain for LLM orchestration and Groq's `llama-3.3-70b-versatile` model for all LLM operations including SQL generation, query refinement, result analysis, spell checking, and question validation.

## Key Features

### 🤖 Agentic AI Capabilities

1. **Multi-Step Reasoning**: The agent can break down complex queries into multiple steps
2. **Error Recovery**: Automatically refines failed SQL queries based on error messages (up to 3 retries)
3. **Tool-Based Architecture**: Uses specialized tools for different tasks
4. **Context Awareness**: Maintains conversation history using LangChain's `InMemoryChatMessageHistory`
5. **Execution Logging**: Tracks all agent steps for debugging and transparency
6. **Question Validation**: Validates if questions are transaction-related before processing
7. **Spell Checking**: Automatically corrects spelling errors in user questions (silent/internal)
8. **Smart Output Formatting**: Automatically detects if user wants records (CSV) or summary (natural language)

### 💬 Conversational Chatbot Interface

- **Streamlit Chat UI**: Modern chatbot interface with `st.chat_input` and `st.chat_message`
- **Example Questions**: Clickable example questions for user guidance
- **Chat History**: Persistent conversation history with timestamps
- **SQL Visibility**: Expandable SQL queries for transparency
- **CSV Download**: Downloadable CSV files for record-list questions

### 🔒 Security Features

1. **SQL Injection Prevention**: Validates SQL queries to ensure they only contain SELECT statements
2. **Dangerous Operation Blocking**: Blocks DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, and other dangerous SQL operations
3. **User-Friendly Error Messages**: Returns polite error messages for security violations

### 🎯 Smart Features

1. **LLM-Based Question Classification**: Automatically determines if user wants records (CSV) or summary (text)
2. **Dynamic Filtering**: Bank IDs and Account IDs are dynamically filtered and validated
3. **Date Reference**: Current date can be set via date picker for temporal queries
4. **Mandatory Filters**: Bank IDs and Account IDs are required for all queries

## Architecture Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                      (Streamlit Chatbot)                             │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  User Question  │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Spell Checking  │
                          │    (LLM)        │
                          └────────┬────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
          ┌──────────────────┐        ┌──────────────────┐
          │   Has Errors?    │        │  No Errors       │
          └────────┬─────────┘        └────────┬─────────┘
                   │                           │
        ┌──────────┴──────────┐                │
        │                     │                │
        ▼                     ▼                │
┌──────────────┐    ┌─────────────────┐        │
│   Corrected  │    │  Original Question│      │
│   Question   │    │   (unchanged)    │       │
└──────┬───────┘    └────────┬─────────┘       │
       │                     │                 │
       └──────────┬──────────┘                 │
                  │                            │
                  └───────────┬────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Question Validation  │
                   │       (LLM)          │
                   └──────────┬───────────┘
                              │
               ┌──────────────┴──────────────┐
               │                             │
               ▼                             ▼
       ┌───────────────┐          ┌─────────────────┐
       │ Invalid - Out │          │   Valid - OK    │
       │  of Context   │          └────────┬────────┘
       └───────┬───────┘                   │
               │                           │
               │                           ▼
               │                  ┌─────────────────┐
               │                  │  Generate SQL   │
               │                  │ (with filters)  │
               │                  └────────┬────────┘
               │                           │
               │                           ▼
               │                  ┌─────────────────┐
               │                  │ Validate SQL    │
               │                  │(Security Check) │
               │                  └────────┬────────┘
               │                           │
               │              ┌────────────┴────────────┐
               │              │                         │
               │              ▼                         ▼
               │      ┌───────────────┐      ┌─────────────────┐
               │      │   Security    │      │  Secure Query   │
               │      │  Violation    │      └────────┬────────┘
               │      └───────┬───────┘               │
               │              │                       │
               │              │                       ▼
               │              │              ┌─────────────────┐
               │              │              │ Execute Query   │
               │              │              └────────┬────────┘
               │              │                       │
               └──────────────┴───────────┬───────────┘
                                          │
                          ┌───────────────┴───────────────┐
                          │                               │
                          ▼                               ▼
                  ┌───────────────┐          ┌─────────────────┐
                  │  Query Error  │          │ Query Success   │
                  └───────┬───────┘          └────────┬────────┘
                          │                           │
              ┌───────────┴───────────┐               │
              │                       │               │
              ▼                       ▼               │
      ┌───────────────┐    ┌─────────────────┐        │
      │ Retry Count   │    │  Refine Query   │        │
      │    >= 3?      │    │     (LLM)       │        │
      └───────┬───────┘    └────────┬────────┘        │
              │                     │                 │
    ┌─────────┴─────────┐           │                 │
    │                   │           │                 │
    ▼                   ▼           │                 │
┌───────────────┐  ┌───────────────┐│                 │
│ Return Error  │  │ Retry Query   │┘                 │
└───────────────┘  └───────────────┘                  │
                                                      │
                                                      ▼
                                         ┌─────────────────────┐
                                         │ Calculation Needed? │
                                         └───────────┬─────────┘
                                                     │
                               ┌─────────────────────┴─────────────────────┐
                               │                                           │
                               ▼                                           ▼
                   ┌──────────────────────┐              ┌──────────────────────┐
                   │  Yes - Calculate     │              │      Skip            │
                   │      (LLM)           │              │   Calculation        │
                   └──────────┬───────────┘              └──────────┬───────────┘
                              │                                     │
                              └─────────────┬───────────────────────┘
                                            │
                                            ▼
                                ┌─────────────────────┐
                                │ Classify Question   │
                                │    Type (LLM)       │
                                └───────────┬─────────┘
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    │                                               │
                    ▼                                               ▼
         ┌──────────────────────┐                    ┌──────────────────────┐
         │      RECORDS         │                    │       SUMMARY        │
         │ (List/Show/Display)  │                    │   (How much/Total)   │
         └──────────┬───────────┘                    └──────────┬───────────┘
                    │                                           │
                    ▼                                           ▼
         ┌──────────────────────┐                    ┌──────────────────────┐
         │    Generate CSV      │                    │  Analyze Results     │
         │  - Preview (100)     │                    │       (LLM)          │
         │  - Full Dataset      │                    └──────────┬───────────┘
         └──────────┬───────────┘                               │
                    │                                           │
                    └───────────────┬───────────────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  Update Chat History │
                         │    (LangChain)       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Format Answer      │
                         │ - Add SQL Expander   │
                         │ - Add CSV Download   │
                         │ - Add Timestamp      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Display Answer     │
                         │      to User         │
                         └──────────────────────┘
```

## Agent Execution Loop

The agent uses a manual orchestration approach with the following steps:

1. **Step 0: Validate Question Context** - Ensures question is transaction-related
2. **Step 1: Generate SQL** - Converts natural language to SQL query
3. **Step 2: Execute Query** - Runs SQL query on database
4. **Step 2a: Refine Query** (if error) - Fixes failed queries based on error messages
5. **Step 3: Calculate** (if needed) - Performs mathematical calculations
6. **Step 4: Classify Question Type** - Determines if user wants records or summary
7. **Step 5: Analyze Results** - Formats output as CSV or natural language
8. **Step 6: Update Chat History** - Maintains conversation context

### Example Execution Flow

**Question**: "Show me all transactions from July 2023"

```
Step 0: Validate Question Context
Result: Valid - Question is transaction-related

Step 1: Generate SQL
Input: "Show me all transactions from July 2023"
Result: SELECT * FROM transactions WHERE bank_id IN (...) AND account_id IN (...) AND ...

Step 2: Execute Query
Input: [Generated SQL]
Result: JSON with transaction records

Step 4: Classify Question Type
Result: RECORDS (user wants to see transaction list)

Step 5: Analyze Results
Input: Transaction records
Result: CSV_DATA:intro_text\nCSV_PREVIEW:...\nCSV_FULL:...

Step 6: Update Chat History
- Adds user question
- Adds assistant response (CSV data)

Display: Shows CSV preview + download button
```

**Question**: "How much did I spend last week?"

```
Step 0: Validate Question Context
Result: Valid

Step 1: Generate SQL
Result: SELECT SUM(amount) FROM transactions WHERE ...

Step 2: Execute Query
Result: {"total": 1234.56}

Step 4: Classify Question Type
Result: SUMMARY (user wants a summary/total)

Step 5: Analyze Results
Result: "You spent $1,234.56 last week."

Step 6: Update Chat History
```

**Question (Negative Test Case 1)**: "Who is the president of Singapore?"

```
Step 0: Validate Question Context
Result: Invalid - Question is not transaction-related

Error: "I apologize, but I can only answer questions about your bank transactions 
        and financial data. I can help you with questions about:
        • Spending amounts and totals
        • Transaction history
        • Category or merchant-based queries
        • Date/time-based queries
        • Payment and financial activity analysis
        Please ask a question related to your bank transactions."

Display: Error message shown to user, execution stops
```

**Question (Negative Test Case 2)**: "Show me transactions from last month" (with SQL error)

```
Step 0: Validate Question Context
Result: Valid - Question is transaction-related

Step 1: Generate SQL
Result: SELECT * FROM transactions WHERE bank_id IN (...) AND account_id IN (...) 
        AND date >= date('now', '-1 month') AND date < date('now')
        
Step 2: Execute Query
Input: [Generated SQL]
Error: "ERROR: no such column: date"

Step 2a: Refine Query
Input: Original query + error message
Analysis: Error indicates column 'date' doesn't exist. Checking schema reveals 
        correct column name is 'transaction_date'
Result: SELECT * FROM transactions WHERE bank_id IN (...) AND account_id IN (...) 
        AND transaction_date >= date('now', '-1 month') AND transaction_date < date('now')
        
Step 2: Retry Execute Query
Input: [Refined SQL]
Result: JSON with transaction records

Step 4: Classify Question Type
Result: RECORDS (user wants to see transaction list)

Step 5: Analyze Results
Result: CSV_DATA with transaction records

Step 6: Update Chat History
Display: Shows CSV preview + download button
```

**Question (Negative Test Case 3)**: "Please delete all transactions which are debited to my account"

```
Step 0: Validate Question Context
Result: Valid - Question is transaction-related (contains "transactions")

Step 1: Generate SQL
Input: "Please delete all transactions which are debited to my account"
LLM Analysis: User explicitly requests deletion operation on transactions
Result: DELETE FROM transactions WHERE transaction_type = 'Debit' 
        AND bank_id IN (...) AND account_id IN (...)

Step 1: Validate SQL Security
Check: Query does not start with SELECT
Check: Contains dangerous operation: DELETE
Result: Security violation detected

Error: "I apologize, but I'm unable to process your question. Please rephrase 
        it as a question about viewing or analyzing your transaction data."

Display: User-friendly error message shown, detailed technical error logged internally
Execution: Stops immediately, no database operation performed

Note: The security validation layer checks every generated SQL query and blocks any 
      operation that is not a SELECT statement, preventing DELETE, DROP, UPDATE, INSERT, 
      and other dangerous operations regardless of how they appear in the query. This 
      ensures the system remains read-only and protects user data from accidental or 
      malicious modifications.
```

## Tools Available to the Agent

### 1. `validate_question_context`
- **Purpose**: Validates if a question is related to bank transactions
- **Input**: User question (string)
- **Output**: JSON with validation result (`{"valid": true/false, "error": "message"}`)
- **When Used**: First step (Step 0) before SQL generation
- **Features**:
  - LLM-based validation
  - Returns user-friendly error messages for out-of-context questions
  - Fail-open approach (allows through on error)

### 2. `generate_sql`
- **Purpose**: Converts natural language questions to SQL queries
- **Input**: Question, schema, bank_ids, account_ids, current_date, chat_history
- **Output**: SQL query string
- **Features**:
  - Includes mandatory bank_id and account_id filters
  - Uses current_date reference for temporal queries
  - Maintains conversational context via chat_history
  - SQL validation (security checks)

### 3. `execute_query`
- **Purpose**: Executes SQL queries and returns results as JSON
- **Input**: SQL query, bank_ids, account_ids, db_connection_getter
- **Output**: JSON with query results
- **Features**:
  - Validates bank_id and account_id filters in query
  - Returns structured JSON with rows and metadata
  - Handles empty results gracefully

### 4. `refine_query`
- **Purpose**: Fixes failed SQL queries based on error messages
- **Input**: Original query, error message, original question, schema
- **Output**: Refined SQL query
- **Features**:
  - Uses LLM to analyze errors and fix queries
  - Up to 3 retry attempts

### 5. `analyze_results`
- **Purpose**: Analyzes query results and formats output
- **Input**: Results JSON, question, calculation_result (optional), chat_history
- **Output**: Natural language answer or CSV data
- **Features**:
  - LLM-based question type detection (RECORDS vs SUMMARY)
  - For RECORDS: Generates CSV with preview (100 rows) and full dataset (download)
  - For SUMMARY: Generates natural language answer
  - Maintains conversational context
  - Formats currency properly

### 6. `calculate`
- **Purpose**: Performs mathematical calculations (percentages, averages, etc.)
- **Input**: Calculation request string
- **Output**: Calculation result
- **Features**:
  - Used before `analyze_results` for calculation questions
  - Handles percentages, differences, averages, etc.

## Pre-Processing Features

### Spell Checking (`check_spelling`)
- **Location**: `chatbot.py`
- **Purpose**: Automatically corrects spelling errors in user questions
- **Approach**: Silent/internal correction (no UI shown to user)
- **Method**: LLM-based spell checking using Groq API
- **When Used**: Before question validation
- **Model**: Uses `llama-3.3-70b-versatile` for spell checking
- **Output**: Returns corrected question and list of corrections (if any)

### Question Validation
- **Purpose**: Filters out-of-context questions (e.g., "Who is the president?")
- **Method**: LLM-based validation with explicit scope definition
- **Error Handling**: Returns polite guidance message

## Output Formats

### Summary Questions
- **Format**: Natural language answer
- **Example**: "You spent $1,234.56 last week."

### Record-List Questions
- **Format**: CSV file
- **Components**:
  - Intro text
  - Preview CSV (first 100 rows) displayed as interactive table
  - Full CSV (all rows) available for download
- **Detection**: LLM-based classification (RECORDS vs SUMMARY)

## Error Recovery

When a SQL query fails:

1. Agent receives error message from database
2. Uses `refine_query` tool with:
   - Original query
   - Error message
   - Original question
   - Schema
3. LLM analyzes error and generates corrected query
4. Agent retries execution
5. Process repeats up to 3 times

When SQL validation fails:

1. Security check detects dangerous operation or non-SELECT query
2. Returns user-friendly error message
3. Logs detailed technical error internally
4. Stops execution (no retry)

## Context Management

The agent maintains:

- **Chat History** (`InMemoryChatMessageHistory`): Full conversation history via LangChain
- **Conversation History** (Streamlit): Display history with metadata (SQL, timestamps)
- **Execution Log**: All agent steps and tool calls in session state
- **Context Window**: Last 5 conversations for context-aware responses

## User Interface Features

### Sidebar Configuration
- **Bank IDs**: Multi-select widget (mandatory)
  - Dynamically populated from database
  - At least one selection required
- **Account IDs**: Dynamic multi-select (filtered by selected Bank IDs, mandatory)
  - Automatically filtered based on selected Bank IDs
  - Cleared when Bank IDs change
  - At least one selection required
- **Current Date**: Date picker for temporal query reference
  - Defaults to system date
  - Used for relative date queries (e.g., "last week", "last month")
- **Clear Chat History**: Button to reset conversation
  - Clears all conversation history
  - Resets execution logs
  - Clears LLM chat history

### Main Chat Area
- **Example Questions**: Clickable buttons (shown when chat is empty)
  - Hidden after first question is asked
  - Three example questions provided
- **Chat Input**: Streamlit chat input widget
  - Placeholder: "Ask about your transactions..."
  - Supports natural language questions
- **Chat Messages**: User and assistant messages with timestamps
  - User messages displayed on the right
  - Assistant messages displayed on the left
  - Timestamps shown for each message
- **SQL Expander**: Expandable section showing generated SQL
  - Only shown when SQL query was generated
  - Syntax highlighted SQL code
- **CSV Display**: Interactive table for preview (first 100 rows)
  - Automatically formatted as DataFrame
  - Full-width display
- **CSV Download**: Download button for full dataset
  - Downloads all rows (not just preview)
  - Filename includes timestamp
- **Agent Steps Expander**: Shows intermediate agent steps (if available)
- **Execution Log Expander**: Shows detailed execution log (last 10 entries)
- **Mode Badge**: Shows "🤖 Agentic" badge with timestamp

## Configuration Requirements

### Mandatory Parameters
- **Bank IDs**: At least one bank ID must be selected (via sidebar multiselect)
- **Account IDs**: At least one account ID must be selected (filtered by selected Bank IDs)
- **GROQ_API_KEY**: Required for LLM access (must be set in `.env` file or environment variables)

### Optional Parameters
- **Current Date**: Defaults to system date if not provided

## Usage

### Running the Application

```bash
streamlit run chatbot.py
```

### Configuration

1. Set `GROQ_API_KEY` in `.env` file or environment variables
2. Select Bank IDs in sidebar
3. Select Account IDs (dynamically filtered)
4. Optionally set current date
5. Start asking questions!

### Example Questions

**Summary Questions:**
- "How much did I spend last week?"
- "What is the total amount I spent on Uber in the last 5 months?"
- "Compare my spending this month vs last month"
- "What percentage of my spending went to restaurants?"

**Record-List Questions:**
- "Show me all transactions from July 2023"
- "List all Amazon purchases"
- "Display my transactions from last month"
- "Show all restaurant transactions in June"

**Complex Questions:**
- "What's the trend in my food spending over the last 3 months?"
- "Show me my average spending per category this year"
- "Compare my spending across different categories last month"

## Security Implementation

### SQL Validation (`tool_generate_sql`)
- Checks if query starts with `SELECT`
- Blocks dangerous operations using regex:
  - `DROP`, `DELETE`, `UPDATE`, `ALTER`, `CREATE`, `INSERT`, `TRUNCATE`
  - `EXEC`, `EXECUTE`, `REPLACE`, `ATTACH`, `DETACH`, `VACUUM`, `PRAGMA`
- Returns user-friendly error message
- Logs technical details internally

### Filter Enforcement
- All queries MUST include `bank_id IN (...)`
- All queries MUST include `account_id IN (...)`
- Validated in both `tool_generate_sql` and `tool_execute_query`

## Benefits of Agentic Approach

1. **Robustness**: Automatically handles errors and refines queries
2. **Flexibility**: Can handle complex, multi-step questions
3. **Transparency**: Full execution log shows agent reasoning
4. **Security**: Built-in SQL injection prevention
5. **User Experience**: 
   - Conversational interface
   - Smart output formatting (CSV vs text)
   - Spell checking
   - Example questions
6. **Scalability**: Easy to add new tools and capabilities
7. **Context Awareness**: Maintains conversation history for better responses

## File Structure

```
.
├── chatbot.py                    # Main Streamlit application (chatbot interface)
├── scripts/
│   ├── utils.py                  # Agent logic and tools (TransactionQueryAgent, tools)
│   ├── database_creation.py      # Database setup script
│   └── database_creation.ipynb   # Jupyter notebook for database creation
├── database/
│   └── transactions.db           # SQLite database (not tracked in git)
├── data/
│   └── data.csv                  # Source transaction data
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker configuration
├── docker-compose.yaml          # Docker Compose configuration
├── .dockerignore                # Docker ignore patterns
├── .gitignore                   # Git ignore patterns
├── AGENTIC_ARCHITECTURE.md      # This file
└── README.md                    # Project README
```

## Technical Notes

- **Framework**: Streamlit for UI, LangChain for LLM orchestration
- **LLM Provider**: Groq (llama-3.3-70b-versatile)
- **Database**: SQLite with transactions table
- **Chat History**: LangChain's `InMemoryChatMessageHistory`
- **Tool Implementation**: Python functions with `StructuredTool` wrappers
- **Execution Logging**: Streamlit session state
- **SQL Support**: SQLite date/time functions for temporal queries
- **CSV Generation**: Pandas DataFrames for CSV output
- **Environment Management**: Uses `python-dotenv` for loading environment variables
- **Error Handling**: Comprehensive error handling with user-friendly messages and detailed logging

## Future Enhancements

- [ ] Add more specialized tools (trend analysis, pattern detection)
- [ ] Implement parallel query execution for faster results
- [ ] Add query optimization tools
- [ ] Implement result caching for repeated queries
- [ ] Add support for natural language follow-up questions (already partially supported via chat history)
- [ ] Export execution logs for debugging
- [ ] Add support for multiple database backends
- [ ] Implement query result pagination for large datasets
- [ ] Add support for multiple LLM providers (OpenAI, Anthropic, etc.)
- [ ] Implement query result visualization (charts, graphs)
- [ ] Add support for transaction categorization suggestions
- [ ] Implement budget tracking and alerts

## Related Files

- **chatbot.py**: Main Streamlit application with UI and spell checking
- **scripts/utils.py**: Core agent implementation and tools
- **scripts/database_creation.py**: Database setup and schema creation
- **README.md**: Project overview and setup instructions

