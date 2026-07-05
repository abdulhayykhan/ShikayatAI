"""
tools/letter_formatter.py
─────────────────────────
ShikayatAI – Letter Formatter Utility

Provides helper functions for formatting complaint letter text.
Note: Primary letter generation is handled directly by the DrafterAgent
via its system prompt. These utilities are available for post-processing
or standalone use.
"""

from __future__ import annotations

import textwrap
from datetime import datetime


def format_english_letter(
    authority_full_name: str,
    physical_address: str,
    complaint_type: str,
    summary_english: str,
    reference_number: str,
    location: str = "Karachi",
) -> str:
    """
    Formats a formal English complaint letter.

    Args:
        authority_full_name: Full name of the responsible authority.
        physical_address: Mailing address of the authority.
        complaint_type: Category of the complaint (e.g., water, electricity).
        summary_english: English summary of the complaint.
        reference_number: Pre-generated reference number (e.g. REF-2026-12345678).
        location: The complainant's area/neighborhood.

    Returns:
        A fully formatted English complaint letter as a string.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    letter = f"""\
Reference No: {reference_number}
Date: {date_str}

The {authority_full_name},
{physical_address}

Subject: Complaint Regarding {complaint_type.title()} Issue

Respected Sir/Madam,

I, the undersigned resident of {location}, wish to register a formal complaint \
regarding {summary_english}

I kindly request your immediate attention to this matter and urge prompt resolution \
within the stipulated timeframe. Please acknowledge receipt of this complaint and \
provide a reference number for tracking purposes.

Yours faithfully,
_____________________
Name: _______________
CNIC: _______________
Contact: ____________
Address: ____________
"""
    return letter


def format_urdu_letter(
    authority_full_name_urdu: str,
    physical_address: str,
    complaint_type_urdu: str,
    summary_urdu: str,
    reference_number: str,
    location_urdu: str = "کراچی",
) -> str:
    """
    Formats a formal Urdu complaint letter (درخواست style).

    Args:
        authority_full_name_urdu: Authority name in Urdu.
        physical_address: Mailing address of the authority.
        complaint_type_urdu: Complaint type translated to Urdu.
        summary_urdu: Urdu summary of the complaint.
        reference_number: Pre-generated reference number.
        location_urdu: The complainant's area in Urdu script.

    Returns:
        A fully formatted Urdu complaint letter as a string.
    """
    now = datetime.now()
    urdu_months = [
        "جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون",
        "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"
    ]
    date_urdu = f"{now.day} {urdu_months[now.month - 1]} {now.year}"

    letter = f"""\
حوالہ نمبر: {reference_number}
تاریخ: {date_urdu}

جناب {authority_full_name_urdu},
{physical_address}

موضوع: {complaint_type_urdu} سے متعلق شکایت

جناب والا،

میں {location_urdu} کا/کی رہائشی ہوں اور {summary_urdu} کی شکایت درج کرانا چاہتا/چاہتی ہوں۔

گزارش ہے کہ اس معاملے پر فوری توجہ دی جائے اور اسے جلد از جلد حل کیا جائے۔ \
براہ کرم شکایت موصول ہونے کی تصدیق کریں اور ٹریکنگ کے لیے ایک حوالہ نمبر فراہم کریں۔

خاکسار،
_____________________
نام: _______________
شناختی کارڈ: _______________
رابطہ: ____________
پتہ: ____________
"""
    return letter


def truncate_for_preview(text: str, max_chars: int = 300) -> str:
    """Returns a truncated preview of letter text."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."
