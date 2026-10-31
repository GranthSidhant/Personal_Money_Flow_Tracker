import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from app.extensions import db
from app.models.ai_draft import AIDraft
from app.models.voice_note import VoiceNote
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.category import Category
from app.models.expense import Expense
from app.models.expense_allocation import ExpenseAllocation
from app.services.allocation_service import record_expense_with_allocations
from app.services.audit_service import log_audit_event
from app.utils.money import rupees_to_paise, format_inr


def is_ai_configured() -> bool:
    """Return True if Gemini API key is configured in environment."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key)


def get_ai_status() -> Dict[str, Any]:
    """Return status metadata about AI provider and configuration."""
    has_key = is_ai_configured()
    return {
        "enabled": True,  # Heuristic fallback is always active locally
        "has_api_key": has_key,
        "provider": "gemini" if has_key else "heuristic",
        "model": "gemini-1.5-flash" if has_key else "rule-based-local",
        "label": "Google Gemini 1.5 Flash" if has_key else "Local Heuristic Engine (Free / Offline)",
    }


def parse_with_gemini(text: str, context_notes: str = "") -> Dict[str, Any]:
    """
    Call Google Gemini REST API using server-side key.
    Enforces strict structured JSON output.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    prompt = (
        "You are an expert personal financial assistant for an app tracking money received from people "
        "and expenses paid. Analyze the following user note/transcript and extract financial intent into strict JSON.\n\n"
        "Rules:\n"
        "1. transaction_type MUST be one of: 'EXPENSE', 'RECEIPT', or 'AMBIGUOUS'.\n"
        "2. Do NOT invent information. If unknown, use null.\n"
        "3. amount_rupees: numeric float or null if not mentioned.\n"
        "4. person_name: name of the person who gave or received money, or null.\n"
        "5. category: standard category like 'Groceries', 'Food', 'Travel', 'Utilities', 'Medical', 'Shopping', or null.\n"
        "6. description: short description of what happened.\n"
        "7. confidence: 'HIGH', 'MEDIUM', or 'LOW'.\n"
        "8. warnings: array of strings noting any ambiguities or missing fields.\n\n"
        f"User Note:\n{text}\n"
    )
    if context_notes:
        prompt += f"\nAdditional Context:\n{context_notes}\n"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=12) as response:
        res_body = response.read().decode("utf-8")
        parsed_res = json.loads(res_body)
        raw_text = parsed_res["candidates"][0]["content"]["parts"][0]["text"]
        extracted = json.loads(raw_text)

    # Normalize fields
    amount_rupees = extracted.get("amount_rupees")
    amount_paise = rupees_to_paise(float(amount_rupees)) if amount_rupees else 0

    return {
        "transaction_type": extracted.get("transaction_type", "AMBIGUOUS"),
        "amount_rupees": float(amount_rupees) if amount_rupees else 0.0,
        "amount_paise": amount_paise,
        "person_name": extracted.get("person_name"),
        "category": extracted.get("category"),
        "description": extracted.get("description", text[:100]),
        "confidence": extracted.get("confidence", "MEDIUM"),
        "warnings": extracted.get("warnings", []),
    }


