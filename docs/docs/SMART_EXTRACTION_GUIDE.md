# Smart Extraction & Setup Guide

This guide explains how to enable and use the **Smart Extraction** system in Silico AI. This hybrid system uses rules-based parsing for speed and **Gemini LLM-assisted recovery** for high-fidelity extraction from complex scientific literature.

## 1. Get your Gemini API Key

To use the Smart Extraction features, you need a Google Gemini API key.

1.  Go to the [Google AI Studio](https://aistudio.google.com/).
2.  Sign in with your Google account.
3.  Click on **"Get API key"** in the sidebar.
4.  Click **"Create API key in new project"**.
5.  **Copy your API key** immediately and store it safely.

## 2. Configure the Backend

The backend service needs this key to communicate with Gemini.

1.  Navigate to the method-development service directory:
    ```bash
    cd services/method-development
    ```
2.  If you don't have a `.env` file yet, copy the example:
    ```bash
    cp .env.example .env
    ```
3.  Open `.env` and add your key:
    ```env
    SILICO_METHOD_DEVELOPMENT_GOOGLE_API_KEY=your_copied_api_key_here
    ```
4.  (Optional) Ensure LLM orchestration is enabled for the observer features:
    ```env
    SILICO_METHOD_DEVELOPMENT_ENABLE_LLM_ORCHESTRATION=true
    ```

## 3. Run the Application

### Start the Backend
From the `services/method-development` directory:
```bash
# Install dependencies (includes the new python-dotenv)
uv sync

# Run the server on port 8001
USE_MILVUS=false uv run uvicorn app.main:app --reload --port 8001
```

### Start the Frontend
In a new terminal, from the project root:
```bash
cd apps/agent
npm install
npm run dev
```
The app will be available at `http://localhost:5175`.

## 4. Run the Optimized Demo

We have updated the **"Quick Demo"** to showcase the system's full potential.

1.  Open the dashboard in your browser.
2.  Click the **"Quick Demo"** button in the top right of the "Local System" card.
3.  This will automatically load the **Metformin and Sitagliptin** case.
4.  Click **"Run Discovery"**.

### What to look for:
- **LLM Assistance**: In the results, look for the "Method extraction was recovered via LLM assistance" warning. This shows Gemini successfully parsed complex PDF text that standard regex missed.
- **Vetted Evidence**: Snippets are now concisely summarized into 1-2 telling sentences by the Agent.
- **Physics Scaling**: Watch how the system automatically scales the literature method (usually 150mm columns) down to your high-speed 50mm UPLC hardware.
