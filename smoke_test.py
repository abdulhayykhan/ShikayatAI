"""
smoke_test.py
─────────────
Post-deployment verification script for ShikayatAI API.
Hits /api/health and /api/complaint to verify the service is running correctly.
"""

import argparse
import requests
import sys

def run_tests(base_url: str):
    print(f"==================================================")
    print(f" SHIKAYAT-AI SMOKE TESTS: {base_url}")
    print(f"==================================================\n")

    # 1. Health Check Test
    print("[TEST 1] Verifying /api/health...")
    try:
        health_resp = requests.get(f"{base_url}/api/health", timeout=10)
        health_data = health_resp.json()
        
        assert health_resp.status_code == 200, f"Expected status 200, got {health_resp.status_code}"
        assert health_data.get("status") == "ok", "Status is not 'ok'"
        assert "Classifier" in health_data.get("agents", []), "Agents list missing Classifier"
        print("✅ Health check passed.\n")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        sys.exit(1)

    # 2. Complaint Inference Test
    print("[TEST 2] Verifying /api/complaint (Orchestrator Pipeline)...")
    payload = {
        "complaint": "There is a massive water leak in our street that needs immediate fixing.",
        "user_id": "smoke_test_user_001",
        "location": "Test Location Karachi"
    }
    
    try:
        complaint_resp = requests.post(f"{base_url}/api/complaint", json=payload, timeout=120)
        
        if complaint_resp.status_code == 429:
            print("⚠️ API returned 429 RESOURCE_EXHAUSTED. The Groq quota limit was hit.")
            print("   (This means the infrastructure is wired up correctly, but the AI key is maxed out).")
            sys.exit(0)
            
        assert complaint_resp.status_code == 200, f"Expected status 200, got {complaint_resp.status_code}\nResponse: {complaint_resp.text}"
        
        complaint_data = complaint_resp.json()
        
        # Verify JSON shape — matches DrafterResult schema from agents/drafter.py
        assert "reference_number" in complaint_data, "Missing 'reference_number'"
        assert "english_letter" in complaint_data, "Missing 'english_letter'"
        assert "urdu_letter" in complaint_data, "Missing 'urdu_letter'"
        assert "submission_method" in complaint_data, "Missing 'submission_method'"
        assert complaint_data["submission_method"] in ("online", "physical", "both", "phone"), \
            f"Invalid submission_method: {complaint_data['submission_method']}"
        assert len(complaint_data["english_letter"]) > 50, "English letter seems too short"
        assert len(complaint_data["urdu_letter"]) > 20, "Urdu letter seems too short"
        
        print("✅ Inference endpoint passed. Valid DrafterResult JSON returned.")
        print(f"   Reference No:    {complaint_data['reference_number']}")
        print(f"   Submit Via:      {complaint_data['submission_method']}")
        if complaint_data.get("helpline_to_call"):
            print(f"   Helpline:        {complaint_data['helpline_to_call']}")
        print("\nSmoke Tests Completed Successfully! 🎉")
        
    except AssertionError as ae:
        print(f"❌ Inference test failed assertion: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Inference test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run smoke tests against ShikayatAI API")
    parser.add_argument("--url", type=str, required=True, help="Base URL of the deployed API (e.g., https://shikayatai-api-xyz.run.app)")
    args = parser.parse_args()
    
    # Clean trailing slashes
    url = args.url.rstrip('/')
    run_tests(url)
