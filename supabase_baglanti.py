from supabase import create_client, Client

SUPABASE_URL = "https://obgsuwmljpvniincpkvr.supabase.co"
SUPABASE_KEY = "sb_publishable_i1KMuRCv2rsa9_dvse8MMw_h7s8TEvR"

# Supabase istemcisini başlatıyoruz
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)