# Obsidian & PDF Study Brain 🧠

A highly polished, premium Streamlit application that acts as a local RAG (Retrieval-Augmented Generation) brain for your study materials. It seamlessly blends knowledge from your personal **Obsidian Vault** and uploaded **PDF Textbooks** to provide highly contextual, cited answers to your questions.

## Features

✨ **Premium Glassmorphic UI**: A stunning, custom-built minimalist dark theme featuring floating contextual sidebars, responsive chat pills, and custom SVG animations.
📚 **Multi-Modal Knowledge**: Query against your PDF materials, your Obsidian markdown notes, or both simultaneously in Hybrid mode.
🔄 **Incremental Syncing**: Intelligently syncs your Obsidian vault without rebuilding the entire index. It tracks modified times and only updates what has changed.
⚡ **Local Vector Storage**: Uses FAISS for lightning-fast, entirely local vector similarity search.
🎯 **Citation Tracking**: Every answer provided by the AI includes specific source citations (e.g., specific PDF pages or specific Obsidian note titles).
📝 **Direct to Obsidian**: Features a one-click "Compile & Save to Obsidian" button that distills the AI's answer and saves it directly back into your vault as a permanently linked note.

## Prerequisites

Before running the application, ensure you have the following installed:
- Python 3.9+
- A valid Groq API Key (or your configured LLM provider)

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
   GROQ_API_KEY=your_groq_api_key_here
   OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
   ```
   *(Ensure you update the paths in `config.py` if your directory structures differ).*

## Usage

1. **Start the Application:**
   ```bash
   streamlit run main.py
   ```

2. **Navigating the Interface:**
   - **Upload PDFs**: Drag and drop your study materials into the floating sidebar to ingest them into the memory.
   - **Build Index**: Click "Extract & Build Index" to process the text and build the FAISS vector database.
   - **Select Mode**: Choose between "PDF Textbook Only", "Obsidian Vault Graph Only", or "Hybrid" depending on what knowledge you want to query.
   - **Sync Vault**: Click "Sync Obsidian Brain" to incrementally update the vector database with your latest manual notes.

## Architecture & Technologies

- **Frontend**: [Streamlit](https://streamlit.io/) (Heavily customized with raw CSS injections for a native-app feel).
- **Orchestration**: [LangChain](https://python.langchain.com/) for chunking, embedding, and retrieval orchestration.
- **Vector Database**: [FAISS](https://github.com/facebookresearch/faiss) for local, fast nearest-neighbor lookups.
- **Embeddings & LLM**: Powered by configured LangChain models (e.g., Groq / Llama).

## License

This project is open-source and available under the MIT License.
