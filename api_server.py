"""
FastAPI server to handle financial research requests using LangChain and Octagon tools.
"""

import sys
import os
import re # Import regex
import asyncio
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles # Import StaticFiles
from fastapi.responses import FileResponse # To serve index.html
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from dotenv import load_dotenv

# --- LangChain / LLM Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_core.messages import HumanMessage, AIMessage # Import AIMessage
from langchain_core.exceptions import OutputParserException
from openai import OpenAI, APIError # Use new OpenAI client and specific error

# Load environment variables
load_dotenv()

# --- Pydantic Models for Request/Response ---

class ChatMessage(BaseModel):
    """Represents a single message in the chat history.
    Type can be 'user' or 'bot'.
    Timestamp is expected as an ISO format string (or similar) from the frontend.
    """
    type: str = Field(..., pattern="^(user|bot)$") # Add validation
    content: str
    timestamp: str # Kept as string for simplicity, parsing not needed by agent

class AskRequest(BaseModel):
    """Request model for the /ask endpoint."""
    input: str = Field(..., description="The user's question.")
    chat_history: List[ChatMessage] = Field(default_factory=list, description="The previous messages in the conversation.")
    use_mock: bool = Field(False, description="If true, return a mock response instead of calling the agent.")

class AskResponse(BaseModel):
    """Response model for the /ask endpoint."""
    output: str = Field(..., description="The agent's response, potentially including sources.")

# --- Agent Initialization Logic (from sec_bot_cli.py) ---

def initialize_google_llm():
    """Initialize the Google Generative AI LLM client for the agent."""
    google_api_key_raw = os.getenv("GOOGLE_API_KEY")
    if not google_api_key_raw:
        print("FATAL: GOOGLE_API_KEY not found in .env file or environment.", file=sys.stderr)
        raise ValueError("GOOGLE_API_KEY not configured.")
    
    # Strip potential surrounding quotes (single or double)
    google_api_key = google_api_key_raw.strip('"\'')
    
    if not google_api_key: # Check if empty after stripping
        print("FATAL: GOOGLE_API_KEY is empty after stripping quotes.", file=sys.stderr)
        raise ValueError("GOOGLE_API_KEY is effectively empty.")

    try:
        print(f"Attempting to initialize Google LLM with key ending: ...{google_api_key[-4:]}") # Log last 4 chars
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", google_api_key=google_api_key, temperature=0.2)
        print("Google LLM (Agent Brain) Initialized successfully.")
        return llm
    except Exception as e:
        print(f"Error initializing Google LLM: {e}", file=sys.stderr)
        raise RuntimeError(f"Could not initialize Google LLM: {e}")

