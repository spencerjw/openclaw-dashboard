#!/bin/bash
# Run from server to update dashboard data and push to GitHub
cd "$(dirname "$0")"

echo "Collecting agent data..."
python3 collect_data.py

echo "Pushing to GitHub..."
git add -A
git commit -m "Dashboard snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)" --allow-empty
git push origin main

echo "Done. Streamlit Cloud will auto-redeploy."
