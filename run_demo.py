"""
run_demo.py
───────────
Quick end-to-end demo script that exercises every agent without
needing the Streamlit UI. Run this to verify the backend works.

Usage:
    python scripts/run_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.schemas import (
    AgentRequest, FarmerProfile, Language, Season, SoilType
)
from backend.agents.orchestrator import orchestrate

# ── Demo profile: wheat farmer in Punjab ──────────────────────────────────────

DEMO_PROFILE = FarmerProfile(
    name="Ramesh Kumar",
    location="Ludhiana, Punjab",
    latitude=30.9010,
    longitude=75.8573,
    land_size_acres=5.0,
    soil_type=SoilType.ALLUVIAL,
    current_crop="wheat",
    season=Season.RABI,
    language=Language.ENGLISH,
)

DEMO_QUERIES = [
    ("RAG", "What fertilisers should I use for wheat and when?"),
    ("Weather", "How much should I irrigate this week based on the weather?"),
    ("Market", "What is the current wheat price and should I sell now?"),
    ("Advisory", "Make a complete season plan for my wheat farm"),
    ("Multilingual", "मेरी गेहूं की फसल में पीली पट्टियाँ हैं, क्या करूँ?"),
]


def run_demo():
    print("=" * 70)
    print("  SMART FARMING AI AGENT — END-TO-END DEMO")
    print("=" * 70)

    for label, query in DEMO_QUERIES:
        print(f"\n{'─'*60}")
        print(f"  [{label}] Query: {query[:70]}")
        print(f"{'─'*60}")

        lang = Language.HINDI if any(ord(c) > 127 for c in query) else Language.ENGLISH

        request = AgentRequest(
            query=query,
            farmer_profile=DEMO_PROFILE,
            language=lang,
        )

        try:
            response = orchestrate(request)
            print(f"\nAgents Used: {[r.agent_name for r in response.agent_responses]}")
            print(f"\nMerged Answer:\n{response.merged_answer[:600]}")
            if len(response.merged_answer) > 600:
                print("... [truncated for demo]")
        except Exception as e:
            print(f"ERROR: {e}")

    print("\n" + "=" * 70)
    print("  Demo complete! All agents exercised.")
    print("  Start the full UI: streamlit run frontend/app.py")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
