import streamlit as st


def inject_styles():
    st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-size: 16.5px;
        line-height: 1.75;
    }

    p, li, .stMarkdown p {
        line-height: 1.75 !important;
    }

    /* Text inputs */
    .stTextInput > div > div > input {
        padding: 10px 14px !important;
        font-size: 16px !important;
    }

    /* Textareas */
    .stTextArea > div > div > textarea {
        padding: 14px !important;
        font-size: 16px !important;
        line-height: 1.75 !important;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        padding: 4px 8px !important;
    }

    /* Form submit / primary buttons — subtle rounding */
    .stButton > button, .stFormSubmitButton > button {
        border-radius: 6px !important;
    }
    </style>
    """, unsafe_allow_html=True)
