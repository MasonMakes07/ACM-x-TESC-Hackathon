"""Readable dark workstation theme. Owner: Person 3 / Codex B."""

import streamlit as st


# Adds responsive spacing and visible focus without hiding native accessibility controls.
def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: dark; }
        .stApp { background: #0b1420; color: #edf3fa; }
        .stMainBlockContainer { max-width: 1440px; padding-top: 2rem; }
        [data-testid="stSidebar"] { background: #121f30; }
        [data-testid="stCaptionContainer"] { color: #b8c8d9; }
        [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums;
            font-size: clamp(1.15rem, 2.3vw, 1.9rem); overflow-wrap: anywhere; }
        [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
        h1, h2, h3 { letter-spacing: -.015em; }
        p, li { line-height: 1.65; }
        a { text-underline-offset: .2em; }
        button, [role="tab"], summary { min-height: 44px; }
        button:focus-visible, a:focus-visible, summary:focus-visible,
        input:focus-visible, [role="tab"]:focus-visible {
            outline: 3px solid #70e1bb !important; outline-offset: 3px;
        }
        .ew-confidence { display: inline-block; border: 1px solid currentColor;
            border-radius: 6px; padding: .35rem .7rem; font-weight: 600; }
        @media (max-width: 640px) {
            .stMainBlockContainer { padding: 1rem; }
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
            [data-testid="stColumn"] { min-width: min(100%, 280px); flex: 1 1 280px; }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { animation: none !important;
                transition: none !important; scroll-behavior: auto !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
