"""
Finance Controller — Test Live OpenAI Connection
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

import openai

api_key = os.getenv("OPENAI_API_KEY")
print("=" * 60)
print("  Finance Controller — Live OpenAI Connectivity Test")
print(f"  Key Prefix: {api_key[:14]}...{api_key[-6:] if api_key else 'None'}")
print("=" * 60)

if not api_key:
    print("[FAIL] No OPENAI_API_KEY found in .env")
    sys.exit(1)

client = openai.OpenAI(api_key=api_key)

print("\n[Step 1] Verifying API authentication via client.models.list() ...")
try:
    models = client.models.list()
    gpt_models = [m.id for m in models.data if "gpt" in m.id]
    print(f"  [PASS] Successfully authenticated! Total models: {len(models.data)}")
    print(f"  Available GPT models: {', '.join(sorted(gpt_models)[:6])}")
except Exception as e:
    print(f"  [FAIL] Authentication / Models call failed: {type(e).__name__}: {e}")

print("\n[Step 2] Testing live inference via client.chat.completions.create (gpt-4o-mini) ...")
try:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a financial reconciliation AI assistant. Respond in JSON."},
            {"role": "user", "content": "Return a JSON object with keys 'status' (string) and 'latency_check' (boolean)."},
        ],
        response_format={"type": "json_object"},
        max_tokens=60,
    )
    print("  [PASS] Live inference succeeded!")
    print(f"  Model:    {resp.model}")
    print(f"  Response: {resp.choices[0].message.content}")
    print(f"  Usage:    {resp.usage}")
except Exception as e:
    print(f"  [STATUS] Chat completion attempt: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
