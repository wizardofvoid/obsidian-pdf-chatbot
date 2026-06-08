import logging
import streamlit as st
import config
from rag_agent import RAGAgent
from streamlit_mic_recorder import mic_recorder

logger = logging.getLogger(__name__)

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
    """Injects high-quality minimal dark custom CSS styling from assets/style.css."""
    from pathlib import Path
    style_path = Path(__file__).resolve().parent / "assets" / "style.css"
    if style_path.exists():
        with open(style_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
    else:
        st.warning("Could not find assets/style.css")

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

@st.cache_resource
def init_config():
@st.cache_resource
def init_config():
    config.init()
    from git_sync import sync_obsidian_repo
    sync_obsidian_repo()
    return True

def main():
    init_config()
    st.set_page_config(page_title="Obsidian & PDF Brain Chat", layout="wide")
    inject_premium_styles()
    
    st.title("Obsidian & PDF Study Brain")
    
    agent = get_agent()
    
    # Self-healing cache reload if class signature changed
    try:
        agent.get_index_status
        agent.clean_text_for_tts
        if not st.session_state.get("_cache_busted", False):
            st.cache_resource.clear()
            st.session_state["_cache_busted"] = True
            st.rerun()
    except AttributeError:
        st.cache_resource.clear()
        st.rerun()
    audio = None
    voice_mode = "Translate to English"
    
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
            st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>Cloud Integration</h3>", unsafe_allow_html=True)
            if st.button("Pull Latest Notes from GitHub", use_container_width=True):
                with st.spinner("Pulling from GitHub..."):
                    from git_sync import sync_obsidian_repo
                    if sync_obsidian_repo():
                        st.success("Successfully pulled latest notes from GitHub!")
                        # Optionally, we could automatically run Neo4j sync here
                    else:
                        st.error("Failed to pull from GitHub. Check variables.")
        st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>Voice Assistant</h3>", unsafe_allow_html=True)
        voice_mode = st.selectbox(
            "Voice input mode:",
            options=["Translate to English", "Original Language (Transcription)"],
            index=0
        )
        st.checkbox("Read-Aloud Assistant Responses", value=False, key="tts_read_aloud")
        st.slider("Voice Speed Adjust", min_value=-50, max_value=50, value=-10, step=5, format="%d%%", key="tts_speed")
        audio = mic_recorder(
            start_prompt=" Start Speaking",
            stop_prompt=" Stop & Submit",
            key="mic_recorder",
            use_container_width=True
        )
        
        st.markdown("---")
        st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>1. Upload PDF Materials</h3>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Upload one or more PDFs", type=["pdf"], accept_multiple_files=True
        )
        
        uploaded_file_names = [f.name for f in uploaded_files] if uploaded_files else []
        
        if "prev_uploaded_files" not in st.session_state:
            st.session_state["prev_uploaded_files"] = []
            
        saved_names = []
        removed_names = []
        
        # Sync PDFs in storage with files currently uploaded in Streamlit
        if uploaded_files or st.session_state["prev_uploaded_files"]:
            from document_manager import DocumentManager
            saved_names, removed_names, current_names = DocumentManager.sync_streamlit_uploads(
                uploaded_files, st.session_state["prev_uploaded_files"]
            )
            from document_manager import DocumentManager
            saved_names, removed_names, current_names = DocumentManager.sync_streamlit_uploads(
                uploaded_files, st.session_state["prev_uploaded_files"]
            )
            if saved_names:
                st.success(f"Saved: {', '.join(saved_names)}")
            if removed_names:
                st.warning(f"Deleted from storage: {', '.join(removed_names)}")
            st.session_state["prev_uploaded_files"] = current_names
            st.session_state["prev_uploaded_files"] = current_names
            
        st.markdown("<h3 style='color:#9AA0A6; font-size:0.9rem; font-weight:500; margin-bottom:0.4rem; font-family:Inter, sans-serif;'>2. Knowledge Indexing</h3>", unsafe_allow_html=True)
        
        # Ingest state checks
        status = agent.get_index_status()
        
        # Determine configuration options
        skip_ocr = st.checkbox("Skip Image OCR (Fast Mode)", value=True, key="skip_ocr")
        auto_sync = st.checkbox("Auto-Sync on upload/delete", value=True, key="auto_sync")
        
        if auto_sync and (saved_names or removed_names):
            with st.spinner("Auto-synchronizing vector index..."):
                ok = agent.run_ingestion(skip_ocr=skip_ocr)
            if ok:
                st.toast("⚡ Index synchronized successfully!")
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error("Auto-sync failed.")
        
        # Display Index Status Panel
        if not status["active_files"]:
            st.info("No PDF files uploaded yet. Add some PDFs above.")
        else:
            if status["needs_sync"]:
                st.warning("⚠️ Vector index is out of sync.")
                if status["to_add"]:
                    st.markdown("**Pending additions/updates:**")
                    for f in status["to_add"]:
                        st.markdown(f"<span style='color: #E2B714; font-size: 0.85rem;'>➕ {f}</span>", unsafe_allow_html=True)
                if status["to_delete"]:
                    st.markdown("**Pending removals:**")
                    for f in status["to_delete"]:
                        st.markdown(f"<span style='color: #F87171; font-size: 0.85rem;'>➖ {f}</span>", unsafe_allow_html=True)
            else:
                st.success("✅ Index is perfectly synchronized!")
                st.markdown("**Currently Indexed PDFs:**")
                for f in status["indexed_files"]:
                    st.markdown(f"<span style='color: #10B981; font-size: 0.85rem;'>📄 {f}</span>", unsafe_allow_html=True)
                    
        st.markdown("")
        # Manual Trigger Button
        if st.button("Extract & Sync Index Manually", use_container_width=True):
            with st.spinner("Synchronizing vector index..."):
                ok = agent.run_ingestion(skip_ocr=skip_ocr)
            st.cache_resource.clear()
            if ok:
                st.success("FAISS Vector Index updated!")
                st.rerun()
            else:
                st.error("Index synchronization failed.")
                
        st.markdown("---")
        if st.button("Clear Chat History", use_container_width=True):
            agent.clear_session(session_id)
            st.session_state["messages"] = []
            st.success(f"Cleared history for session '{session_id}'.")
            
        if st.button("Factory Reset Storage", use_container_width=True):
            from document_manager import DocumentManager
            if DocumentManager.factory_reset():
                agent.reload()
                agent.clear_session(session_id)
                st.session_state["messages"] = []
                st.session_state["prev_uploaded_files"] = []
                st.cache_resource.clear()
                st.success("Successfully cleared all PDFs, cache indexes, and chat memory!")
            else:
                st.error("Factory reset failed. See logs.")
            from document_manager import DocumentManager
            if DocumentManager.factory_reset():
                agent.reload()
                agent.clear_session(session_id)
                st.session_state["messages"] = []
                st.session_state["prev_uploaded_files"] = []
                st.cache_resource.clear()
                st.success("Successfully cleared all PDFs, cache indexes, and chat memory!")
            else:
                st.error("Factory reset failed. See logs.")
            
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
                if msg.get("audio_bytes"):
                    is_latest = (i == len(st.session_state["messages"]) - 1)
                    should_autoplay = is_latest and not msg.get("autoplay_done", False)
                    if should_autoplay:
                        msg["autoplay_done"] = True
                    st.audio(msg["audio_bytes"], format="audio/mp3", autoplay=should_autoplay)
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
    
    if not question and audio:
        import hashlib
        audio_hash = hashlib.md5(audio['bytes']).hexdigest()
        if st.session_state.get("last_processed_audio") != audio_hash:
            st.session_state["last_processed_audio"] = audio_hash
            
            with st.spinner("Processing speech..."):
                translate = (voice_mode == "Translate to English")
                ext = audio.get("format", "webm")
                transcribed_text = agent.transcribe_audio(
                    audio_bytes=audio["bytes"],
                    format=ext,
                    translate=translate
                )
                
            if transcribed_text.strip():
                question = transcribed_text.strip()
                st.toast(f"🗣️ Heard: {question}")
            else:
                st.warning("Could not recognize any speech. Please try again.")
                
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
            
    audio_bytes = None
    logger.debug("tts_read_aloud active: %s", st.session_state.get('tts_read_aloud', False))
    if st.session_state.get("tts_read_aloud", False):
        with st.spinner("Synthesizing voice response..."):
            try:
                cleaned = agent.clean_text_for_tts(answer)
                logger.debug("Cleaned text for TTS: '%s'", cleaned)
                if cleaned:
                    speed_val = st.session_state.get("tts_speed", -10)
                    rate_str = f"{speed_val:+d}%"
                    logger.debug("Calling text_to_speech with rate: '%s'", rate_str)
                    audio_bytes = agent.text_to_speech(cleaned, rate=rate_str)
                    logger.debug("Successfully generated %s bytes of audio", len(audio_bytes) if audio_bytes else 0)
                else:
                    logger.debug("Cleaned text is empty. Skipping TTS.")
            except Exception as e:
                logger.error("TTS failed: %s", e)

    st.session_state["messages"].append({
        "role": "assistant",
        "content": answer,
        "citations": unique_citations,
        "audio_bytes": audio_bytes
    })
    st.rerun()

if __name__ == "__main__":
    main()
