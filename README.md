# Obsidian & PDF Study Brain

A highly polished, premium Streamlit application that acts as a local RAG (Retrieval-Augmented Generation) brain for your study materials. It seamlessly blends knowledge from your personal **Obsidian Vault** and uploaded **PDF Textbooks** to provide highly contextual, cited answers to your questions.

## Features

- **Premium Glassmorphic UI**: A stunning, custom-built minimalist dark theme featuring floating contextual sidebars, responsive chat pills, and custom SVG animations.
- **Multi-Modal Knowledge**: Query against your PDF materials, your Obsidian markdown notes, or both simultaneously in Hybrid mode.
- **Voice Assistant**: Full support for microphone voice input, automatic transcription/translation, and configurable Text-To-Speech (TTS) audio responses.
- **Cloud Vector Storage**: Uses **Pinecone** for lightning-fast, persistent, cloud-based vector similarity search across PDFs and notes.
- **Cloud Graph Storage**: Integrates with **Neo4j** to build and traverse an active Knowledge Graph of your Obsidian Vault, powering deep GraphRAG.
- **Cloud Deployment Ready**: Includes an automated `git_sync.py` hook to securely pull your Obsidian Vault from a private GitHub repository every time the app spins up on Streamlit Community Cloud.
- **Citation Tracking**: Every answer provided by the AI includes specific source citations (e.g., specific PDF pages or explicit Graph/Note relationships).
- **Direct to Obsidian**: Features a one-click "Compile & Save to Obsidian" button that distills the AI's answer and saves it directly back into your vault as a permanently linked note.

## Prerequisites

Before running the application, ensure you have the following installed:
- Python 3.9+
- A valid Groq API Key (or your configured Langchain LLM provider)
- Google API Key (for embeddings)
- Pinecone API Key
- Neo4j Aura URI and Credentials
- GitHub Personal Access Token (if pulling a private Obsidian Vault)

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/wizardofvoid/obsidian-pdf-chatbot.git
   cd obsidian-pdf-chatbot
   ```

2. **Install Dependencies:**
   Create a virtual environment and install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your API keys and directory paths:
   ```env
   GROQ_API_KEY=your_groq_api_key
   GOOGLE_API_KEY=your_google_api_key
   PINECONE_API_KEY=your_pinecone_key
   PINECONE_INDEX_NAME=obsidian-brain
   NEO4J_URI=your_neo4j_uri
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_neo4j_password
   
   # For local usage
   OBSIDIAN_VAULT_DIR=/path/to/your/obsidian/vault
   
   # For Streamlit Cloud Deployment
   OBSIDIAN_REPO_URL=github.com/your-username/your-obsidian-vault
   GITHUB_TOKEN=your_github_token
   ```

## Usage

1. **Start the Application:**
   ```bash
   streamlit run main.py
   ```

2. **Navigating the Interface:**
   - **Upload PDFs**: Drag and drop your study materials into the floating sidebar.
   - **Build Index**: Click "Extract & Build Index" to process the text and batch-upsert the embeddings to Pinecone.
   - **Select Mode**: Choose between "PDF Textbook Only", "Obsidian Vault Graph Only", or "Hybrid".
   - **Sync Vault**: Click "Sync Obsidian Brain" to scan your vault, update vector embeddings, and re-populate the Neo4j Knowledge Graph.
   - **Cloud Sync**: Use "Pull Latest Notes from GitHub" to trigger a repository sync if running in the cloud.

## Architecture & Technologies

- **Frontend**: [Streamlit](https://streamlit.io/) (Heavily customized with raw CSS injections for a native-app feel).
- **Orchestration**: [LangGraph & LangChain](https://python.langchain.com/) for tool-calling, autonomous extraction, and retrieval orchestration.
- **Vector Database**: [Pinecone](https://www.pinecone.io/) for cloud-based embeddings and fast similarity search.
- **Graph Database**: [Neo4j](https://neo4j.com/) to capture the dynamic relationships between notes.
- **Embeddings**: Google Generative AI Embeddings (`models/gemini-embedding-2`).
- **LLM**: Groq (Llama-3.3-70b-versatile for chatting, Llama-3.1-8b for entity extraction).
- **Voice**: Edge TTS and Streamlit Mic Recorder.

## License

This project is open-source and available under the MIT License.
