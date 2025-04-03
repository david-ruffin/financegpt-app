# FinanceGPT Web Application

A web application leveraging LangChain and specialized Octagon AI agents to answer financial research questions via a chat interface. Originally based on a CLI tool (`sec_bot_cli.py`).

## Features

-   **Web Chat Interface:** Provides a user-friendly chat UI (built with React) for asking questions.
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
-   **Cost-Effective UI Testing:** Provides a `/mock` URL path to test the frontend UI with sample data without incurring expensive backend API call costs.
-   **Containerized Deployment:** Packaged using Docker for consistent deployment on Azure App Service.

## Architecture

-   **Frontend:** React (using Vite) located in the `project/` directory.
-   **Backend:** Python FastAPI web server (`api_server.py`) serving the frontend and handling API requests.
-   **Orchestrator LLM:** Google Gemini (`gemini-1.5-pro-latest`) via `langchain-google-genai`.
-   **Agent Framework:** LangChain (`create_tool_calling_agent`, `AgentExecutor`). The API backend handles agent execution statelessly per request.
-   **Tools:** Custom LangChain `Tool` definitions wrapping calls to specific Octagon agent models via their OpenAI-compatible API.
-   **Containerization:** Docker (`Dockerfile`) builds the frontend and packages it with the Python backend.
-   **Deployment:** Hosted on Azure App Service (`https://secv2.azurewebsites.net/`). Container images stored in Azure Container Registry (`crwestus001.azurecr.io`).

## Setup for Local Testing (Docker - Recommended)

This method runs the exact container image that gets deployed, ensuring the most accurate test environment.

1.  **Prerequisites:**
    *   Docker installed and running.
    *   Access to Google AI API key.
    *   Access to Octagon API key (Sign up at [Octagon AI](https://app.octagonai.co/signup) and generate a key in Settings -> API Keys).

2.  **Clone the Repository (if applicable):**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

3.  **Create `.env` File:**
    *   Create a file named `.env` in the project root directory.
    *   Add your API keys:
        ```dotenv
        GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
        OCTAGON_API_KEY="YOUR_OCTAGON_API_KEY"
        # Optional: Override default Octagon base URL if needed
        # OCTAGON_API_BASE_URL="https://api.octagonagents.com/v1"
        ```
    *   **IMPORTANT:** Ensure `.env` is in your `.gitignore` file.

4.  **Build the Docker Image:**
    ```bash
    docker build -t financegpt-app .
    ```

5.  **Run the Docker Container:** (Example maps to local port 8002)
    ```bash
    # Ensure no other service is using port 8002 locally
    docker run --rm -p 8002:8000 --env-file .env financegpt-app
    ```
    *   `--rm`: Removes the container when stopped.
    *   `-p 8002:8000`: Maps port 8002 on your host machine to port 8000 inside the container (where the app listens).
    *   `--env-file .env`: Loads API keys from your `.env` file into the container.

6.  **Access the Application:**
    *   **Live Mode (Real API calls, costs money):** Open `http://localhost:8002/`
    *   **Mock Mode (UI testing, free):** Open `http://localhost:8002/mock`
        *   This mode uses the same UI but displays hardcoded sample data instead of calling the `/ask` API, allowing you to test UI formatting without cost.

## Local Development (Separate Servers - For Rapid Frontend Iteration Only)

This method is useful **only** when you need very fast feedback cycles while actively editing frontend code (React/CSS). It uses the Vite development server's Hot Module Replacement (HMR). **Do not use this for final pre-deployment testing.**

1.  **Setup:** Complete steps 1-3 from the Docker setup above (Prerequisites, Clone, `.env` file).

2.  **Setup Python Environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate # On Windows use `.venv\\Scripts\\activate`
    pip install -r requirements.txt
    ```

3.  **Run Backend Server (Terminal 1):**
    ```bash
    # Ensure virtual env is active
    # Ensure .env file exists in the root
    uvicorn api_server:app --reload --port 8000
    ```

4.  **Run Frontend Server (Terminal 2):**
    ```bash
    # Navigate to the frontend directory
    cd project
    npm install
    npm run dev -- --port 8003 # Runs frontend on port 8003
    ```
    *   **Note:** The Vite dev server (`npm run dev`) needs to be configured to proxy API requests from the frontend (running on port 8003) to the backend (running on port 8000). This is typically done in `vite.config.js` or `vite.config.ts` within the `project` directory (create one if it doesn't exist). A common proxy setup looks like:
        ```javascript
        // vite.config.js or vite.config.ts
        import { defineConfig } from 'vite'
        import react from '@vitejs/plugin-react'

        export default defineConfig({
          plugins: [react()],
          server: {
            port: 8003, // Or your desired frontend port
            proxy: {
              // Proxy API requests to the backend server
              '/ask': {
                target: 'http://localhost:8000', // Your backend address
                changeOrigin: true,
              }
            }
          }
        })
        ```

5.  **Access the Application:**
    *   **Live Mode:** Open `http://localhost:8003/`
    *   **Mock Mode:** Open `http://localhost:8003/mock`

## Deployment to Azure

The application is deployed as a Docker container to Azure App Service.

1.  **Build Clean Image:** Ensure latest changes are included and avoid cache issues.
    ```bash
    docker build --platform linux/amd64 --no-cache -t financegpt-app .
    ```
2.  **Tag for ACR:**
    ```bash
    # Replace with your ACR details if different
    docker tag financegpt-app crwestus001.azurecr.io/financegpt-app:amd64
    ```
3.  **Login to ACR (if needed):**
    ```bash
    az login # Ensure you're logged into the correct Azure account
    az acr login --name crwestus001 # Replace with your ACR name
    ```
4.  **Push to ACR:**
    ```bash
    docker push crwestus001.azurecr.io/financegpt-app:amd64
    ```
5.  **Update Azure App Service:** Tell App Service to pull the new image version.
    ```bash
    # Replace secv2/sec with your App Service name / Resource Group if different
    az webapp config container set --name secv2 --resource-group sec --container-image-name crwestus001.azurecr.io/financegpt-app:amd64
    ```
6.  **Verify:** Check both `https://secv2.azurewebsites.net/` and `https://secv2.azurewebsites.net/mock` after Azure finishes updating (may take a few minutes). Clear browser cache aggressively if needed.

## Project Files

-   `api_server.py`: FastAPI backend server.
-   `project/`: Directory containing the React frontend source code.
    -   `project/src/App.tsx`: Main React component.
    -   `project/package.json`: Frontend dependencies.
    -   `project/dist/`: Built frontend assets (generated during Docker build).
-   `Dockerfile`: Instructions for building the production Docker image.
-   `.dockerignore`: Specifies files/directories to exclude from the Docker build context.
-   `requirements.txt`: Python backend dependencies.
-   `.env`: Stores API keys (needs to be created by user).
-   `@roadmap.txt`: Development plan and tasks.
-   `@history.txt`: Log of development changes.
-   `README.md`: This file.
-   `sec_bot_cli.py`: Original CLI version (kept for reference/potential reuse).

## Future Enhancements (from Roadmap)

-   Refine tool descriptions/prompts for improved agent accuracy.
-   Set up GitHub Actions for CI/CD to Azure App Service (Automate deployment).
-   Add more robust error handling and user feedback in the UI.
-   Explore adding conversational memory to the backend API (would require state management). 