def run_octagon_agent_with_sources(model_name: str, prompt: str) -> str:
    """
    Calls the Octagon API using the responses endpoint to get an answer
    and source annotations.
    """
    octagon_api_key_raw = os.getenv("OCTAGON_API_KEY")
    octagon_base_url = os.getenv("OCTAGON_API_BASE_URL", "https://api-gateway.octagonagents.com/v1")
    error_message = f"Error executing Octagon tool {model_name}"

    if not octagon_api_key_raw:
        print(f"Error: OCTAGON_API_KEY not found for tool {model_name}.", file=sys.stderr)
        return f"{error_message}: The OCTAGON_API_KEY is not configured on the server."
    
    # Strip potential surrounding quotes
    octagon_api_key = octagon_api_key_raw.strip('"\'')

    if not octagon_api_key: # Check if empty after stripping
        print(f"Error: OCTAGON_API_KEY is empty after stripping quotes for tool {model_name}.", file=sys.stderr)
        return f"{error_message}: The OCTAGON_API_KEY is effectively empty."

    try:
        # Use the stripped key
        client = OpenAI(api_key=octagon_api_key, base_url=octagon_base_url)
        print(f"\n--- Calling Octagon Tool: {model_name} (Key ending: ...{octagon_api_key[-4:]}) ---")
        print(f"Prompt: {prompt}")

        tool_instructions = "Analyze the provided input and return the relevant information with source citations."
        if "sec" in model_name:
            tool_instructions = "Analyze SEC filings based on the input and extract requested data with source citations."
        elif "transcript" in model_name:
            tool_instructions = "Analyze earnings call transcripts based on the input and extract requested information with source citations."
        # Add more specific instructions for other tools if desired

        response = client.responses.create(
            model=model_name,
            instructions=tool_instructions,
            input=prompt
        )
        # print(f"Raw Octagon Response: {response}") # Verbose logging

        if response.output and response.output[0].content:
            analysis_text = response.output[0].content[0].text
        else:
            analysis_text = "No analysis text found in the response."

        sources_text = "\n\nSOURCES:"
        annotations = response.output[0].content[0].annotations if response.output and response.output[0].content else []

        if annotations:
            for annotation in annotations:
                order = getattr(annotation, 'order', '?')
                name = getattr(annotation, 'name', 'Unknown Source')
                url = getattr(annotation, 'url', 'No URL Provided')
                sources_text += f"\n{order}. {name}: {url}"
        else:
            sources_text += "\nNo sources provided by the agent."

        print(f"--- Octagon Tool ({model_name}) Result --- A:{len(analysis_text)} S:{len(sources_text)}")
        # print(f"Analysis: {analysis_text}") # Less verbose logging
        # print(f"Formatted Sources: {sources_text.strip()}")
        print(f"---------------------------")

        return analysis_text + sources_text

    except APIError as e:
        print(f"\nOctagon API Error in {model_name}: {e}", file=sys.stderr)
        error_detail = f"Status Code: {e.status_code}, Response Body: {e.body}" if hasattr(e, 'status_code') else str(e)
        # Return a user-facing error string
        return f"{error_message}: API Error - {error_detail}. Please check server logs."
    except Exception as e:
        print(f"\nUnexpected Error in Octagon tool {model_name}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        # Return a user-facing error string
        return f"{error_message}: Unexpected error occurred - {e}. Please check server logs."

# --- Octagon Tool Definitions ---
# (Copied directly from sec_bot_cli.py)
sec_tool = Tool(
    name="octagon_sec_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-sec-agent", prompt),
    description="Use ONLY for questions about **PUBLIC** company SEC filings (like 10-K, 10-Q, 8-K), financial data reported IN filings, risk factors, CIK numbers, filing dates, or specific sections FROM filings. Returns answer and source links. Input requires the PUBLIC company name/ticker. Example: 'What is the CIK for Apple Inc?' or 'What were MSFT risk factors in their 2023 10-K?'."
)
transcripts_tool = Tool(
    name="octagon_transcripts_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-transcripts-agent", prompt),
    description="Use ONLY for questions about **PUBLIC** company earnings call transcripts or investor commentary. Ask about executive statements, financial guidance, analyst questions, or topics discussed during calls. Returns answer and source links. Input requires the company name and call period. Example: 'What did Microsoft CEO say about AI in the Q4 2023 earnings call?'."
)
financials_tool = Tool(
    name="octagon_financials_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-financials-agent", prompt),
    description="Use ONLY for financial statement analysis, calculating specific financial metrics, or comparing ratios for **PUBLIC** companies based on reported financials. Returns answer and source links. Input requires the company, metric/ratio, and time period. Example: 'Compare the gross margins of Apple and Microsoft for fiscal year 2023'."
)
stock_data_tool = Tool(
    name="octagon_stock_data_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-stock-data-agent", prompt),
    description="Use ONLY for questions about **PUBLIC** company stock market data. Ask about stock price movements, trading volumes, market trends, valuation metrics, technical indicators, or benchmark comparisons. Returns answer and source links. Input requires the company/ticker and time period. Example: 'How has NVDA stock performed compared to the S&P 500 over the last 6 months?'."
)
companies_tool = Tool(
    name="octagon_companies_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-companies-agent", prompt),
    description="Use ONLY for questions about **PRIVATE** company information (companies NOT listed on stock exchanges), like general info, financials, employee trends, sector analysis, or competitors. Returns answer and potentially source links (if applicable). Providing the website URL improves results. Example: 'What is the employee count for Anthropic (anthropic.com)?' DO NOT use for public companies like Microsoft or Apple."
)
funding_tool = Tool(
    name="octagon_funding_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-funding-agent", prompt),
    description="Use ONLY for questions about **PRIVATE** company startup funding rounds, investors, valuations, and investment trends. Returns answer and potentially source links (if applicable). Providing the website URL improves results. Example: 'What was OpenAI (openai.com) latest funding round size?'."
)
deals_tool = Tool(
    name="octagon_deals_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-deals-agent", prompt),
    description="Use this tool to research M&A (mergers and acquisitions) and IPO (initial public offering) transactions, prices, and valuations for both **PUBLIC and PRIVATE** companies. Returns answer and potentially source links (if applicable). Specify companies involved. Example: 'What was the acquisition price when Microsoft acquired GitHub?'."
)
investors_tool = Tool(
    name="octagon_investors_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-investors-agent", prompt),
    description="Use this tool to look up information about specific **INVESTORS** (VC firms, PE firms, etc.), their investment criteria, activities, or check sizes. Returns answer and potentially source links (if applicable). Providing the website URL improves results. Example: 'What is the typical check size for QED Investors (qedinvestors.com)?'"
)
debts_tool = Tool(
    name="octagon_debts_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-debts-agent", prompt),
    description="Use this tool to analyze **PRIVATE DEBT** activities, borrowers, and lenders. Returns answer and potentially source links (if applicable). Example: 'List debt activities for borrower American Tower' or 'Compile debt activities for lender ING Group in Q4 2024'."
)
scraper_tool = Tool(
    name="octagon_scraper_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-scraper-agent", prompt),
    description="Use this tool ONLY to extract structured data fields or tables from a **SPECIFIC WEBPAGE URL**. Returns extracted data and potentially source link (the URL provided). Clearly state what info to extract and provide the full URL. Example: 'Extract property prices from zillow.com/san-francisco-ca/'. DO NOT use for general questions."
)
deep_research_tool = Tool(
    name="octagon_deep_research_agent",
    func=lambda prompt: run_octagon_agent_with_sources("octagon-deep-research-agent", prompt),
    description="Use this tool for **COMPLEX or BROAD** research questions requiring aggregation from multiple sources or analysis of trends/impacts. Returns answer and source links. Use other tools first if the question fits their specific purpose. Example: 'Research the financial impact of Apple privacy changes on digital advertising companies'."
)

