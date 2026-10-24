"""Load data/sources.yaml, honouring `enabled: false` (a disabled source is kept in the file but skipped everywhere)."""
import os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_all():
    return yaml.safe_load(open(os.path.join(ROOT, "data", "sources.yaml")))

def enabled(src=None):
    """{sport: [enabled sources]} for sports that have at least one enabled source."""
    src = load_all() if src is None else src
    out = {sp: [s for s in lst if s.get("enabled", True) is not False] for sp, lst in src.items()}
    return {sp: lst for sp, lst in out.items() if lst}

def enabled_sports(src=None):
    return set(enabled(src))
