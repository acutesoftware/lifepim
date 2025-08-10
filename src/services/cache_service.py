# ----------------------------------------------------------------------------
# FILE: services/cache_service.py
# ----------------------------------------------------------------------------
import os, pickle
from config import CACHE_FILE

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}

def save_cache(data):
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        print('Cache save failed', e)

