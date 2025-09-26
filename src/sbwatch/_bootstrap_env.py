from __future__ import annotations
from dotenv import load_dotenv, find_dotenv
# Load .env from the current project; let .env override any existing env vars
load_dotenv(find_dotenv(usecwd=True), override=True)