def parse_with_heuristics(text: str, user_id: int) -> Dict[str, Any]:
    """
    Robust local rule-based extractor when Gemini API key is absent.
    Satisfies project requirements: zero paid requirements for local development.
    """
    clean_text = text.strip()
    warnings = []

    # 1. Detect Amount
    # Matches patterns like ₹1,500, Rs. 2000, 500 inr, or just numbers with currency context
    amount_pattern = re.compile(r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*(?:₹|rs\.?|inr|rupees?)?", re.IGNORECASE)
    matches = amount_pattern.findall(clean_text)

    amount_rupees = 0.0
    for match in matches:
        raw_num = match.replace(",", "").strip()
        if raw_num:
            try:
                val = float(raw_num)
                if val > 0:
                    amount_rupees = val
                    break
            except ValueError:
                continue

    if amount_rupees == 0.0:
        warnings.append("Could not confidently extract transaction amount from note.")

    # 2. Detect Transaction Type
    lower = clean_text.lower()
    receipt_keywords = ["received", "got", "sent me", "gave me", "credit", "transfer from", "given by", "paid me"]
    expense_keywords = ["spent", "bought", "purchased", "paid", "bill", "debit", "swiped", "expense", "cost"]

    is_receipt = any(kw in lower for kw in receipt_keywords)
    is_expense = any(kw in lower for kw in expense_keywords)

    if is_receipt and not is_expense:
        transaction_type = "RECEIPT"
    elif is_expense and not is_receipt:
        transaction_type = "EXPENSE"
    else:
        transaction_type = "AMBIGUOUS"
        warnings.append("Note contains mixed or ambiguous signals between money received and money spent.")

    # 3. Detect Person
    detected_person = None
    known_people = Person.query.filter_by(user_id=user_id).filter(Person.archived_at.is_(None)).all()
    for p in known_people:
        if re.search(r"\b" + re.escape(p.name) + r"\b", clean_text, re.IGNORECASE):
            detected_person = p.name
            break

    if not detected_person:
        common_names = ["Mother", "Father", "Mom", "Dad", "Sister", "Brother", "Rahul", "Priya", "Amit", "Boss"]
        for cn in common_names:
            if re.search(r"\b" + re.escape(cn) + r"\b", clean_text, re.IGNORECASE):
                detected_person = cn
                break

    # 4. Detect Category
    detected_category = None
    categories = Category.query.filter((Category.user_id == user_id) | (Category.user_id.is_(None))).all()
    for cat in categories:
        if re.search(r"\b" + re.escape(cat.name) + r"\b", clean_text, re.IGNORECASE):
            detected_category = cat.name
            break

    if not detected_category:
        category_map = {
            "Groceries": ["grocery", "groceries", "supermarket", "vegetables", "fruits", "milk", "bread", "ration"],
            "Dining & Food": ["dinner", "lunch", "breakfast", "swiggy", "zomato", "restaurant", "cafe", "coffee", "tea"],
            "Transportation": ["uber", "ola", "auto", "cab", "metro", "bus", "petrol", "diesel", "fuel"],
            "Utilities": ["electricity", "wifi", "internet", "water bill", "recharge", "mobile"],
            "Healthcare": ["medicine", "doctor", "chemist", "pharmacy", "clinic", "hospital"],
        }
        for cat_name, kw_list in category_map.items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", lower) for kw in kw_list):
                detected_category = cat_name
                break

    confidence = "HIGH" if (amount_rupees > 0 and transaction_type != "AMBIGUOUS") else ("MEDIUM" if amount_rupees > 0 else "LOW")

    return {
        "transaction_type": transaction_type,
        "amount_rupees": amount_rupees,
        "amount_paise": rupees_to_paise(amount_rupees),
        "person_name": detected_person,
        "category": detected_category,
        "description": clean_text[:120],
        "confidence": confidence,
        "warnings": warnings,
    }


def create_ai_draft_from_note(
    user_id: int,
    voice_note_id: int,
    include_location: bool = False,
    explicit_consent: bool = True,
) -> AIDraft:
    """
    Extract structured financial draft from a VoiceNote.
    Requires explicit user action/consent.
    Saves AIDraft in PENDING_REVIEW status.
    AI NEVER writes directly to the financial ledger.
    """
    if not explicit_consent:
        raise ValueError("Explicit user consent is required before processing notes through AI.")

    voice_note = VoiceNote.query.filter_by(id=voice_note_id, user_id=user_id).first()
    if not voice_note:
        raise ValueError("Voice note not found or access denied.")

    note_text = (voice_note.transcript or voice_note.text_note or voice_note.title or "").strip()
    if not note_text:
        raise ValueError("Voice note has no audio transcript or text note to process.")

    context_str = ""
    if include_location and voice_note.location:
        loc = voice_note.location
        context_str = f"Location context: {loc.label or 'Unknown'}, City: {loc.city or 'Unknown'}"

    provider_info = get_ai_status()
    provider = provider_info["provider"]
    model = provider_info["model"]
    error_msg = None

    if provider == "gemini":
        try:
            payload = parse_with_gemini(note_text, context_notes=context_str)
        except Exception as e:
            # Graceful fallback to heuristic if Gemini fails or times out
            error_msg = f"Gemini API request failed: {str(e)}. Fallback to local heuristic extraction."
            payload = parse_with_heuristics(note_text, user_id=user_id)
            provider = "heuristic-fallback"
    else:
        payload = parse_with_heuristics(note_text, user_id=user_id)

    draft = AIDraft(
        user_id=user_id,
        voice_note_id=voice_note.id,
        provider=provider,
        model=model,
        status="PENDING_REVIEW",
        extracted_payload_json=json.dumps(payload),
        confidence_metadata_json=json.dumps({
            "confidence": payload.get("confidence", "MEDIUM"),
            "warnings": payload.get("warnings", []),
        }),
        processing_error=error_msg,
    )

    db.session.add(draft)

    if voice_note.status == "UNREVIEWED":
        voice_note.status = "TRANSCRIBED"

    db.session.commit()

    log_audit_event(
        user_id=user_id,
        entity_type="AIDraft",
        entity_id=draft.id,
        action="CREATE",
        after_snapshot={
            "voice_note_id": voice_note.id,
            "provider": provider,
            "model": model,
            "status": "PENDING_REVIEW",
            "extracted": payload,
        },
    )

    return draft


def approve_ai_draft(user_id: int, draft_id: int, approval_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Approve an AI draft and generate real financial ledger records.
    Strict safety constraints:
    1. AI never writes to ledger automatically; only explicit user approval triggers this.
    2. Prevents duplicate approval.
    3. Runs full domain validations.
    4. Records provenance (origin_type='AI_DRAFT').
    """
    draft = AIDraft.query.filter_by(id=draft_id, user_id=user_id).first()
    if not draft:
        raise ValueError("AI Draft not found or access denied.")

    if draft.status == "APPROVED":
        raise ValueError("This AI draft has already been approved. Duplicate approval is prevented.")

    if draft.status == "REJECTED":
        raise ValueError("Cannot approve a rejected AI draft. Please create a new draft if needed.")

    action_type = approval_data.get("transaction_type", "").upper()
    amount_paise = int(approval_data.get("amount_paise", 0))

    if amount_paise <= 0:
        raise ValueError("Approved transaction amount must be greater than zero.")

    created_entity_id = None
    created_entity_type = ""

    if action_type == "RECEIPT":
        # 1. Validate / retrieve Person
        person_id = approval_data.get("person_id")
        if not person_id:
            new_person_name = approval_data.get("new_person_name", "").strip()
            if not new_person_name:
                raise ValueError("A Person must be selected or provided for incoming receipts.")
            person = Person.query.filter_by(user_id=user_id, name=new_person_name).first()
            if not person:
                person = Person(user_id=user_id, name=new_person_name)
                db.session.add(person)
                db.session.flush()
            person_id = person.id
        else:
            person = Person.query.filter_by(id=person_id, user_id=user_id).first()
            if not person:
                raise ValueError("Selected Person not found.")

        # 2. Validate / retrieve Fund
        fund_id = approval_data.get("fund_id")
        if not fund_id:
            new_fund_name = approval_data.get("new_fund_name", "").strip()
            if not new_fund_name:
                new_fund_name = f"{person.name}'s Fund"
            fund = Fund(user_id=user_id, person_id=person_id, title=new_fund_name)
            db.session.add(fund)
            db.session.flush()
            fund_id = fund.id
        else:
            fund = Fund.query.filter_by(id=fund_id, user_id=user_id).first()
            if not fund:
                raise ValueError("Selected Fund not found.")

        received_date_str = approval_data.get("date")
        if received_date_str:
            try:
                received_at = datetime.fromisoformat(received_date_str).replace(tzinfo=timezone.utc)
            except Exception:
                received_at = datetime.now(timezone.utc)
        else:
            received_at = datetime.now(timezone.utc)

        receipt = Receipt(
            user_id=user_id,
            fund_id=fund_id,
            amount_paise=amount_paise,
            received_at=received_at,
            payment_method=approval_data.get("payment_method", "Cash"),
            notes=f"Approved from AI Draft #{draft.id}. {approval_data.get('notes', '')}".strip(),
        )
        db.session.add(receipt)
        db.session.flush()

        created_entity_id = receipt.id
        created_entity_type = "Receipt"

    elif action_type == "EXPENSE":
        title = approval_data.get("title", "").strip() or "Voice Expense"
        category_id = approval_data.get("category_id")
        if category_id:
            cat = Category.query.get(category_id)
            if not cat or (cat.user_id and cat.user_id != user_id):
                category_id = None

        expense_date_str = approval_data.get("date")
        if expense_date_str:
            try:
                expense_at = datetime.fromisoformat(expense_date_str).replace(tzinfo=timezone.utc)
            except Exception:
                expense_at = datetime.now(timezone.utc)
        else:
            expense_at = datetime.now(timezone.utc)

        # Build allocations: default to Pocket Money or selected Fund
        allocations_data = approval_data.get("allocations", [])
        if not allocations_data:
            # Single funding source specified
            source_type = approval_data.get("source_type", "POCKET_MONEY")
            fund_id = approval_data.get("fund_id") if source_type == "FUND" else None
            allocations_data = [{
                "source_type": source_type,
                "fund_id": fund_id,
                "allocated_amount_paise": amount_paise,
                "is_recoverable": bool(approval_data.get("is_recoverable", False)),
            }]

        expense = record_expense_with_allocations(
            user_id=user_id,
            title=title,
            total_amount_paise=amount_paise,
            expense_at=expense_at,
            allocations_data=allocations_data,
            category_id=category_id,
            merchant=approval_data.get("merchant"),
            payment_method=approval_data.get("payment_method", "Cash"),
            description=f"Approved from AI Draft #{draft.id}. {approval_data.get('description', '')}".strip(),
        )
        # Mark provenance
        expense.origin_type = "AI_DRAFT"

        # Link voice note to expense
        if draft.voice_note:
            draft.voice_note.linked_expense_id = expense.id
            draft.voice_note.status = "LINKED"

        created_entity_id = expense.id
        created_entity_type = "Expense"

    else:
        raise ValueError(f"Invalid transaction type '{action_type}'. Must be RECEIPT or EXPENSE.")

    # Mark Draft Approved
    now = datetime.now(timezone.utc)
    draft.status = "APPROVED"
    draft.reviewed_at = now
    draft.approved_at = now

    if draft.voice_note and draft.voice_note.status != "LINKED":
        draft.voice_note.status = "LINKED"

    db.session.commit()

    log_audit_event(
        user_id=user_id,
        entity_type="AIDraft",
        entity_id=draft.id,
        action="APPROVE",
        after_snapshot={
            "status": "APPROVED",
            "created_entity_type": created_entity_type,
            "created_entity_id": created_entity_id,
            "amount_paise": amount_paise,
        },
    )

    return True, f"Successfully approved AI Draft #{draft.id} into {created_entity_type}.", {
        "entity_type": created_entity_type,
        "entity_id": created_entity_id,
    }


def reject_ai_draft(user_id: int, draft_id: int, reason: Optional[str] = None) -> bool:
    """Reject an AI draft."""
    draft = AIDraft.query.filter_by(id=draft_id, user_id=user_id).first()
    if not draft:
        raise ValueError("AI Draft not found or access denied.")

    if draft.status == "APPROVED":
        raise ValueError("Cannot reject an already approved AI draft.")

    now = datetime.now(timezone.utc)
    draft.status = "REJECTED"
    draft.reviewed_at = now
    if reason:
        draft.processing_error = f"Rejected by user: {reason}"

    db.session.commit()

    log_audit_event(
        user_id=user_id,
        entity_type="AIDraft",
        entity_id=draft.id,
        action="REJECT",
        after_snapshot={"status": "REJECTED", "reason": reason},
    )

    return True
