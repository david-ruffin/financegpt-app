# SEC Bot CLI

A Command Line Interface (CLI) application leveraging LangChain and specialized Octagon AI agents to answer financial research questions.

## Features

-   **Natural Language Queries:** Ask questions about public/private companies, SEC filings, earnings calls, financials, stock data, funding, deals, investors, debts, or scrape websites.
-   **Intelligent Agent:** Uses Google Gemini (via LangChain) to understand your question and select the appropriate specialized Octagon agent tool.
-   **Comprehensive Tool Access:** Integrates the full suite of Octagon agents:
    -   `octagon_sec_agent`: Public company SEC filings, CIKs, specific sections.
    -   `octagon_transcripts_agent`: Public company earnings call transcripts and commentary.
    -   `octagon_financials_agent`: Public company financial statement analysis and ratio calculations.
    -   `octagon_stock_data_agent`: Public company stock market data, prices, volume, trends.
    -   `octagon_companies_agent`: Private company information (general info, financials, employees, competitors).
    -   `octagon_funding_agent`: Private company funding rounds, investors, valuations.
    -   `octagon_deals_agent`: Public and private company M&A and IPO transactions.
    -   `octagon_investors_agent`: Investor firm details, criteria, activities.
    -   `octagon_debts_agent`: Private debt activities, borrowers, lenders.
    -   `octagon_scraper_agent`: Extract structured data from specific webpage URLs.
    -   `octagon_deep_research_agent`: Complex/broad research questions aggregating multiple sources.
-   **Direct API Integration:** Communicates directly with the Octagon API (`api.octagonagents.com`) using an OpenAI-compatible interface.
-   **Conversational Memory:** Remembers previous turns in interactive mode for follow-up questions.
-   **Modes:** Supports both interactive chat and single-question non-interactive execution.

## Architecture

-   **Orchestrator LLM:** Google Gemini (`gemini-1.5-pro-latest`) via `langchain-google-genai`.
-   **Agent Framework:** LangChain (`create_tool_calling_agent`, `AgentExecutor`).
-   **Tools:** Custom LangChain `Tool` definitions wrapping calls to specific Octagon agent models.
-   **Octagon API Client:** `langchain_openai.ChatOpenAI` configured to point to the Octagon API endpoint and use the Octagon API key.
-   **Memory:** `langchain.memory.ConversationBufferMemory`.
-   **Interface:** Python standard library (`argparse`, `input`, `print`).

## Setup

1.  **Prerequisites:**
    *   Python 3.9+ recommended.
    *   Access to Google AI API key.
    *   Access to Octagon API key (Sign up at [Octagon AI](https://app.octagonai.co/signup) and generate a key in Settings -> API Keys).

2.  **Clone the Repository (if applicable):**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

3.  **Create Virtual Environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Create `.env` File:**
    *   Create a file named `.env` in the project root directory.
    *   Add your API keys:
        ```dotenv
        GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
        OCTAGON_API_KEY="YOUR_OCTAGON_API_KEY"
        # Optional: Override default Octagon base URL if needed
        # OCTAGON_API_BASE_URL="https://api.octagonagents.com/v1" 
        ```
    *   **IMPORTANT:** Add `.env` to your `.gitignore` file to avoid committing keys.

## Usage

Ensure your virtual environment is activated (`source .venv/bin/activate`).

**Interactive Mode (with Memory):**

```bash
python sec_bot_cli.py
```

Follow the prompts. Ask your questions. Type `exit` or `quit` to end.

**Non-Interactive Mode (Single Question, No Memory):**

```bash
python sec_bot_cli.py -q "Your question here"
```

Example:
```bash
python sec_bot_cli.py -q "What did Microsoft CEO say about AI in the Q4 2023 earnings call?"
python sec_bot_cli.py -q "What is the CIK for Apple Inc?"
python sec_bot_cli.py -q "What is the employee count for Anthropic (anthropic.com)?"
```

## Web API & Frontend Integration (Planned)

While the current tool is a CLI, the next stage involves transforming it into a web service to support the provided frontend application (`project/` directory).

1.  **FastAPI Backend:** The core logic from `sec_bot_cli.py` will be refactored into a Python FastAPI web server (`api_server.py`). This server will expose an endpoint (e.g., `/ask`) to receive questions.
2.  **Frontend Connection:** The frontend application (in `project/src/`) will be updated to send user queries to the backend API's `/ask` endpoint.
3.  **Data Flow:** The frontend sends the question (and chat history) as JSON; the FastAPI backend processes it using the LangChain agent and Octagon tools; the backend returns the answer/sources as JSON to the frontend for display.
4.  **Local Testing:** Both the FastAPI server and the frontend development server (e.g., using `npm run dev` in the `project` directory) will be run concurrently for local integration testing.

## Testing UI with Mock Data (Local Development Only)

To test frontend UI changes (like layout, styling, or how responses are displayed) without hitting the real, potentially costly Octagon APIs, you can temporarily modify the backend server *locally*.

1.  **Run Backend Locally:** Start the FastAPI server using Uvicorn with the `--reload` flag:
    ```bash
    # Ensure .venv is active
    uvicorn api_server:app --reload --port 8000
    ```
2.  **Temporarily Modify Backend:** Open `api_server.py`. Find the `@app.post("/ask")` function (`ask_agent`). Add temporary code at the very beginning of this function to immediately return a hardcoded mock `AskResponse` object. For example:
    ```python
    @app.post("/ask", response_model=AskResponse)
    async def ask_agent(request: AskRequest):
        # --- TEMPORARY MOCK FOR LOCAL UI TESTING ---
        print("!!! RETURNING MOCK DATA FROM /ask !!!")
        mock_output = "This is a **mock** response for local UI test. URL: https://example.com/fake"
        return AskResponse(output=mock_output)
        # --- END TEMPORARY MOCK ---

        # Original agent logic starts below this point...
        if agent_executor is None:
           # ... rest of function
    ```
3.  **Save Backend File:** Uvicorn (because of `--reload`) will automatically detect the change and restart the server with the mock logic active.
4.  **Run Frontend Dev Server:** In a separate terminal:
    ```bash
    cd project
    npm run dev -- --port 8003 # Or your preferred port
    ```
5.  **Test UI:** Open `http://localhost:8003` in your browser. All requests will now receive the mock data from your temporarily modified local backend.
6.  **IMPORTANT:** **Do NOT commit** the temporary changes made to `api_server.py`. When finished testing, remove the temporary mock code from the `/ask` endpoint and save the file again. The Docker image for deployment should *always* contain the original, unmodified `/ask` endpoint logic.

## Project Files

-   `sec_bot_cli.py`: Main application script.
-   `requirements.txt`: Project dependencies.
-   `.env`: Stores API keys (needs to be created).
-   `@roadmap.txt`: Development plan and tasks.
-   `@history.txt`: Log of development changes.
-   `README.md`: This file.

## Future Enhancements (from Roadmap)

-   Address `flake8` linting issues in `sec_bot_cli.py`.
-   Refine tool descriptions/prompts for improved agent accuracy.
-   Address `LangChainDeprecationWarning` for memory initialization (if applicable after refactor).
-   Develop **FastAPI backend** (`api_server.py`) to serve agent logic.
-   **Integrate existing frontend** (`project/`) with the FastAPI backend.
-   Containerize the application (backend + frontend build).
-   Set up GitHub Actions for CI/CD to Azure Container Apps. 