ALL_TOOLS = [
    sec_tool, transcripts_tool, financials_tool, stock_data_tool,
    companies_tool, funding_tool, deals_tool, investors_tool,
    debts_tool, scraper_tool, deep_research_tool
]

# --- Global Agent Setup ---
# Initialize components globally on server start
agent_executor = None
try:
    llm = initialize_google_llm()
    # Define the prompt template (moved here for global scope)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a specialized financial research assistant using Octagon tools. \
Your ONLY task is to determine the single best Octagon tool for the user's query and execute it. \
**The exact, complete, and unmodified string returned by that tool IS THE FINAL ANSWER.** \
**DO NOT summarize, rephrase, interpret, or add any text to the tool's output.** \
Return ONLY what the tool provides, including the full 'SOURCES:' section if present. \
Do not use your own knowledge. If a query is outside the scope of the tools (e.g., 'hello'), state that you can only answer financial/company questions."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    # Create the agent
    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt_template)
    # Create the agent executor (without memory for stateless API calls)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True # Set to False in production?
    )
    print("LangChain Agent Executor created successfully (stateless).")
except (ValueError, RuntimeError) as e:
    print(f"FATAL: Agent Executor could not be initialized: {e}", file=sys.stderr)
    # agent_executor remains None, will cause 503 error on requests

