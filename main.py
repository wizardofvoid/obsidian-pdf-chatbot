import streamlit as st
from rag_agent import RAGAgent

@st.cache_resource
def get_agent() -> RAGAgent:
    return RAGAgent()

def format_citation(c):
    source = c.get("source", "")
    page = c.get("page", "")
    if source and "Obsidian" in source:
        return f"`{source}` ({page})"
    else:
        return f"`{source}` (pg. {page})"

def inject_premium_styles():
    """Injects high-quality minimal dark custom CSS styling and Plus Jakarta Sans overrides directly into the Streamlit page."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&display=swap');
            
            /* Typography base */
            html, body, .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6, button, input, select, textarea {
                font-family: 'Outfit', -apple-system, sans-serif !important;
                -webkit-font-smoothing: antialiased;
            }
            
            /* Main backgrounds */
            .stApp {
                background-color: #09090b !important;
                background-image: radial-gradient(circle at 50% 0%, rgba(30, 30, 40, 0.5), rgba(9, 9, 11, 1) 60%) !important;
            }
            .block-container {
                background-color: transparent !important;
            }
            
            /* Floating Glassmorphic Sidebar (Contextual Panel) */
            section[data-testid="stSidebar"] {
                background-color: rgba(9, 9, 11, 0.65) !important;
                backdrop-filter: blur(20px) !important;
                -webkit-backdrop-filter: blur(20px) !important;
                border-right: none !important;
                border: 1px solid rgba(255, 255, 255, 0.08) !important;
                border-radius: 24px !important;
                height: 94vh !important;
                top: 3vh !important;
                left: 1vw !important;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6) !important;
                transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            }
            
            /* Hide sidebar collapse button background for cleaner look */
            button[kind="header"] {
                background-color: transparent !important;
            }
            
            /* Narrow, centered layout */
            .block-container {
                max-width: 850px !important;
                padding-top: 2rem !important;
                padding-bottom: 8rem !important;
            }
            
            /* Elegant headings */
            h1, h2, h3, h4 {
                color: #fafafa !important;
                font-weight: 500 !important;
                letter-spacing: -0.02em !important;
            }
            h1 {
                font-size: 2.25rem !important;
                margin-bottom: 2rem !important;
            }
            
            /* Text colors */
            p, span, label, .stMarkdown {
                color: #a1a1aa !important;
            }
            
            /* Buttons */
            div.stButton > button, [data-testid="stFormSubmitButton"] > button {
                background-color: #18181b !important;
                color: #fafafa !important;
                border: 1px solid #27272a !important;
                border-radius: 6px !important;
                padding: 0.5rem 1rem !important;
                font-weight: 500 !important;
                transition: all 0.2s ease !important;
            }
            
            div.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
                background-color: #27272a !important;
                border-color: #3f3f46 !important;
                color: #ffffff !important;
            }
            
            /* File Uploader Fix & Styling */
            [data-testid="stFileUploader"] {
                background-color: transparent !important;
            }
            [data-testid="stFileUploaderDropzone"] {
                background-color: #09090b !important;
                border: 1px dashed #3f3f46 !important;
                border-radius: 8px !important;
                padding: 2rem !important;
                transition: all 0.2s ease !important;
            }
            [data-testid="stFileUploaderDropzone"]:hover {
                border-color: #52525b !important;
                background-color: #18181b !important;
            }
            /* Specifically style the Browse Files button inside uploader */
            [data-testid="stFileUploaderDropzone"] button {
                background-color: #18181b !important;
                color: #fafafa !important;
                border: 1px solid #27272a !important;
                border-radius: 6px !important;
                font-weight: 500 !important;
            }
            [data-testid="stFileUploaderDropzone"] button:hover {
                background-color: #27272a !important;
                border-color: #3f3f46 !important;
            }
            
            /* Inputs and Selects */
            div[data-baseweb="select"] > div {
                background-color: #09090b !important;
                border: 1px solid #27272a !important;
                border-radius: 6px !important;
            }
            div[data-baseweb="select"] > div:hover {
                border-color: #3f3f46 !important;
            }
            input[type="text"] {
                background-color: #09090b !important;
                border: 1px solid #27272a !important;
                color: #fafafa !important;
                border-radius: 6px !important;
            }
            input[type="text"]:focus {
                border-color: #52525b !important;
            }
            
            /* Chat Interface - Lighter Premium Bubbles */
            [data-testid="stChatMessage"] {
                border-radius: 12px !important;
                padding: 1.5rem !important;
                margin-bottom: 1.5rem !important;
                border: 1px solid transparent !important;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -1px rgba(0, 0, 0, 0.1) !important;
                background-color: #1f1f23 !important;
                border-color: #27272a !important;
            }
            
            /* User Message Differentiation */
            [data-testid="stChatMessage"]:has(div[role="img"]:contains("👤")),
            [data-testid="stChatMessage"]:has(span:contains("user")),
            [data-testid="stChatMessage"]:nth-child(odd) {
                background-color: #27272a !important;
                border-color: #3f3f46 !important;
            }
            
            /* Style Avatars */
            [data-testid="chatAvatarIcon-user"], [data-testid="chatAvatarIcon-assistant"], [data-testid="stChatMessageAvatar"] {
                background-color: transparent !important;
                border-radius: 8px !important;
            }
            
            /* Sleek Floating Chat Input */
            [data-testid="stChatInput"] {
                background-color: rgba(9, 9, 11, 0.7) !important;
                backdrop-filter: blur(20px) !important;
                -webkit-backdrop-filter: blur(20px) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                border-radius: 50px !important;
                box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.8) !important;
                padding: 0.25rem 1rem !important;
                margin-bottom: 2vh !important;
                width: calc(100% - 2rem) !important;
                margin-left: auto !important;
                margin-right: auto !important;
            }
            
            [data-testid="stChatInput"]:focus-within {
                border-color: rgba(255, 255, 255, 0.3) !important;
                box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.3), 0 15px 35px -5px rgba(0, 0, 0, 0.8) !important;
            }
            
            /* Alerts */
            .stAlert {
                background-color: transparent !important;
                border: 1px solid #27272a !important;
                color: #a1a1aa !important;
                border-radius: 6px !important;
            }
            
            /* Hide Streamlit elements */
            #MainMenu, footer { visibility: hidden !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

def render_message_with_source(content: str):
    import re
    match = re.search(r'\[SOURCE:\s*(MATERIALS|GENERAL|HYBRID)\]', content)
    source_type = None
    if match:
        source_type = match.group(1)
        content = content.replace(match.group(0), "").strip()
        
    st.markdown(content)
    
    if source_type == "MATERIALS":
        st.markdown(
            '<div style="display: inline-block; background: #181B20; color: #9AA0A6; '
            'border: 1px solid #2B2E3A; border-radius: 4px; padding: 3px 10px; '
            'font-size: 0.8rem; font-weight: 500; margin-top: 8px; font-family: \'Inter\', sans-serif;">'
            'Source: Study Materials</div>', 
            unsafe_allow_html=True
        )
    elif source_type == "GENERAL":
        st.markdown(
            '<div style="display: inline-block; background: #181B20; color: #9AA0A6; '
            'border: 1px solid #2B2E3A; border-radius: 4px; padding: 3px 10px; '
            'font-size: 0.8rem; font-weight: 500; margin-top: 8px; font-family: \'Inter\', sans-serif;">'
            'Source: General Knowledge</div>', 
            unsafe_allow_html=True
        )
    elif source_type == "HYBRID":
        st.markdown(
            '<div style="display: inline-block; background: #181B20; color: #9AA0A6; '
            'border: 1px solid #2B2E3A; border-radius: 4px; padding: 3px 10px; '
            'font-size: 0.8rem; font-weight: 500; margin-top: 8px; font-family: \'Inter\', sans-serif;">'
            'Source: Hybrid (Materials + General)</div>', 
            unsafe_allow_html=True
        )

def main():
    st.set_page_config(page_title="Obsidian & PDF Brain Chat", layout="wide")
    inject_premium_styles()
    
    st.title("Obsidian & PDF Study Brain")
    
    agent = get_agent()
    
    missing = agent.missing_env_vars()
    if missing:
        st.error(f"Missing variables in your `.env` file: {', '.join(missing)}")
        st.info("Make sure you copy or fill out the `.env` file inside this project directory.")
        st.stop()
        
    with st.sidebar:
        st.markdown("<h2 style='color:#FFFFFF; font-size:1.15rem; font-weight:600; margin-bottom:0.8rem; font-family:Inter, sans-serif;'>System Control</h2>", unsafe_allow_html=True)
        session_id = st.text_input("Session ID", value="default_session")
        
        st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>Knowledge Scope</h3>", unsafe_allow_html=True)
        rag_mode = st.selectbox(
            "Select retriever mode:",
            options=["PDF Textbook Only", "Obsidian Vault Graph Only", "Hybrid (PDF + Obsidian)"],
            index=0
        )
        
        mode_mapping = {
            "PDF Textbook Only": "pdf",
            "Obsidian Vault Graph Only": "obsidian",
            "Hybrid (PDF + Obsidian)": "hybrid"
        }
        selected_mode = mode_mapping[rag_mode]
        
        if selected_mode in ("obsidian", "hybrid"):
            st.markdown("---")
            if st.button("Sync Obsidian Brain", use_container_width=True):
                with st.spinner("Scanning and re-indexing vault for new manual notes..."):
                    res = agent.sync_obsidian_vault()
                    if res["success"]:
                        st.success("Obsidian index synchronized successfully!")
                        st.cache_resource.clear()
                    else:
                        st.error(f"Sync failed: {res['error']}")
                        
        st.markdown("---")
        st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>1. Upload PDF Materials</h3>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Upload one or more PDFs", type=["pdf"], accept_multiple_files=True
        )
        
        uploaded_file_names = [f.name for f in uploaded_files] if uploaded_files else []
        
        if "prev_uploaded_files" not in st.session_state:
            st.session_state["prev_uploaded_files"] = []
            
        # Sync PDFs in storage with files currently uploaded in Streamlit
        if uploaded_files or st.session_state["prev_uploaded_files"]:
            from pathlib import Path
            from config import INPUT_PDF_DIR, OUTPUT_DIR
            
            input_dir = Path(INPUT_PDF_DIR)
            input_dir.mkdir(exist_ok=True, parents=True)
            
            # Save new uploads
            saved_names = []
            for uploaded_file in uploaded_files:
                file_path = input_dir / uploaded_file.name
                if not file_path.exists():
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_names.append(uploaded_file.name)
            if saved_names:
                st.success(f"Saved: {', '.join(saved_names)}")
                
            # Remove deleted uploads
            removed_names = []
            for existing_file in input_dir.glob("*.pdf"):
                if existing_file.name in st.session_state["prev_uploaded_files"] and existing_file.name not in uploaded_file_names:
                    existing_file.unlink()
                    removed_names.append(existing_file.name)
                    # Clear its cached text files
                    for ocr_state in ["True", "False"]:
                        cache_file = Path(OUTPUT_DIR) / "cache" / f"{existing_file.name}_ocr_{ocr_state}.txt"
                        if cache_file.exists():
                            cache_file.unlink()
            if removed_names:
                st.warning(f"Deleted from storage: {', '.join(removed_names)}")
                
            st.session_state["prev_uploaded_files"] = uploaded_file_names
            
        st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>2. Knowledge Indexing</h3>", unsafe_allow_html=True)
        skip_ocr = st.checkbox("Skip Image OCR (Fast Mode)", value=True)
        if st.button("Extract & Build Index", use_container_width=True):
            with st.spinner("Extracting text and building vector index..."):
                ok = agent.run_ingestion(skip_ocr=skip_ocr)
            st.cache_resource.clear()
            if ok:
                st.success("FAISS Vector Index is ready!")
            else:
                st.error("Index build failed. Check logs and try again.")
                
        st.markdown("---")
        if st.button("Clear Chat History", use_container_width=True):
            agent.clear_session(session_id)
            st.session_state["messages"] = []
            st.success(f"Cleared history for session '{session_id}'.")
            
        if st.button("Factory Reset Storage", use_container_width=True):
            import shutil
            from pathlib import Path
            from config import INPUT_PDF_DIR, OUTPUT_DIR, VECTORSTORE_DIR
            
            input_dir = Path(INPUT_PDF_DIR)
            if input_dir.exists():
                shutil.rmtree(input_dir)
                input_dir.mkdir(parents=True, exist_ok=True)
                
            output_dir = Path(OUTPUT_DIR)
            if output_dir.exists():
                shutil.rmtree(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                
            faiss_dir = Path(VECTORSTORE_DIR)
            if faiss_dir.exists():
                shutil.rmtree(faiss_dir)
                
            agent.reload()
            agent.clear_session(session_id)
            st.session_state["messages"] = []
            st.session_state["prev_uploaded_files"] = []
            st.cache_resource.clear()
            st.success("Successfully cleared all PDFs, cache indexes, and chat memory!")
            
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        
    assistant_avatar = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='40' fill='none' stroke='%23fafafa' stroke-width='4' stroke-dasharray='60 40'><animateTransform attributeName='transform' type='rotate' from='0 50 50' to='360 50 50' dur='4s' repeatCount='indefinite'/></circle><circle cx='50' cy='50' r='20' fill='%23fafafa'><animate attributeName='opacity' values='0.5;1;0.5' dur='2s' repeatCount='indefinite'/></circle></svg>"
    user_avatar = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><g><animateTransform attributeName='transform' type='translate' values='0,0; 0,-5; 0,0' dur='3s' repeatCount='indefinite'/><circle cx='50' cy='35' r='20' fill='%23a1a1aa'/><path d='M 20 90 Q 50 50 80 90' stroke='%23a1a1aa' stroke-width='10' fill='none' stroke-linecap='round'/></g></svg>"

    # Render previous messages
    for i, msg in enumerate(st.session_state["messages"]):
        avatar = assistant_avatar if msg["role"] == "assistant" else user_avatar
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant":
                render_message_with_source(msg["content"])
            else:
                st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("citations"):
                st.caption("**Sources:** " + ", ".join(format_citation(c) for c in msg["citations"]))
                
            # Render Compile & Save directly under the latest assistant response bubble
            if msg["role"] == "assistant" and i == len(st.session_state["messages"]) - 1:
                st.markdown("---")
                if st.button("Compile & Save to Obsidian", use_container_width=True, key=f"save_to_obs_{i}"):
                    with st.spinner("Distilling key takeaways and writing note to Obsidian..."):
                        user_q = "Study Takeaway"
                        if i >= 1:
                            user_q = st.session_state["messages"][i - 1]["content"]
                            
                        res = agent.save_concepts_to_obsidian(user_q, msg["content"], msg.get("citations") or [])
                        if res["success"]:
                            st.success(f"Successfully compiled, saved, and auto-linked note: **{res['note_title']}**!")
                        else:
                            st.error(f"Failed to save note: {res['error']}")
                st.markdown("---")
            
    if selected_mode in ("pdf", "hybrid") and not agent.index_ready():
        st.info("No PDF Index detected. Upload your study materials in the sidebar and click 'Extract & Build Index' to get started.")
        st.stop()
        
    question = st.chat_input("Ask a question about your documents...")
    if not question:
        return
        
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(question)
        
    with st.chat_message("assistant", avatar=assistant_avatar):
        citations_container = []
        message_placeholder = st.empty()
        
        # Stream the raw answer first
        with message_placeholder.container():
            answer = st.write_stream(
                agent.ask_stream(
                    question,
                    session_id=session_id,
                    citations=citations_container,
                    mode=selected_mode,
                    chat_history=st.session_state["messages"][:-1]
                )
            )
            
        # Re-render with clean rendering + source pill
        message_placeholder.empty()
        with message_placeholder.container():
            render_message_with_source(answer)
        
        # Filter duplicates and render citations
        unique_citations = []
        seen = set()
        for c in citations_container:
            key = (c["source"], c["page"])
            if key not in seen and c["source"] is not None and c["page"] is not None:
                seen.add(key)
                unique_citations.append(c)
                
        if unique_citations:
            st.caption("**Sources:** " + ", ".join(format_citation(c) for c in unique_citations))
        else:
            unique_citations = None
            
    st.session_state["messages"].append({
        "role": "assistant",
        "content": answer,
        "citations": unique_citations
    })
    st.rerun()

if __name__ == "__main__":
    main()
