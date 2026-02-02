# backend/agents/policy/policy_agent.py
from __future__ import annotations

import os
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Unified config import (your project layout)
from config import config


class PolicyAgent:
    """
    HR Policy Q&A agent (neat bullets, no citations).
    - Retrieves policy chunks from a FAISS index.
    - Prompts your LLM to produce 3–6 concise bullets.
    - No LC chain objects; compatible with LC 0.2.x vectorstores.
    """

    def __init__(self, llm: Any):
        """
        llm: an LLM wrapper that may implement one of:
             - generate(prompt)
             - _call(prompt)
             - __call__(prompt)
             - run(prompt)
        """
        self.llm = llm
        self.vectorstore = None            # FAISS instance when loaded
        self._embeddings = None            # HuggingFaceEmbeddings (lazy)
        self.is_loaded = False

        # Try to auto-load the index without raising if missing
        self._auto_load_index()

    # ===================== lazy deps =====================

    def _get_embeddings(self):
        """Return a HuggingFaceEmbeddings instance (handles old/new import paths)."""
        if self._embeddings is None:
            try:
                # Preferred path
                from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
            except Exception:
                # Some environments expose at submodule
                from langchain_huggingface.embeddings import HuggingFaceEmbeddings  # type: ignore

            model_name = getattr(config, "EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
            self._embeddings = HuggingFaceEmbeddings(model_name=model_name)
        return self._embeddings

    def _lazy_import_faiss_and_types(self):
        """Return (FAISS, Document, RecursiveCharacterTextSplitter)."""
        from langchain.docstore.document import Document  # type: ignore
        from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
        from langchain_community.vectorstores import FAISS  # type: ignore
        return FAISS, Document, RecursiveCharacterTextSplitter

    # ===================== index load / build =====================

    def _auto_load_index(self) -> None:
        index_dir = getattr(config, "FAISS_INDEX_PATH", None)
        if not index_dir:
            logger.info("PolicyAgent: FAISS index path not configured.")
            self.is_loaded = False
            return

        index_file = os.path.join(index_dir, "index.faiss")
        if not os.path.exists(index_file):
            logger.info("PolicyAgent: no existing index at %s", index_file)
            self.is_loaded = False
            return

        try:
            FAISS, _, _ = self._lazy_import_faiss_and_types()
            embeddings = self._get_embeddings()
            try:
                self.vectorstore = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
            except TypeError:
                self.vectorstore = FAISS.load_local(index_dir, embeddings)
            self.is_loaded = self.vectorstore is not None
            if self.is_loaded:
                logger.info("PolicyAgent: FAISS index loaded successfully.")
        except Exception as e:
            logger.exception("PolicyAgent: could not auto-load index: %s", e)
            self.is_loaded = False

    def load_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Parse a policy PDF, chunk, embed, and persist a FAISS index."""
        if not os.path.exists(pdf_path):
            return {"error": f"PDF file not found: {pdf_path}"}

        try:
            texts: List[str] = []

            # Prefer LlamaParse if available
            try:
                from llama_parse import LlamaParse  # type: ignore
                parser = LlamaParse(
                    api_key=getattr(config, "LLAMA_CLOUD_API_KEY", None),
                    result_type="markdown",
                    verbose=False,
                )
                parsed_documents = parser.load_data(pdf_path)
                for doc in parsed_documents:
                    if hasattr(doc, "text"):
                        texts.append(doc.text or "")
                    elif hasattr(doc, "page_content"):
                        texts.append(doc.page_content or "")
                    else:
                        texts.append(str(doc))
            except Exception:
                # Fallback to PyPDF
                try:
                    from pypdf import PdfReader  # type: ignore
                    reader = PdfReader(pdf_path)
                    for page in reader.pages:
                        texts.append((page.extract_text() or "").strip())
                except Exception as e:
                    logger.exception("No parser available to read PDF: %s", e)
                    return {"error": "No parser available to read the PDF."}

            if not texts:
                return {"error": "No text extracted from PDF."}

            FAISS, Document, RecursiveCharacterTextSplitter = self._lazy_import_faiss_and_types()
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=getattr(config, "CHUNK_SIZE", 1500),
                chunk_overlap=getattr(config, "CHUNK_OVERLAP", 400),
                separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
                length_function=len,
            )

            documents = []
            base = os.path.basename(pdf_path)
            for i, text in enumerate(texts):
                for chunk in splitter.split_text(text or ""):
                    documents.append(
                        Document(page_content=chunk, metadata={"page": i + 1, "source": base})
                    )

            embeddings = self._get_embeddings()
            index_dir = getattr(config, "FAISS_INDEX_PATH", "policy_faiss_index")
            os.makedirs(index_dir, exist_ok=True)
            self.vectorstore = FAISS.from_documents(documents, embedding=embeddings)
            self.vectorstore.save_local(index_dir)
            self.is_loaded = True

            return {
                "success": True,
                "message": "PDF loaded and indexed",
                "chunks": len(documents),
                "pages": len(texts),
            }
        except Exception as e:
            logger.exception("Error in load_pdf: %s", e)
            return {"error": f"Error loading PDF: {str(e)}"}

    def load_existing_index(self) -> Dict[str, Any]:
        """Explicitly load FAISS index from disk."""
        try:
            index_dir = getattr(config, "FAISS_INDEX_PATH", None)
            if not index_dir:
                return {"error": "Configuration missing (FAISS_INDEX_PATH)"}
            index_file = os.path.join(index_dir, "index.faiss")
            if not os.path.exists(index_file):
                return {"error": "No existing policy index found. Please upload a policy PDF first."}

            FAISS, _, _ = self._lazy_import_faiss_and_types()
            embeddings = self._get_embeddings()
            try:
                self.vectorstore = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
            except TypeError:
                self.vectorstore = FAISS.load_local(index_dir, embeddings)
            self.is_loaded = self.vectorstore is not None
            return {"success": True, "message": "Loaded existing policy index"} if self.is_loaded else {"error": "Failed to load index"}
        except Exception as e:
            logger.exception("Error loading existing index: %s", e)
            self.is_loaded = False
            return {"error": f"Error loading index: {str(e)}"}

    # ===================== helpers =====================

    def _clean_text(self, text: str) -> str:
        """Remove URLs, bracket citations and excessive whitespace."""
        if not text:
            return text
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(r"\(source[:\s]?[^\)]*\)", "", text, flags=re.I)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _format_bullets(self, text: str, max_bullets: int = 6) -> str:
        """
        Normalize arbitrary LLM text into tight, consistent bullets beginning with '• '.
        No headings, no sources, no extra prose.
        """
        if not text:
            return "• Policy not found — consult HR."

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        bullets: List[str] = []

        for ln in lines:
            # remove any leading bullet symbols then re-prefix with '• '
            ln = re.sub(r'^[\-\*\u2022\u2023\u25E6\u2219\u2043\u2013\u2014\.\s]+', '', ln)
            if ln:
                bullets.append(f"• {ln}")
            if len(bullets) >= max_bullets:
                break

        if not bullets:
            # Split by sentences if the model returned paragraphs
            for s in re.split(r"(?<=[.!?])\s+", text):
                s = s.strip()
                if s:
                    bullets.append(f"• {s}")
                if len(bullets) >= max_bullets:
                    break

        # Trim overly long bullets
        trimmed: List[str] = []
        for b in bullets[:max_bullets]:
            pure = b[2:].strip()
            words = pure.split()
            trimmed_text = " ".join(words[:22]) + ("…" if len(words) > 22 else "")
            trimmed.append(f"• {trimmed_text}")

        return "\n".join(trimmed)

    def _invoke_llm(self, prompt: str) -> str:
        """Try different invocation styles on the provided LLM."""
        llm_obj = self.llm
        if hasattr(llm_obj, "generate") and callable(getattr(llm_obj, "generate")):
            return llm_obj.generate(prompt)
        if hasattr(llm_obj, "_call") and callable(getattr(llm_obj, "_call")):
            return llm_obj._call(prompt, stop=None)
        if callable(llm_obj):
            return llm_obj(prompt)
        if hasattr(llm_obj, "run") and callable(getattr(llm_obj, "run")):
            return llm_obj.run(prompt)
        raise RuntimeError("No supported call interface found on LLM")

    def _build_context(self, question: str, k: int = 6) -> str:
        """Pull k most similar chunks and build a concise context block."""
        if not self.is_loaded:
            load_result = self.load_existing_index()
            if "error" in load_result:
                return ""

        if not self.vectorstore:
            return ""

        try:
            if hasattr(self.vectorstore, "as_retriever"):
                retriever = self.vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})
                docs = retriever.get_relevant_documents(question) if hasattr(retriever, "get_relevant_documents") else self.vectorstore.similarity_search(question, k=k)
            else:
                docs = self.vectorstore.similarity_search(question, k=k)
        except Exception:
            docs = self.vectorstore.similarity_search(question, k=k)

        # Stitch together short snippets; keep it light for the LLM
        parts = []
        for d in docs or []:
            txt = getattr(d, "page_content", "") or ""
            if txt:
                parts.append(txt.strip()[:1200])
        return "\n\n".join(parts[:k])

    # ===================== public API =====================

    def query(self, question: str, return_raw: bool = False) -> Dict[str, Any]:
        """
        Returns neat bullet points (string) with no source/citation noise.
        """
        if not self.is_loaded:
            load_result = self.load_existing_index()
            if "error" in load_result:
                return {
                    "error": "Policy database not initialized. Please upload a policy PDF first.",
                    "answer": "• Policy not found — consult HR.",
                }

        context = self._build_context(question, k=6) or "No relevant policy information found."

        # Tight prompt designed to yield bullets only
        prompt = f"""
You are an HR policy assistant. The user asked: "{question}"

Relevant snippets from the company's policy documents:
{context}

Write ONLY clear, concise bullet points for the user:
- 3 to 6 bullets total.
- No sources, no URLs, no headings, no citations.
- Try to cover: eligibility, duration, carry-forward/encashment, documentation, and exceptions when relevant.
- If information is missing, write exactly: "Policy not found — consult HR."
- Each bullet must begin with "• " and be ≤ 22 words.

Output must be ONLY bullet lines that start with "• ". No extra text.
""".strip()

        try:
            raw = self._invoke_llm(prompt)
        except Exception as e:
            logger.exception("LLM call failed: %s", e)
            return {"error": f"LLM call failed: {e}", "answer": "• Internal LLM error. Please try again later."}

        cleaned = self._clean_text(raw or "")
        bullets = self._format_bullets(cleaned, max_bullets=6)

        if not return_raw:
            return {"success": True, "answer": bullets}

        # Optional debug preview (not shown in UI)
        preview = []
        if context and context != "No relevant policy information found.":
            for para in context.split("\n\n")[:5]:
                preview.append((para[:300] + "...") if len(para) > 300 else para)

        return {
            "success": True,
            "answer": bullets,
            "raw_model_output": raw,
            "source_preview": preview,
        }

    def ask(self, question: str) -> str:
        """Convenience alias returning just the answer string for portals."""
        res = self.query(question, return_raw=False)
        return res.get("answer", "• Policy assistant unavailable.")
