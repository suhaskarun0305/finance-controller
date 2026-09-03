"""
Finance Controller — Deduplication & Ingestion Pipeline Layer
==============================================================

Ensures idempotent ingestion of financial records:
  1. Computes deterministic SHA-256 fingerprints for incoming payloads.
  2. Detects existing duplicate fingerprints/IDs and logs a `duplicate_detected` audit event.
  3. Quarantines malformed/incomplete records into the `quarantine_records` table.
  4. Inserts clean unique records with assigned fingerprints.
"""

import hashlib
import json
from enum import Enum
from typing import Any, Dict, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.payment import Payment
from backend.models.invoice import Invoice
from backend.models.settlement import Settlement
from backend.models.quarantine import QuarantineRecord
from backend.models.audit import AuditLog
from backend.reconciliation.normalizer import normalize_record


class IngestionStatus(str, Enum):
    INGESTED = "INGESTED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"


def compute_fingerprint(record_type: str, record: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a payload record.

    Primary identifiers (e.g. razorpay_payment_id) take precedence.
    Fallback hashes join critical business fields (amount, date, reference/customer).
    """
    rec_type = record_type.lower()

    if rec_type == "payment":
        rzp_id = record.get("razorpay_payment_id")
        if rzp_id:
            raw_key = f"payment:{rzp_id}"
        else:
            amt = record.get("amount")
            dt = str(record.get("payment_date"))
            ref = record.get("reference_number") or record.get("order_id") or ""
            raw_key = f"payment:{amt}:{dt}:{ref}"

    elif rec_type == "invoice":
        inv_num = record.get("invoice_number")
        if inv_num:
            raw_key = f"invoice:{inv_num}"
        else:
            amt = record.get("amount")
            cust = record.get("customer_id") or ""
            dt = str(record.get("issue_date"))
            raw_key = f"invoice:{amt}:{cust}:{dt}"

    elif rec_type == "settlement":
        stl_id = record.get("razorpay_settlement_id")
        if stl_id:
            raw_key = f"settlement:{stl_id}"
        else:
            utr = record.get("utr") or ""
            gross = record.get("gross_amount") or record.get("amount")
            dt = str(record.get("settlement_date"))
            raw_key = f"settlement:{utr}:{gross}:{dt}"

    else:
        # Generic payload fallback hash
        raw_key = f"{rec_type}:{json.dumps(record, sort_keys=True)}"

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class DeduplicationPipeline:
    """Idempotent ingestion pipeline with fingerprinting and quarantine handling."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def process_record(
        self, raw_payload: Dict[str, Any], record_type: str = "payment"
    ) -> Tuple[IngestionStatus, Any]:
        """
        Process a single incoming raw record.

        Returns (IngestionStatus, Object/Detail):
          - (INGESTED, model_instance) if successfully ingested
          - (DUPLICATE, fingerprint) if duplicate detected (no-op + audit log created)
          - (QUARANTINED, quarantine_record) if malformed (stored in quarantine_records)
        """
        # 1. Normalize record (catch malformed inputs)
        try:
            normalized = normalize_record(raw_payload, record_type=record_type)
        except Exception as exc:
            quarantine = self._quarantine_record(
                raw_payload=raw_payload,
                record_type=record_type,
                reason=str(exc),
                error_code="MALFORMED_RECORD",
            )
            return IngestionStatus.QUARANTINED, quarantine

        # 2. Compute fingerprint
        fingerprint = compute_fingerprint(record_type, normalized)
        normalized["fingerprint"] = fingerprint

        # 3. Check for duplicates in DB
        existing_model = self._find_existing_duplicate(record_type, normalized, fingerprint)

        if existing_model:
            # Log duplicate_detected audit event
            self._log_duplicate_event(record_type, fingerprint, normalized, existing_model.id)
            return IngestionStatus.DUPLICATE, fingerprint

        # 4. Insert clean record into DB
        model_inst = self._insert_model(record_type, normalized)
        return IngestionStatus.INGESTED, model_inst

    def _find_existing_duplicate(
        self, record_type: str, normalized: Dict[str, Any], fingerprint: str
    ) -> Any | None:
        """Query DB for duplicate by fingerprint or unique ID."""
        rec_type = record_type.lower()

        if rec_type == "payment":
            # Check by fingerprint or razorpay_payment_id
            rzp_id = normalized.get("razorpay_payment_id")
            stmt = select(Payment).where(
                (Payment.fingerprint == fingerprint)
                | (Payment.razorpay_payment_id == rzp_id if rzp_id else False)
            )
            return self.session.scalars(stmt).first()

        elif rec_type == "invoice":
            inv_num = normalized.get("invoice_number")
            stmt = select(Invoice).where(
                (Invoice.fingerprint == fingerprint)
                | (Invoice.invoice_number == inv_num if inv_num else False)
            )
            return self.session.scalars(stmt).first()

        elif rec_type == "settlement":
            stl_id = normalized.get("razorpay_settlement_id")
            stmt = select(Settlement).where(
                (Settlement.fingerprint == fingerprint)
                | (Settlement.razorpay_settlement_id == stl_id if stl_id else False)
            )
            return self.session.scalars(stmt).first()

        return None

    def _log_duplicate_event(
        self, record_type: str, fingerprint: str, payload: Dict[str, Any], existing_id: str
    ) -> None:
        """Create audit log entry for duplicate detection."""
        audit = AuditLog(
            entity_type=record_type,
            entity_id=existing_id,
            action="duplicate_detected",
            actor="ingestion_deduplicator",
            details=json.dumps(
                {
                    "fingerprint": fingerprint,
                    "reason": "Duplicate transaction ingestion rejected (idempotent skip).",
                    "payload_snippet": str(payload)[:200],
                }
            ),
        )
        self.session.add(audit)
        self.session.commit()

    def _quarantine_record(
        self, raw_payload: Dict[str, Any], record_type: str, reason: str, error_code: str
    ) -> QuarantineRecord:
        """Store invalid payload into quarantine_records table."""
        quarantine = QuarantineRecord(
            record_type=record_type,
            raw_payload_json=json.dumps(raw_payload, default=str),
            quarantine_reason=reason,
            error_code=error_code,
        )
        self.session.add(quarantine)
        self.session.commit()
        return quarantine

    def _insert_model(self, record_type: str, normalized: Dict[str, Any]) -> Any:
        """Instantiate and persist ORM model."""
        rec_type = record_type.lower()

        # Clean out temporary normalized keys before ORM instantiation
        payload = {
            k: v for k, v in normalized.items()
            if not k.startswith("normalized_")
        }

        if rec_type == "payment":
            obj = Payment(**payload)
        elif rec_type == "invoice":
            obj = Invoice(**payload)
        elif rec_type == "settlement":
            obj = Settlement(**payload)
        else:
            raise ValueError(f"Unsupported record_type for DB insertion: {record_type}")

        self.session.add(obj)
        self.session.commit()
        return obj
