
import io
import re
import os
from urllib.parse import urlparse
from datetime import datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document
from PIL import Image

# --------------------------------------------------
# TRUTHLENS CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="TruthLens | Information Verification",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #0b1020;
        color: #edf2ff;
    }
    [data-testid="stSidebar"] {
        background: #111a30;
    }
    h1, h2, h3 {
        color: #8bb8ff !important;
    }
    .hero {
        padding: 28px;
        border-radius: 18px;
        background: linear-gradient(120deg, #142344, #172b43);
        border: 1px solid #304669;
        margin-bottom: 24px;
    }
    .hero p {
        color: #c7d5ed;
        font-size: 16px;
    }
    .note {
        background: #14213a;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #60a5fa;
        margin: 12px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
    )
}


def valid_url(value):
    try:
        parsed = urlparse(value.strip())
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and "." in parsed.hostname
            and not any(
                ch.isspace() for ch in value.strip()
            )
        )
    except ValueError:
        return False


def fetch_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    if "text/html" not in content_type:
        raise ValueError(
            "This URL does not return a readable HTML page."
        )

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(
        ["script", "style", "nav", "footer", "header"]
    ):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = soup.get_text(" ", strip=True)

    return title, text[:30000]


def extract_document(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")

    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages[:30]
        )

    if name.endswith(".docx"):
        document = Document(io.BytesIO(data))
        return "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

    raise ValueError(
        "Unsupported file. Upload a TXT, PDF, or DOCX document."
    )


def inspect_text(text):
    """
    This is a preliminary rule-based screening tool.
    It does not independently establish whether a claim is true.
    """
    text = text.strip()

    if not text:
        return {
            "label": "Insufficient information",
            "score": 0,
            "reasons": ["No readable text was provided."],
        }

    reasons = []
    lower = text.lower()

    sensational_phrases = [
        "share before it gets deleted",
        "100% guaranteed",
        "secret they don't want you to know",
        "forward to everyone",
        "miracle cure",
        "shocking truth",
        "breaking news",
    ]

    matches = [
        phrase
        for phrase in sensational_phrases
        if phrase in lower
    ]

    if matches:
        reasons.append(
            "Sensational wording detected: "
            + ", ".join(matches)
        )

    if re.search(r"https?://", text):
        reasons.append(
            "The text contains a URL that may need independent verification."
        )

    if re.search(r"\b(always|never|everyone|nobody)\b", lower):
        reasons.append(
            "Absolute language is present; check for supporting evidence."
        )

    if re.search(r"\b\d{1,3}%\b", text):
        reasons.append(
            "A numerical percentage was found. Verify its source and context."
        )

    if not reasons:
        reasons.append(
            "No configured warning patterns were detected. "
            "This does not prove the claim is true."
        )

    # This is a heuristic screening score, NOT a probability of falsity.
    score = min(100, len(matches) * 25)
    if re.search(r"\b(always|never|everyone|nobody)\b", lower):
        score = min(100, score + 10)

    label = (
        "Needs careful verification"
        if matches or score >= 10
        else "No obvious warning patterns"
    )

    return {
        "label": label,
        "score": score,
        "reasons": reasons,
    }


def show_result(text, source_name="User submission"):
    result = inspect_text(text)

    st.subheader("Preliminary screening result")
    st.write("**Source:**", source_name)
    st.write("**Assessment:**", result["label"])
    st.progress(result["score"] / 100)
    st.caption(
        f"Heuristic warning score: {result['score']}/100. "
        "This is not an accuracy score or probability that a claim is false."
    )

    st.markdown("**Observations**")
    for reason in result["reasons"]:
        st.write(f"- {reason}")

    st.warning(
        "This screening uses simple text patterns, not a trained "
        "fact-checking model. Verify claims against independent, "
        "credible sources before sharing them."
    )

    st.session_state.history.insert(
        0,
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source_name,
            "assessment": result["label"],
        },
    )


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.title("🔎 TruthLens")
st.sidebar.caption("Information verification workspace")

