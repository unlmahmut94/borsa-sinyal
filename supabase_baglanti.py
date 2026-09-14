import os
import streamlit as st

# Önce GitHub Actions ortamından (env) okumayı dene, yoksa Streamlit secrets'a bak
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
# Supabase istemcisinin dışarıdan import edilebilmesi için:
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)