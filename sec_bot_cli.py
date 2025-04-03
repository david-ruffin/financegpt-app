import sys
import os
import re # Import regex
import argparse # Import argparse
from dotenv import load_dotenv
import json # Import standard json library
import requests  # Import requests
from langchain_google_genai import ChatGoogleGenerativeAI # Re-import Google LLM
from langchain_openai import ChatOpenAI  # Use ChatOpenAI for Octagon
from langchain_core.messages import HumanMessage
from langchain_core.exceptions import OutputParserException # Import specific exceptions
import openai # Import openai for APIError
from langchain.agents import AgentExecutor, create_tool_calling_agent # Use create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder # Import prompt components
from langchain_core.tools import Tool # Import BaseTool for custom tools
from langchain.memory import ConversationBufferMemory # Import memory
from openai import OpenAI, APIError # Import new OpenAI client and specific error

# Load environment variables from .env file
load_dotenv()

def initialize_google_llm():
    """Initialize the Google Generative AI LLM client for the agent."""
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found.", file=sys.stderr)
        sys.exit(1)
    try:
        # Ensure temperature is appropriate for the agent's reasoning task
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", google_api_key=google_api_key, temperature=0.2)
        print("Google LLM (Agent Brain) Initialized successfully.")
        return llm
    except Exception as e:
        print(f"Error initializing Google LLM: {e}", file=sys.stderr)
        sys.exit(1)

def run_octagon_agent_with_sources(model_name: str, prompt: str) -> str:
    """
    Calls the Octagon API using the responses endpoint to get an answer
    and source annotations.
    """
    octagon_api_key = os.getenv("OCTAGON_API_KEY")
    # Use the base URL specified in the responses.create documentation
    octagon_base_url = os.getenv("OCTAGON_API_BASE_URL", "https://api-gateway.octagonagents.com/v1")
    error_message = f"Error executing {model_name}"

    if not octagon_api_key:
        print(f"Error: OCTAGON_API_KEY not found for tool {model_name}.", file=sys.stderr)
        return f"{error_message}: Missing API key."

    try:
        # Initialize the OpenAI client pointing to Octagon
        client = OpenAI(
            api_key=octagon_api_key,
            base_url=octagon_base_url
        )

        print(f"\n--- Calling Octagon Tool: {model_name} ---")
        print(f"Prompt: {prompt}")

        # Define generic instructions based on likely tool purpose
        # These could be more specific if needed, but let's start simple.
        tool_instructions = "Analyze the provided input and return the relevant information with source citations."
        if "sec" in model_name:
            tool_instructions = "Analyze SEC filings based on the input and extract requested data with source citations."
        elif "transcript" in model_name:
            tool_instructions = "Analyze earnings call transcripts based on the input and extract requested information with source citations."
        # Add more specific instructions for other tools if desired

        response = client.responses.create(
            model=model_name,
            instructions=tool_instructions, # Add the required instructions field
            input=prompt
        )
        print(f"Raw Octagon Response: {response}") # Log raw response for debugging

        # Extract the analysis text
        if response.output and response.output[0].content:
            analysis_text = response.output[0].content[0].text
        else:
            analysis_text = "No analysis text found in the response."

        # Extract and format annotations
        sources_text = "\n\nSOURCES:"
        annotations = response.output[0].content[0].annotations if response.output and response.output[0].content else []

        if annotations:
            for annotation in annotations:
                # Ensure all expected fields exist
                order = getattr(annotation, 'order', '?')
                name = getattr(annotation, 'name', 'Unknown Source')
                url = getattr(annotation, 'url', 'No URL Provided')
                sources_text += f"\n{order}. {name}: {url}"
        else:
            sources_text += "\nNo sources provided by the agent."

        print(f"--- Octagon Tool Result ---")
        print(f"Analysis: {analysis_text}")
        print(f"Sources Raw: {annotations}")
        print(f"Formatted Sources: {sources_text.strip()}")
        print(f"---------------------------")

        # -- Debugging Print --
        print(f"DEBUG: analysis_text before return:\n---\n{analysis_text}\n---")
        print(f"DEBUG: sources_text before return:\n---\n{sources_text}\n---")
        # -- End Debugging Print --

        # Combine analysis and sources for the final output string
        return analysis_text + sources_text

    except APIError as e:
        # Handle specific API errors (like auth, rate limits)
        print(f"\nAPI Error in {model_name}: {e}", file=sys.stderr)
        error_detail = f"Status Code: {e.status_code}, Body: {e.body}" if hasattr(e, 'status_code') else str(e)
        return f"{error_message}: API Error - {error_detail}"
    except Exception as e:
        # Handle other potential errors (network, parsing, etc.)
        print(f"\nUnexpected Error in {model_name}: {e}", file=sys.stderr)
        # Add more context if possible, e.g., print traceback
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"{error_message}: Unexpected error - {e}"

# --- Octagon Tool Definitions --- 

# Define tools using the new function
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

# --- Agent Setup --- 