page = st.sidebar.radio(
    "Choose a verification tool",
    [
        "Overview",
        "Text Verification",
        "News & URL Checker",
        "Document Analysis",
        "Image Inspection",
        "Video Inspection",
        "Verification History",
        "About TruthLens",
    ],
)

st.sidebar.divider()
st.sidebar.caption(
    "Evidence first. Check sources before trusting claims."
)

# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------

if page == "Overview":
    st.markdown(
        """
        <div class="hero">
            <h1>TruthLens</h1>
            <p>
                Examine claims, inspect sources, and identify information
                that needs further verification.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Your verification workspace")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📝 Text")
        st.write("Screen statements for warning patterns.")

    with col2:
        st.markdown("### 🌐 News & URLs")
        st.write("Extract readable webpage content for review.")

    with col3:
        st.markdown("### 📄 Documents")
        st.write("Extract text from PDF, DOCX, and TXT files.")

    col4, col5, col6 = st.columns(3)

    with col4:
        st.markdown("### 🖼️ Images")
        st.write("Inspect image properties and visible content manually.")

    with col5:
        st.markdown("### 🎥 Videos")
        st.write("Review a video link and its accompanying claims.")

    with col6:
        st.markdown("### 🔍 Evidence")
        st.write("Use independent sources to check disputed claims.")

    st.info(
        "Start with Text Verification or News & URL Checker. "
        "The current version performs preliminary screening, not "
        "authoritative real/fake classification."
    )

# --------------------------------------------------
# TEXT VERIFICATION
# --------------------------------------------------

elif page == "Text Verification":
    st.title("📝 Text Verification")
    st.write(
        "Enter a claim, social media post, message, or statement."
    )

    claim = st.text_area(
        "Text to examine",
        height=180,
        placeholder=(
            "Paste the claim here...\n"
            "Example: Share before it gets deleted."
        ),
    )

    if st.button("Examine Text", type="primary"):
        if claim.strip():
            show_result(claim, "Text submission")
        else:
            st.warning("Enter some text first.")

# --------------------------------------------------
# NEWS & URL CHECKER
# --------------------------------------------------

elif page == "News & URL Checker":
    st.title("🌐 News & URL Checker")
    st.write(
        "Fetch readable webpage text for preliminary screening. "
        "A webpage's wording alone cannot establish whether its claims are true."
    )

    url = st.text_input(
        "Article or webpage URL",
        placeholder="https://example.com/news-article",
    )

    if st.button("Fetch and Examine", type="primary"):
        if not valid_url(url):
            st.error("Enter a valid HTTP or HTTPS URL.")
        else:
            try:
                with st.spinner("Fetching webpage..."):
                    title, article_text = fetch_page(url)

                st.markdown(f"### {title or 'Webpage content'}")
                st.write("**Fetched URL:**", url)
                st.text_area(
                    "Extracted webpage text",
                    article_text,
                    height=220,
                )

                if article_text.strip():
                    show_result(article_text, url)
                else:
                    st.warning(
                        "No readable article text was found."
                    )

                st.markdown("### Further verification")
                st.markdown(
                    "- [Google Fact Check Explorer]"
                    "(https://toolbox.google.com/factcheck/explorer)"
                )
                st.markdown(
                    "- [Alt News]"
                    "(https://www.altnews.in/)"
                )
                st.markdown(
                    "- [BOOM]"
                    "(https://www.boomlive.in/)"
                )
                st.caption(
                    "These links are research starting points. "
                    "Their inclusion does not mean the submitted claim "
                    "has been checked or endorsed by them."
                )

            except requests.RequestException as error:
                st.error(
                    "Could not retrieve the webpage. It may block automated "
                    "requests or be unavailable."
                )
                st.caption(str(error))
            except ValueError as error:
                st.error(str(error))

# --------------------------------------------------
# DOCUMENT ANALYSIS
# --------------------------------------------------

elif page == "Document Analysis":
    st.title("📄 Document Analysis")
    st.write(
        "Extract text from documents and screen it for warning patterns."
    )

    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["txt", "pdf", "docx"],
    )

    if uploaded_file is not None:
        st.write("**File:**", uploaded_file.name)

        if st.button("Analyze Document", type="primary"):
            try:
                extracted_text = extract_document(uploaded_file)

                if not extracted_text.strip():
                    st.warning(
                        "No text could be extracted. Scanned PDFs may "
                        "require OCR, which is not implemented here."
                    )
                else:
                    st.text_area(
                        "Extracted text",
                        extracted_text[:15000],
                        height=220,
                    )
                    show_result(
                        extracted_text[:30000],
                        uploaded_file.name,
                    )

            except Exception as error:
                st.error(f"Could not process the document: {error}")

# --------------------------------------------------
# IMAGE INSPECTION
# --------------------------------------------------

elif page == "Image Inspection":
    st.title("🖼️ Image Inspection")
    st.write(
        "Inspect image metadata and prepare an image for manual "
        "reverse-image or context verification."
    )

    image_file = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
    )

    if image_file is not None:
        try:
            image = Image.open(image_file)
            st.image(
                image,
                caption="Uploaded image",
                use_container_width=True,
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("Width", f"{image.width}px")
            col2.metric("Height", f"{image.height}px")
            col3.metric("Format", image.format or "Unknown")

            st.info(
                "Image metadata and appearance cannot establish authenticity. "
                "This version does not detect manipulated pixels, generate "
                "reverse-image matches, or identify the original upload."
            )

            st.markdown(
                "[Try Google Lens](https://lens.google.com/)"
            )
            st.markdown(
                "[Try TinEye reverse image search](https://tineye.com/)"
            )

        except Exception as error:
            st.error(f"Could not open this image: {error}")

# --------------------------------------------------
# VIDEO INSPECTION
# --------------------------------------------------

elif page == "Video Inspection":
    st.title("🎥 Video Inspection")

    st.write(
        "Submit a video URL and inspect the available source context."
    )

    video_url = st.text_input(
        "Video URL",
        placeholder="https://www.youtube.com/watch?v=...",
    )

    if st.button("Inspect Video Link", type="primary"):
        if not valid_url(video_url):
            st.error("Enter a valid HTTP or HTTPS URL.")
        else:
            st.markdown(
                f"[Open submitted video source]({video_url})"
            )
            st.markdown(
                "[Search Google Fact Check Explorer]"
                "(https://toolbox.google.com/factcheck/explorer)"
            )
            st.info(
                "This feature validates the URL format only. "
                "It does not extract video frames, transcribe audio, "
                "detect deepfakes, or confirm whether the video is authentic."
            )

# --------------------------------------------------
# HISTORY
# --------------------------------------------------

elif page == "Verification History":
    st.title("📚 Verification History")

    if st.session_state.history:
        st.dataframe(
            st.session_state.history,
            use_container_width=True,
        )

        if st.button("Clear Session History"):
            st.session_state.history = []
            st.rerun()
    else:
        st.info(
            "No checks have been recorded in this session yet."
        )

    st.caption(
        "History is stored in the current Streamlit session and is not "
        "a persistent database."
    )

# --------------------------------------------------
# ABOUT
# --------------------------------------------------

elif page == "About TruthLens":
    st.title("About TruthLens")

    st.write(
        """
        TruthLens is a prototype information-verification website designed
        to help users examine potentially misleading claims.

        The current implementation supports:
        - Rule-based screening of submitted text.
        - Retrieval of readable webpage content.
        - Text extraction from PDF, DOCX, and TXT files.
        - Basic image metadata inspection.
        - Video URL inspection and external research links.
        - Session-level verification history.
        """
    )

    st.subheader("Current limitations")

    st.write(
        """
        - It does not yet use a trained fake-news classification model.
        - It does not automatically verify claims against live evidence.
        - Image manipulation and video deepfake detection are not implemented.
        - It does not currently use OCR for scanned documents.
        - A warning score is not a probability of misinformation.
        """
    )

    st.success(
        "The next development phase can integrate claim extraction, "
        "evidence retrieval, source comparison, OCR, speech transcription, "
        "and multimodal authenticity analysis."
    )

# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "TruthLens | Information Verification Prototype | "
    "Results require independent evidence review."
)
