"""
Operating Systems & Computer Systems Architecture practice types:
- page_table_walk: Multi-level virtual to physical address translation
- cache_tag_index_offset: Cache geometry decomposition (Tag, Index, Offset bits)
- assembly_reg_trace: Instruction sequence execution and register file state trace
- deadlock_bankers: Banker's safety algorithm and deadlock avoidance verification

Exports NORMALIZERS, GRADERS, and SECRET_FIELDS. Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"expected", "solution", "physical_address", "expected_bits", "final_registers", "safe_sequence", "is_safe"}


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        val = float(v)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. page_table_walk
# ---------------------------------------------------------------------------
def _np_page_table_walk(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    va_str = _s(p.get("virtual_address") or p.get("va"), 50)
    page_size = int(_num(p.get("page_size_bytes")) or 4096)
    vpn = p.get("vpn")
    ppn = p.get("ppn")

    if not va_str:
        return None

    try:
        va = int(va_str, 16) if va_str.startswith(("0x", "0X")) else int(va_str)
        offset_mask = page_size - 1
        offset = va & offset_mask
        expected_vpn = va // page_size
        actual_ppn = int(ppn) if ppn is not None else (expected_vpn + 0x10)
        pa = (actual_ppn * page_size) | offset
    except Exception:
        return None

    return {
        **base,
        "virtual_address": hex(va),
        "page_size_bytes": page_size,
        "vpn": expected_vpn,
        "ppn": actual_ppn,
        "physical_address": hex(pa),
    }


def _grade_page_table_walk(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = _s(item.get("physical_address")).lower()
    sub_raw = _s(submission.get("physical_address") if isinstance(submission, dict) else submission).lower()

    try:
        exp_int = int(expected, 16) if expected.startswith("0x") else int(expected)
        sub_int = int(sub_raw, 16) if sub_raw.startswith("0x") else int(sub_raw)
        ok = (exp_int == sub_int)
    except Exception:
        ok = False

    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Physical address {hex(exp_int)} verified!" if ok else f"Incorrect address translation.",
        "details": {"submitted": sub_raw, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 2. cache_tag_index_offset
# ---------------------------------------------------------------------------
def _np_cache_tag_index_offset(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    addr_bits = int(_num(p.get("address_bits")) or 32)
    cache_size = int(_num(p.get("cache_size_bytes")) or 32768)
    block_size = int(_num(p.get("block_size_bytes")) or 64)
    ways = int(_num(p.get("associativity_ways")) or 4)

    if block_size <= 0 or ways <= 0:
        return None

    num_blocks = cache_size // block_size
    num_sets = num_blocks // ways
    if num_sets <= 0:
        return None

    offset_bits = int(math.log2(block_size))
    index_bits = int(math.log2(num_sets))
    tag_bits = addr_bits - index_bits - offset_bits

    return {
        **base,
        "address_bits": addr_bits,
        "cache_size_bytes": cache_size,
        "block_size_bytes": block_size,
        "associativity_ways": ways,
        "expected_bits": {
            "tag": tag_bits,
            "index": index_bits,
            "offset": offset_bits,
        },
    }


def _grade_cache_tag_index_offset(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Must submit tag, index, and offset bits.", "details": {}}

    exp = item.get("expected_bits", {})
    t_ok = int(submission.get("tag", -1)) == exp.get("tag")
    i_ok = int(submission.get("index", -1)) == exp.get("index")
    o_ok = int(submission.get("offset", -1)) == exp.get("offset")

    correct = sum([t_ok, i_ok, o_ok])
    score = round(correct / 3.0, 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Cache bit-fields match geometry!" if ok else f"Mismatch in fields ({correct}/3 correct).",
        "details": {"submitted": submission, "expected": exp},
    }


# ---------------------------------------------------------------------------
# 3. assembly_reg_trace
# ---------------------------------------------------------------------------
def _np_assembly_reg_trace(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    instructions = [_s(inst, 100) for inst in p.get("instructions", []) if _s(inst, 100)]
    initial_regs = {str(k).strip(): int(v) for k, v in (p.get("initial_registers") or {}).items()}
    if not instructions:
        return None

    # Simple architectural simulator for trace verification
    regs = dict(initial_regs)
    for line in instructions:
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        op = parts[0].lower()
        if op == "add" and len(parts) >= 4:
            rd, rs1, rs2 = parts[1], parts[2], parts[3]
            regs[rd] = regs.get(rs1, 0) + regs.get(rs2, 0)
        elif op in ("addi", "addk") and len(parts) >= 4:
            rd, rs1, imm = parts[1], parts[2], int(parts[3])
            regs[rd] = regs.get(rs1, 0) + imm
        elif op == "sub" and len(parts) >= 4:
            rd, rs1, rs2 = parts[1], parts[2], parts[3]
            regs[rd] = regs.get(rs1, 0) - regs.get(rs2, 0)
        elif op == "slli" and len(parts) >= 4:
            rd, rs1, sh = parts[1], parts[2], int(parts[3])
            regs[rd] = (regs.get(rs1, 0) << sh) & 0xFFFFFFFF
        elif op == "xor" and len(parts) >= 4:
            rd, rs1, rs2 = parts[1], parts[2], parts[3]
            regs[rd] = regs.get(rs1, 0) ^ regs.get(rs2, 0)

    return {
        **base,
        "instructions": instructions,
        "initial_registers": initial_regs,
        "final_registers": regs,
    }


def _grade_assembly_reg_trace(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("final_registers", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Must submit final register map.", "details": {}}

    matched = 0
    total = len(expected)
    for r, exp_val in expected.items():
        if int(submission.get(r, -999999)) == exp_val:
            matched += 1

    score = round(matched / max(1, total), 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Register trace verified!" if ok else f"Register state divergence ({matched}/{total} matched).",
        "details": {"submitted": submission, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 4. deadlock_bankers
# ---------------------------------------------------------------------------
def _np_deadlock_bankers(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    alloc = p.get("allocation")  # list of lists or dict
    max_claim = p.get("max_claim")
    available = p.get("available")
    if not alloc or not max_claim or not available:
        return None

    # Banker's safety check
    n_proc = len(alloc)
    n_res = len(available)
    need = [[max_claim[i][j] - alloc[i][j] for j in range(n_res)] for i in range(n_proc)]
    work = list(available)
    finish = [False] * n_proc
    safe_seq = []

    while len(safe_seq) < n_proc:
        found = False
        for i in range(n_proc):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(n_res)):
                for j in range(n_res):
                    work[j] += alloc[i][j]
                finish[i] = True
                safe_seq.append(i)
                found = True
                break
        if not found:
            break

    is_safe = (len(safe_seq) == n_proc)

    return {
        **base,
        "allocation": alloc,
        "max_claim": max_claim,
        "available": available,
        "is_safe": is_safe,
        "safe_sequence": safe_seq if is_safe else [],
    }


def _grade_deadlock_bankers(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected_safe = item.get("is_safe", False)
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Must submit is_safe and sequence.", "details": {}}

    sub_safe = bool(submission.get("is_safe"))
    if sub_safe != expected_safe:
        return {"ok": False, "score": 0.0, "feedback": f"State was {'safe' if expected_safe else 'unsafe'}.", "details": {}}

    if not expected_safe:
        return {"ok": True, "score": 1.0, "feedback": "Correctly detected deadlock / unsafe state.", "details": {}}

    # If safe, verify submitted sequence is valid
    sub_seq = submission.get("sequence", [])
    alloc = item.get("allocation", [])
    avail = list(item.get("available", []))
    max_c = item.get("max_claim", [])
    n_res = len(avail)

    if len(sub_seq) != len(alloc):
        return {"ok": False, "score": 0.5, "feedback": "Incomplete safe sequence.", "details": {}}

    valid = True
    work = list(avail)
    for p in sub_seq:
        try:
            if any((max_c[p][j] - alloc[p][j]) > work[j] for j in range(n_res)):
                valid = False
                break
            for j in range(n_res):
                work[j] += alloc[p][j]
        except Exception:
            valid = False
            break

    score = 1.0 if valid else 0.5
    return {
        "ok": valid,
        "score": score,
        "feedback": "Valid safe execution sequence!" if valid else "Safe sequence execution stalled on resources.",
        "details": {"valid": valid},
    }


NORMALIZERS = {
    "page_table_walk": _np_page_table_walk,
    "cache_tag_index_offset": _np_cache_tag_index_offset,
    "assembly_reg_trace": _np_assembly_reg_trace,
    "deadlock_bankers": _np_deadlock_bankers,
}

GRADERS = {
    "page_table_walk": _grade_page_table_walk,
    "cache_tag_index_offset": _grade_cache_tag_index_offset,
    "assembly_reg_trace": _grade_assembly_reg_trace,
    "deadlock_bankers": _grade_deadlock_bankers,
}
