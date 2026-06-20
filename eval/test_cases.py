"""
eval/test_cases.py
──────────────────
Test suite for ShikayatAI Classifier & Safety Pre-Check.
Evaluates 15 test cases across 4 groups.
"""

import asyncio
import json
import os
import sys

# Ensure project root is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.classifier import classify_complaint
from agents.orchestrator import run_safety_precheck

# ─────────────────────────────────────────────
# 1. Test Cases Definition
# ─────────────────────────────────────────────

TEST_CASES = [
    # GROUP 1: Valid complaints in English
    {
        "id": "EN-1",
        "input": "There has been a severe water shortage in our neighborhood for the past 4 days. KWSB is ignoring us.",
        "expected_complaint_type": "water",
        "expected_authority_short": "KWSB",
        "should_reject": False,
        "language": "english"
    },
    {
        "id": "EN-2",
        "input": "My electricity bill for this month has been overcharged by 15,000 PKR despite load shedding.",
        "expected_complaint_type": "electricity",
        "expected_authority_short": "KE",
        "should_reject": False,
        "language": "english"
    },
    {
        "id": "EN-3",
        "input": "Someone is illegally constructing a commercial plaza in our residential zone without SBCA permits.",
        "expected_complaint_type": "illegal_construction",
        "expected_authority_short": "SBCA",
        "should_reject": False,
        "language": "english"
    },

    # GROUP 2: Valid complaints in Urdu script
    {
        "id": "UR-1",
        "input": "تین دن سے ہمارے علاقے میں پانی نہیں آ رہا ہے۔",
        "expected_complaint_type": "water",
        "expected_authority_short": "KWSB",
        "should_reject": False,
        "language": "urdu"
    },
    {
        "id": "UR-2",
        "input": "اس مہینے بجلی کا بل بہت زیادہ اور غلط آیا ہے۔",
        "expected_complaint_type": "electricity",
        "expected_authority_short": "KE",
        "should_reject": False,
        "language": "urdu"
    },
    {
        "id": "UR-3",
        "input": "ہمارے محلے کی مرکزی سڑک ٹوٹی ہوئی ہے جس سے ٹریفک کا مسئلہ ہے۔",
        "expected_complaint_type": "road",
        "expected_authority_short": "KMC",
        "should_reject": False,
        "language": "urdu"
    },

    # GROUP 3: Valid complaints in Romanized Urdu
    {
        "id": "ROM-1",
        "input": "pani nahi aa raha teen din se, tankar mangwana par raha hai",
        "expected_complaint_type": "water",
        "expected_authority_short": "KWSB",
        "should_reject": False,
        "language": "romanized_urdu"
    },
    {
        "id": "ROM-2",
        "input": "bijli nahi hai aadhi raat se, bohot garmi hai",
        "expected_complaint_type": "electricity",
        "expected_authority_short": "KE",
        "should_reject": False,
        "language": "romanized_urdu"
    },
    {
        "id": "ROM-3",
        "input": "kachra nahi utha mahine se, har jagah badboo hai",
        "expected_complaint_type": "garbage",
        "expected_authority_short": "SSMB",
        "should_reject": False,
        "language": "romanized_urdu"
    },
    {
        "id": "ROM-4",
        "input": "sadak mein bada gadhha hai accident ho sakta hai",
        "expected_complaint_type": "road",
        "expected_authority_short": "KMC",
        "should_reject": False,
        "language": "romanized_urdu"
    },

    # GROUP 4: Edge cases that should be REJECTED or clarified
    {
        "id": "EDGE-1",
        "input": "",
        "expected_complaint_type": "none",
        "expected_authority_short": "none",
        "should_reject": True,
        "language": "invalid"
    },
    {
        "id": "EDGE-2",
        "input": "mujhe bohat tez bukhar hai hospital jana hai",
        "expected_complaint_type": "none",
        "expected_authority_short": "none",
        "should_reject": True,
        "language": "romanized_urdu"
    },
    {
        "id": "EDGE-3",
        "input": "police ne mujhe bila waja mara aur phone le liya",
        "expected_complaint_type": "none",
        "expected_authority_short": "none",
        "should_reject": True,
        "language": "romanized_urdu"
    },
    {
        "id": "EDGE-4",
        "input": "XYZ",
        "expected_complaint_type": "none",
        "expected_authority_short": "none",
        "should_reject": True,
        "language": "invalid"
    },
    {
        "id": "EDGE-5",
        "input": "Ye hakumat chor hai, sab paise kha gaye hain, inko vote nahi dena chahiye kabi be. The worst ever system in the history of Pakistan.",
        "expected_complaint_type": "none",
        "expected_authority_short": "none",
        "should_reject": True,
        "language": "romanized_urdu"
    }
]