# --- FastAPI App Initialization ---

app = FastAPI(
    title="SEC Bot API",
    description="API interface for the SEC Bot financial research agent.",
    version="0.1.0"
)

# --- API Endpoints ---

@app.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    """
    Receives a question and chat history, passes it to the LangChain agent,
    or returns a mock response if use_mock is true.
    """
    # --- Mock Response Logic ---
    if request.use_mock:
        print(">>> Mock flag detected. Returning mock response. <<<")
        mock_output = "This is a **mock** response for testing UI rendering. It includes a fake source link: https://example.com/mock-source"
        return AskResponse(output=mock_output)
    # --- End Mock Response Logic ---

    if agent_executor is None:
        print("Error: /ask called but agent_executor is not initialized.", file=sys.stderr)
        raise HTTPException(status_code=503, detail="Agent not initialized. Check server logs for configuration errors (e.g., API keys).")

    print(f"Received request for /ask: '{request.input}' with {len(request.chat_history)} history messages.")

    # Convert incoming chat history to LangChain message objects
    formatted_history = []
    for msg in request.chat_history:
        if msg.type == 'user':
            formatted_history.append(HumanMessage(content=msg.content))
        elif msg.type == 'bot':
            formatted_history.append(AIMessage(content=msg.content))
        # else: Malformed type handled by Pydantic validation

    try:
        # Invoke the agent executor
        # Use asyncio.to_thread for blocking LangChain calls in async FastAPI
        response = await asyncio.to_thread(
            agent_executor.invoke, # Pass the method itself
             {
                 "input": request.input,
                 "chat_history": formatted_history
             }
        )
        agent_output = response.get("output")
        if agent_output is None:
             print("Error: Agent response missing 'output' key.", file=sys.stderr)
             raise HTTPException(status_code=500, detail="Agent failed to produce a valid output.")

        print(f"Agent invocation successful. Output length: {len(agent_output)}")
        return AskResponse(output=agent_output)

    except OutputParserException as e:
        print(f"\nOutput Parsing Error invoking agent: {e}", file=sys.stderr)
        error_text = str(e)
        if "Got output" in error_text:
             raw_output_match = re.search(r"Got output '(.*)'", error_text, re.DOTALL)
             if raw_output_match:
                  # Return the raw output if parsing failed but output exists
                  return AskResponse(output="Agent action failed parsing, but here's the raw response: " + raw_output_match.group(1))
        raise HTTPException(status_code=500, detail=f"Agent Output Parsing Error: {e}")
    except APIError as e: # Catch potential OpenAI/LLM API errors during invoke
         print(f"\nAPI Error during agent invocation: {e}", file=sys.stderr)
         raise HTTPException(status_code=502, detail=f"Upstream API Error (LLM/Agent): {e}")
    except Exception as e:
        print(f"\nUnexpected Error invoking agent: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Internal server error during agent execution: {e}")

# --- Static Files Hosting ---
# Mount the static files directory (containing the built React app)
# IMPORTANT: This path must match the destination in the Dockerfile
app.mount("/assets", StaticFiles(directory="/app/static/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """Serves the main index.html for any other routes, enabling client-side routing."""
    # Check if the agent is initialized, return 503 if not, preventing app load
    if agent_executor is None:
        print("Error: / requested but agent_executor is not initialized.", file=sys.stderr)
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Cannot serve application. Check server logs."
        )
    print(f"Serving index.html for path: {full_path}")
    return FileResponse("/app/static/index.html")

# --- Run instruction (for local development / container) ---
# uvicorn api_server:app --host 0.0.0.0 --port 8000
# Note: Ensure .env file with GOOGLE_API_KEY and OCTAGON_API_KEY is present for local dev
# In container, keys should be passed as environment variables.

# Add imports for mocked response
import asyncio 