def create_agent_executor(llm: ChatGoogleGenerativeAI, tools: list, memory: ConversationBufferMemory):
    """Creates the LangChain agent executor with memory."""
    # Define the prompt template
    prompt = ChatPromptTemplate.from_messages([
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
    
    # Create the agent using create_tool_calling_agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        memory=memory,
        verbose=True
    )
    print("LangChain Agent Executor created with Memory.")
    return agent_executor

def get_agent_answer(agent_executor: AgentExecutor, question: str, chat_history: list) -> str:
    """Gets an answer from the LangChain agent executor, including chat history."""
    error_message = "Sorry, I encountered an error processing your request with the agent."
    try:
        # The agent executor should now receive the formatted string (answer + sources)
        # from the tools via run_octagon_agent_with_sources
        response = agent_executor.invoke({
            "input": question,
            "chat_history": chat_history
        })
        # The final output already includes sources if the tool provided them
        return response.get("output", error_message + " (No output found)")
    except OutputParserException as e:
        print(f"\nOutput Parsing Error invoking agent: {e}", file=sys.stderr)
        # Attempt to recover or provide a fallback response
        # Sometimes the raw llm output might be in the exception string
        error_text = str(e)
        if "Got output" in error_text:
             # Try to extract the raw output if parsing failed
             raw_output_match = re.search(r"Got output '(.*?)'", error_text, re.DOTALL)
             if raw_output_match:
                 return "Agent action failed parsing, but here's the raw response: " + raw_output_match.group(1)
        return error_message + f": Output Parsing Error - {e}"
    except APIError as e:
         print(f"\nAPI Error invoking agent (likely LLM): {e}", file=sys.stderr)
         return error_message + f": API Error - {e}"
    except Exception as e:
        print(f"\nUnexpected Error invoking agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return error_message + f": {e}"

def run_interactive_mode(agent_executor: AgentExecutor, memory: ConversationBufferMemory):
    """Runs the CLI in interactive mode with memory."""
    print("Welcome to SEC Bot CLI! Ask me your financial research questions.")
    print("(Using Google Gemini Agent with Octagon Tools and Memory)")
    print("Type 'exit' or 'quit' to end.")
    while True:
        try:
            user_question = input("> ")
            if user_question.lower() in ['exit', 'quit']:
                print("Exiting SEC Bot. Goodbye!")
                break
            if not user_question:
                continue
            print(f"Processing question: '{user_question}'...")
            
            # Get current chat history from memory FOR the invoke call
            current_history = memory.chat_memory.messages
            
            # Invoke the agent, which will use and update memory
            answer = get_agent_answer(agent_executor, user_question, current_history)
            print(f"Bot: {answer}")

        except EOFError:
            # Handle Ctrl+D
            print("\nExiting SEC Bot. Goodbye!")
            break
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("\nExiting SEC Bot. Goodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred during interactive processing: {e}", file=sys.stderr)

def main():
    """Main function to handle argument parsing and run modes."""

    # 1. Define ALL tools first
    ALL_TOOLS = [
        sec_tool,
        transcripts_tool,
        financials_tool,
        stock_data_tool,
        companies_tool,
        funding_tool,
        deals_tool,
        investors_tool,
        debts_tool,
        scraper_tool,
        deep_research_tool
    ]

    # 2. Create the parser and add ALL arguments, including those referencing tools
    parser = argparse.ArgumentParser(description="SEC Bot CLI - Ask questions using Octagon agents. Answers include sources where available.")
    parser.add_argument("-q", "--question", type=str, help="Ask a single question and exit.")
    parser.add_argument("--test-tool", type=str, choices=[t.name for t in ALL_TOOLS], help="Run a specific tool directly with the provided question (for debugging).")

    # 3. Parse arguments ONCE
    args = parser.parse_args()

    # 4. Handle direct tool testing if requested
    if args.test_tool:
        if not args.question:
            print("Error: Please provide a question using -q when using --test-tool.", file=sys.stderr)
            sys.exit(1)

        # Find the selected tool object (ALL_TOOLS is already defined)
        tool_to_test = next((t for t in ALL_TOOLS if t.name == args.test_tool), None)
        if not tool_to_test:
            print(f"Error: Tool '{args.test_tool}' not found.", file=sys.stderr)
            sys.exit(1)

        print(f"\n--- Testing Tool Directly: {args.test_tool} ---")
        print(f"Question: {args.question}")
        try:
            result = tool_to_test.func(args.question)
            print("\n--- Tool Result ---")
            print(result)
            print("-------------------")
        except Exception as e:
            print(f"\nError running tool directly: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(0)

    # 5. Initialize LLM, Memory, Agent if not testing a tool
    print("Initializing SEC Bot with LangChain Agent and Memory...")
    llm = initialize_google_llm()
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    agent_executor = create_agent_executor(llm, ALL_TOOLS, memory)

    # 6. Run appropriate mode
    if args.question:
        # Non-interactive mode
        print(f"Processing question (non-interactive): '{args.question}'...")
        memory.clear()
        answer = get_agent_answer(agent_executor, args.question, [])
        print(f"\nAgent Answer:\n{answer}")
    else:
        # Interactive mode with memory
        run_interactive_mode(agent_executor, memory)

if __name__ == "__main__":
    main() 