# ─────────────────────────────────────────────
# 2. Evaluation Logic
# ─────────────────────────────────────────────

async def evaluate():
    print("\n" + "="*70)
    print(" SHIKAYAT-AI : CLASSIFIER & SAFETY EVALUATION SUITE")
    print("="*70)

    total_tests = len(TEST_CASES)
    passed_tests = 0
    failures_by_category = {"english": 0, "urdu": 0, "romanized_urdu": 0, "invalid": 0}

    for idx, tc in enumerate(TEST_CASES, 1):
        case_id = tc["id"]
        lang = tc["language"]
        print(f"\n[{idx}/{total_tests}] Running {case_id} ({lang.upper()})...")
        print(f"  Input: '{tc['input']}'")

        try:
            # 1. First run the Orchestrator's Safety Pre-Check
            safety_res = run_safety_precheck(tc["input"])
            is_rejected = not safety_res.get("safe", True)

            # Check rejection logic
            if tc["should_reject"] and not is_rejected:
                print(f"  ❌ FAILED: Should have been rejected but passed safety check.")
                failures_by_category[lang] += 1
                continue
            elif tc["should_reject"] and is_rejected:
                print(f"  ✅ PASSED: Correctly rejected -> {safety_res.get('reason', '').splitlines()[0][:60]}...")
                passed_tests += 1
                continue
            elif not tc["should_reject"] and is_rejected:
                print(f"  ❌ FAILED: Falsely rejected a valid complaint -> {safety_res.get('reason')}")
                failures_by_category[lang] += 1
                continue

            # 2. Run through Classifier Agent if it wasn't rejected
            result = await classify_complaint(tc["input"])
            
            actual_type = result.complaint_type.lower()
            actual_auth = result.responsible_body_short.upper()

            type_match = (actual_type == tc["expected_complaint_type"].lower())
            auth_match = (actual_auth == tc["expected_authority_short"].upper())

            # 3. Print Results & Check Hallucinations
            if type_match and auth_match:
                print(f"  ✅ PASSED: Type=[{actual_type}], Authority=[{actual_auth}]")
                passed_tests += 1
            else:
                print(f"  ❌ FAILED: Expected Type=[{tc['expected_complaint_type']}], Auth=[{tc['expected_authority_short']}]")
                print(f"             Got      Type=[{actual_type}], Auth=[{actual_auth}]")
                failures_by_category[lang] += 1

        except Exception as e:
            # API Quote limits or other runtime errors
            print(f"  ⚠️ ERROR: Exception during processing: {str(e)[:100]}...")
            if "429" in str(e) or "quota" in str(e).lower():
                print("  => Stopping evaluation due to API Quota Limit.")
                break

    # ─────────────────────────────────────────────
    # 4. Final Report Generation
    # ─────────────────────────────────────────────
    print("\n" + "="*70)
    print(" EVALUATION REPORT")
    print("="*70)
    
    # Calculate accuracy
    # (If loop aborted early, calculate against processed tests. But for simplicity, we evaluate out of total)
    accuracy = (passed_tests / total_tests) * 100

    print(f"  Total Passed: {passed_tests} / {total_tests}")
    print(f"  Accuracy    : {accuracy:.1f}%\n")

    if accuracy >= 85.0:
        print("  🎉 TARGET MET: Accuracy is > 85%!")
    else:
        print("  ⚠️ TARGET MISSED: Accuracy is below 85%.")
        print("\n  Failures by Category:")
        for category, count in failures_by_category.items():
            print(f"    - {category.upper()}: {count} failure(s)")

    print("="*70 + "\n")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        
    class _SuppressOtelNoise:
        def __init__(self, real_stderr):
            self._real = real_stderr
        def write(self, msg):
            if "was created in a different Context" not in msg and \
               "Failed to detach context" not in msg and \
               "Root node" not in msg and \
               "GeneratorExit" not in msg:
                self._real.write(msg)
        def flush(self):
            self._real.flush()

    sys.stderr = _SuppressOtelNoise(sys.stderr)

    try:
        asyncio.run(evaluate())
    except KeyboardInterrupt:
        print("\nEvaluation cancelled.")
    finally:
        sys.stderr = sys.stderr._real
