# Transaction Query Assistant

A sophisticated Streamlit-based chatbot application that uses agentic AI to answer natural language questions about bank transactions. Built with LangChain and Groq's LLM, this application provides an intelligent, conversational interface for querying financial transaction data.

Deployed Web Application URL: https://ayushgurtu-moneylion-ta-chatbot-zj79k7.streamlit.app/

## 🤖 Features

### Agentic AI Capabilities
- **Multi-Step Reasoning**: Breaks down complex queries into multiple steps
- **Error Recovery**: Automatically refines failed SQL queries based on error messages (up to 3 retries)
- **Tool-Based Architecture**: Uses specialized tools for different tasks
- **Context Awareness**: Maintains conversation history using LangChain's `InMemoryChatMessageHistory`
- **Execution Logging**: Tracks all agent steps for debugging and transparency
- **Question Validation**: Validates if questions are transaction-related before processing
- **Spell Checking**: Automatically corrects spelling errors in user questions
- **Smart Output Formatting**: Automatically detects if user wants records (CSV) or summary (natural language)

### User Interface
- **Modern Chat UI**: Streamlit chatbot interface with chat input and message display
- **Example Questions**: Clickable example questions for user guidance
- **Chat History**: Persistent conversation history with timestamps
- **SQL Visibility**: Expandable SQL queries for transparency
- **CSV Download**: Downloadable CSV files for record-list questions
- **Dynamic Filtering**: Bank IDs and Account IDs are dynamically filtered and validated

### Security
- **SQL Injection Prevention**: Validates SQL queries to ensure they only contain SELECT statements
- **Dangerous Operation Blocking**: Blocks DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, and other dangerous SQL operations
- **User-Friendly Error Messages**: Returns polite error messages for security violations

## 📋 Prerequisites

- Python 3.11 or higher
- Groq API Key ([Get one here](https://console.groq.com/))
- SQLite database with transactions table (see Database Setup)
- Git (for cloning the repository)
- Docker (optional, for containerized deployment)

## 🚀 Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd "MoneyLion TA"
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Set up environment variables

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 6. Set up the database

Ensure you have a SQLite database at `database/transactions.db` with a `transactions` table. You can use the provided scripts to create the database:

```bash
python scripts/database_creation.py
```

Or use the Jupyter notebook:
```bash
jupyter notebook scripts/database_creation.ipynb
```

## 🎯 Usage

### Running the Application

Start the Streamlit application:

```bash
streamlit run chatbot.py
```

The application will open in your browser at `http://localhost:8501`.

**Note**: Make sure you have:
- Created and populated the database (see Installation step 6)
- Set up your `.env` file with `GROQ_API_KEY`
- Activated your virtual environment

### Using the Application

1. **Configure Settings** (Sidebar):
   - Select at least one **Bank ID** (required)
   - Select at least one **Account ID** (required, filtered by selected Bank IDs)
   - Optionally set the **Current Date** for temporal queries

2. **Ask Questions**:
   - Type your question in the chat input
   - Click on example questions to get started
   - View SQL queries in expandable sections
   - Download CSV files for record-list questions

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

**Complex Questions:**
- "What's the trend in my food spending over the last 3 months?"
- "Show me my average spending per category this year"
- "Compare my spending across different categories last month"

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

1. Ensure your `.env` file is set up with `GROQ_API_KEY`

2. Build and run with Docker Compose:

```bash
docker-compose up --build -d
```

The application will be available at `http://localhost:8501`

3. View logs:

```bash
docker-compose logs -f chatbot
```

4. Stop the application:

```bash
docker-compose down
```

### Using Docker directly

1. Build the image:

```bash
docker build -t transaction-query-assistant .
```

2. Run the container:

```bash
docker run -d \
  -p 8501:8501 \
  -v ./database:/app/database \
  -v ./.env:/app/.env:ro \
  -e GROQ_API_KEY=${GROQ_API_KEY} \
  --name transaction-query-assistant \
  transaction-query-assistant
```

## 📁 Project Structure

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
├── AGENTIC_ARCHITECTURE.md      # Detailed architecture documentation
└── README.md                    # This file
```

## 🔧 Configuration

### Environment Variables

- `GROQ_API_KEY` (required): Your Groq API key for LLM access

### Database Schema

The application expects a SQLite database with a `transactions` table. The schema should include columns such as:
- `bank_id` (INTEGER)
- `account_id` (INTEGER)
- `transaction_date` (DATE)
- `amount` (FLOAT)
- `transaction_type` (TEXT)
- `merchant` (TEXT)
- `category` (TEXT)
- And other relevant transaction fields

See `scripts/database_creation.py` for an example schema.

## 🛠️ Dependencies

Core dependencies (see `requirements.txt`):
- `streamlit>=1.28.0` - Web application framework
- `pandas>=2.0.0` - Data manipulation
- `langchain>=0.1.0` - LLM orchestration framework
- `langchain-core>=0.1.0` - Core LangChain components
- `langchain-groq>=0.1.0` - Groq LLM integration
- `python-dotenv>=1.0.0` - Environment variable management
- `sqlalchemy>=2.0.0` - Database toolkit

## 📚 Architecture

This application implements a fully agentic AI architecture for querying bank transactions. The agent uses a tool-based approach with the following capabilities:

1. **Question Validation**: Ensures questions are transaction-related
2. **SQL Generation**: Converts natural language to SQL queries
3. **Query Execution**: Runs SQL queries with security validation
4. **Error Recovery**: Refines failed queries based on error messages
5. **Result Analysis**: Formats output as CSV or natural language
6. **Context Management**: Maintains conversation history

For detailed architecture documentation, see [AGENTIC_ARCHITECTURE.md](AGENTIC_ARCHITECTURE.md).

## 🔍 Key Components

### TransactionQueryAgent
The core agent class located in `scripts/utils.py` that orchestrates the entire query process:
- Validates questions
- Generates and executes SQL queries
- Handles errors and refines queries
- Analyzes results and formats output
- Maintains conversation context

### Tools
The agent uses specialized tools for different tasks:
- `validate_question_context` - Validates question relevance
- `generate_sql` - Converts natural language to SQL
- `execute_query` - Runs SQL queries safely
- `refine_query` - Fixes failed queries
- `analyze_results` - Formats output intelligently
- `calculate` - Performs mathematical operations

## 🔒 Security Features

- **SQL Injection Prevention**: All queries are validated to ensure they only contain SELECT statements
- **Dangerous Operation Blocking**: Blocks DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE operations
- **Filter Enforcement**: All queries must include bank_id and account_id filters
- **User-Friendly Error Messages**: Security violations return polite error messages

## 🐛 Troubleshooting

### Database Not Found
If you see "Database not found" error:
- Ensure `database/transactions.db` exists
- Run `scripts/database_creation.py` to create the database

### API Key Issues
If you see "GROQ_API_KEY Required" error:
- Check that `.env` file exists and contains `GROQ_API_KEY`
- Verify the API key is valid and has sufficient credits
- Ensure the `.env` file is in the root directory of the project

### Port Already in Use
If port 8501 is already in use:
- Change the port in `docker-compose.yaml` or use `streamlit run chatbot.py --server.port 8502`

## 📝 License

This project is part of a take-home assessment for MoneyLion.

## 🤝 Contributing

This is a take-home assessment project. For questions or issues, please contact the project maintainer.

## 📖 Additional Documentation

- [AGENTIC_ARCHITECTURE.md](AGENTIC_ARCHITECTURE.md) - Detailed architecture and implementation documentation

