"""JSON caseload store. Seed is copied into a writable runtime file."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from threading import Lock

from .clock import desk_date
from .config import ROOT, RUNTIME
from .deadlines import rank_households
from .models import Household, PacketRecord, PendingDecision, RankedCase

SEED_PATH = ROOT / "data" / "seed.json"
RUNTIME_DIR = RUNTIME / "data" / "runtime"
RUNTIME_PATH = RUNTIME_DIR / "caseload.json"
PACKETS_DIR = RUNTIME / "web" / "static" / "packets"


class CaseloadStore:
    def __init__(self) -> None:
        self._lock = Lock()
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        PACKETS_DIR.mkdir(parents=True, exist_ok=True)
        if not RUNTIME_PATH.exists():
            shutil.copyfile(SEED_PATH, RUNTIME_PATH)
        self._data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))

    def reset(self) -> None:
        with self._lock:
            shutil.copyfile(SEED_PATH, RUNTIME_PATH)
            self._data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
            for leftover in PACKETS_DIR.glob("*.pdf"):
                leftover.unlink()
            self._data["pending"] = []
            self._data["packets"] = []
            self._data["night_runs"] = []
            self._persist()

    def _persist(self) -> None:
        RUNTIME_PATH.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def org(self) -> dict:
        return self._data["organization"]

    def households(self) -> list[Household]:
        return [Household.model_validate(h) for h in self._data["households"]]

    def household(self, household_id: str) -> Household:
        for h in self.households():
            if h.household_id == household_id:
                return h
        raise KeyError(household_id)

    def ranked(self) -> list[RankedCase]:
        return rank_households(self.households(), desk_date())

    def pending(self) -> list[PendingDecision]:
        return [PendingDecision.model_validate(p) for p in self._data.get("pending", [])]

    def packets(self) -> list[PacketRecord]:
        return [PacketRecord.model_validate(p) for p in self._data.get("packets", [])]

    def save_pending(self, decision: PendingDecision) -> None:
        with self._lock:
            pending = [p for p in self._data.get("pending", []) if p["household_id"] != decision.household_id]
            pending.append(decision.model_dump())
            self._data["pending"] = pending
            self._persist()

    def clear_pending(self, household_id: str) -> PendingDecision | None:
        with self._lock:
            kept = []
            found = None
            for item in self._data.get("pending", []):
                if item["household_id"] == household_id:
                    found = PendingDecision.model_validate(item)
                else:
                    kept.append(item)
            self._data["pending"] = kept
            self._persist()
            return found

    def add_packet(self, packet: PacketRecord) -> None:
        with self._lock:
            packets = [p for p in self._data.get("packets", []) if p["household_id"] != packet.household_id]
            packets.append(packet.model_dump())
            self._data["packets"] = packets
            self._persist()

    def mark_submitted(self, household_id: str, note: str = "") -> PacketRecord:
        with self._lock:
            for item in self._data.get("packets", []):
                if item["household_id"] == household_id:
                    item["status"] = "submitted"
                    item["decision_note"] = note or item.get("decision_note", "")
                    self._persist()
                    return PacketRecord.model_validate(item)
        raise KeyError(household_id)

    def record_run(self, payload: dict) -> None:
        with self._lock:
            runs = self._data.get("night_runs", [])
            runs.insert(0, payload)
            self._data["night_runs"] = runs[:8]
            self._persist()

    def latest_run(self) -> dict | None:
        runs = self._data.get("night_runs") or []
        return runs[0] if runs else None

    def apply_decision_side_effects(self, household_id: str, choice: str) -> None:
        """After a caseworker chooses, tweak the file so the next tool pass can finish."""
        with self._lock:
            for hh in self._data["households"]:
                if hh["household_id"] != household_id:
                    continue
                if choice == "accept_stale_paystub":
                    for doc in hh["documents"]:
                        if doc["doc_type"] == "paystub":
                            doc["notes"] = "Caseworker accepted stale stub with gap note."
                            doc["issued_on"] = desk_date().isoformat()
                elif choice == "accept_stale_bill":
                    for doc in hh["documents"]:
                        if doc["doc_type"] in {"utility_bill", "proof_of_address"}:
                            doc["notes"] = "Caseworker waived freshness."
                            doc["issued_on"] = desk_date().isoformat()
                elif choice == "use_award_letter":
                    hh["documents"].append(
                        {
                            "doc_id": f"d-{household_id}-award",
                            "doc_type": "paystub",
                            "label": "SSA award letter on file (caseworker confirmed)",
                            "issued_on": desk_date().isoformat(),
                            "notes": "Stands in for paystubs.",
                        }
                    )
                    hh["documents"].append(
                        {
                            "doc_id": f"d-{household_id}-addr",
                            "doc_type": "proof_of_address",
                            "label": "USPS change-of-address printout",
                            "issued_on": desk_date().isoformat(),
                        }
                    )
                elif choice == "collect_signature":
                    for enr in hh["enrollments"]:
                        enr["signature_on_file"] = True
                elif choice == "file_with_income_note":
                    for enr in hh["enrollments"]:
                        enr["income_changed"] = False
                        enr["notes"] = "Filed with income-change addendum."
                elif choice == "expedited_reapply":
                    for enr in hh["enrollments"]:
                        if enr["program"] == "SNAP":
                            enr["next_recert_on"] = desk_date().isoformat()
            self._persist()


STORE = CaseloadStore()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
