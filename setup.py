#!/usr/bin/env python3
"""
setup.py (not a package setup — a convenience setup script)
─────────────────────────────────────────────────────────────
Run once after cloning to:
1. Create .env from .env.example (if not exists)
2. Install requirements
3. Ingest crop documents into ChromaDB
4. Print next steps

Usage: python setup.py
"""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: str):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"  ⚠️  Command exited with code {result.returncode}")
    return result.returncode == 0


print("""
╔══════════════════════════════════════════════════════════════╗
║        🌾 Smart Farming AI — First-Time Setup                ║
╚══════════════════════════════════════════════════════════════╝
""")

# Step 1: .env
env_file = ROOT / ".env"
env_example = ROOT / ".env.example"
if not env_file.exists():
    import shutil
    shutil.copy(env_example, env_file)
    print("✅ Created .env from .env.example")
    print("   ⚠️  IMPORTANT: Edit .env and add your WATSONX_API_KEY and WATSONX_PROJECT_ID")
else:
    print("✅ .env already exists")

# Step 2: Install requirements
print("\n📦 Installing requirements...")
run(f"{sys.executable} -m pip install -r requirements.txt --quiet")
print("✅ Requirements installed")

# Step 3: Ingest documents
print("\n📚 Ingesting crop guides into ChromaDB...")
success = run(f"{sys.executable} -m scripts.ingest_docs")
if success:
    print("✅ Crop guides ingested successfully")
else:
    print("⚠️  Ingestion failed — check that requirements are installed correctly")

# Step 4: Print next steps
print("""
╔══════════════════════════════════════════════════════════════╗
║                     ✅ Setup Complete!                       ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Next Steps:                                                 ║
║                                                              ║
║  1. Edit .env and add your IBM credentials:                  ║
║     WATSONX_API_KEY=...                                      ║
║     WATSONX_PROJECT_ID=...                                   ║
║                                                              ║
║  2. Start the backend:                                       ║
║     uvicorn backend.main:app --reload                        ║
║                                                              ║
║  3. Start the frontend (new terminal):                       ║
║     streamlit run frontend/app.py                            ║
║                                                              ║
║  4. Open: http://localhost:8501                              ║
║                                                              ║
║  OR run end-to-end demo (no UI needed):                      ║
║     python scripts/run_demo.py                               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
