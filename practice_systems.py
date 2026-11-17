"""
Operating Systems & Computer Systems Architecture practice types:
- page_table_walk: Multi-level virtual to physical address translation
- cache_tag_index_offset: Cache geometry decomposition (Tag, Index, Offset bits)
- assembly_reg_trace: Instruction sequence execution and register file state trace
- deadlock_bankers: Banker's safety algorithm and deadlock avoidance verification

Exports NORMALIZERS, GRADERS, SECRET_FIELDS and PUBLIC_FIELDS (both per type). Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Dict[str, Set[str]] = {
    "page_table_walk": {"physical_address"},  # virtual_address, vpn and ppn are the givens
    "cache_tag_index_offset": {"expected_bits"},
    "assembly_reg_trace": {"final_registers"},
    "deadlock_bankers": {"is_safe", "safe_sequence"},
}
PUBLIC_FIELDS: Dict[str, Set[str]] = {"page_table_walk": set(), "cache_tag_index_offset": set(),
                                      "assembly_reg_trace": set(), "deadlock_bankers": {"allocation", "max_claim", "available"}}


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
    """page_table_walk: translate a virtual address to a physical address.
    Fields: virtual_address (hex "0x..." or decimal text), page_size_bytes (default 4096), ppn (the frame the page
    maps to; the server picks vpn + 16 when absent). vpn (virtual page number) and ppn are public givens.
    Secret: physical_address (ppn * page size + offset). Submit {physical_address} or the address as hex/decimal text."""
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

    exp_int = None
    try:
        exp_int = int(expected, 16) if expected.startswith("0x") else int(expected)
        sub_int = int(sub_raw, 16) if sub_raw.startswith("0x") else int(sub_raw)
        ok = (exp_int == sub_int)
    except Exception:
        ok = False

    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Physical address {hex(exp_int)} verified!" if ok else "Incorrect address translation.",
        "details": {"submitted": sub_raw},
    }


# ---------------------------------------------------------------------------
# 2. cache_tag_index_offset
# ---------------------------------------------------------------------------
def _np_cache_tag_index_offset(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """cache_tag_index_offset: split an address into tag, index and offset bit counts.
    Fields: address_bits (default 32), cache_size_bytes (default 32768), block_size_bytes (default 64),
    associativity_ways (default 4); sizes are powers of two. Secret: expected_bits {tag, index, offset}.
    Submit {tag, index, offset} as integer bit counts."""
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

    def bits(key: str) -> int:
        try:
            return int(submission.get(key, -1))
        except (TypeError, ValueError):
            return -1

    t_ok = bits("tag") == exp.get("tag")
    i_ok = bits("index") == exp.get("index")
    o_ok = bits("offset") == exp.get("offset")

    correct = sum([t_ok, i_ok, o_ok])
    score = round(correct / 3.0, 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Cache bit-fields match geometry!" if ok else "Not yet: recheck how the address splits into tag, index and offset bits.",
        "details": {},
    }


# ---------------------------------------------------------------------------
# 3. assembly_reg_trace
# ---------------------------------------------------------------------------
def _np_assembly_reg_trace(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """assembly_reg_trace: trace registers through a short instruction list.
    Fields: instructions (list of text lines: add, addi, sub, slli, xor; at most 64; slli shifts 0-31),
    initial_registers {name: integer, |value| < 2^32, at most 32 registers}.
    Secret: final_registers {name: integer} (computed by the server). Submit {register: integer} for every register."""
    instructions = [_s(inst, 100) for inst in p.get("instructions", []) if _s(inst, 100)]
    initial_regs = {str(k).strip(): int(v) for k, v in (p.get("initial_registers") or {}).items()}
    if not instructions or len(instructions) > 64 or len(initial_regs) > 32 \
            or any(abs(v) >= 2 ** 32 for v in initial_regs.values()):
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
            if not 0 <= sh <= 31:  # RV32 shift amounts are 5 bits; a huge one would build a giant integer
                return None
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
        try:
            if int(submission.get(r, -999999)) == exp_val:
                matched += 1
        except (TypeError, ValueError):
            pass

    score = round(matched / max(1, total), 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Register trace verified!" if ok else "Not yet: retrace the instructions and recheck each register.",
        "details": {},
    }


# ---------------------------------------------------------------------------
# 4. deadlock_bankers
# ---------------------------------------------------------------------------
def _int_matrix(v: Any, rows: int = 0, cols: int = 0) -> Optional[List[List[int]]]:
    """A small matrix of non-negative ints (at most 12 x 8), or None when the shape or values are wrong."""
    if not isinstance(v, list) or not v or len(v) > 12:
        return None
    out: List[List[int]] = []
    for row in v:
        if not isinstance(row, list) or not row or len(row) > 8:
            return None
        try:
            r = [int(x) for x in row]
        except (TypeError, ValueError):
            return None
        if any(x < 0 or x > 10_000 for x in r):
            return None
        out.append(r)
    width = len(out[0])
    if any(len(r) != width for r in out) or (rows and len(out) != rows) or (cols and width != cols):
        return None
    return out


def _bankers_safe_sequence(alloc: List[List[int]], max_claim: List[List[int]], available: List[int]) -> List[int]:
    """The lowest-index-first safe sequence, or [] when the state is unsafe."""
    n_proc, n_res = len(alloc), len(available)
    need = [[max_claim[i][j] - alloc[i][j] for j in range(n_res)] for i in range(n_proc)]
    work, finish, seq = list(available), [False] * n_proc, []
    while len(seq) < n_proc:
        for i in range(n_proc):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(n_res)):
                for j in range(n_res):
                    work[j] += alloc[i][j]
                finish[i] = True
                seq.append(i)
                break
        else:
            return []
    return seq


def _np_deadlock_bankers(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """deadlock_bankers: decide whether a resource state is safe (Banker's algorithm).
    Fields: allocation, max_claim (matrices of non-negative ints, one row per process, one column per resource;
    max_claim >= allocation everywhere), available (vector, one entry per resource); up to 12 processes and 8
    resources. Secret: is_safe, safe_sequence (computed by the server). Submit {is_safe: bool, sequence: [process
    indices, 0-based]}; when the state is safe the sequence must be a permutation of every process that runs, so any
    valid order counts."""
    available_m = _int_matrix([p.get("available")] if isinstance(p.get("available"), list) else None)
    if not available_m:
        return None
    available = available_m[0]
    alloc = _int_matrix(p.get("allocation"), cols=len(available))
    if not alloc:
        return None
    max_claim = _int_matrix(p.get("max_claim"), rows=len(alloc), cols=len(available))
    if not max_claim or any(max_claim[i][j] < alloc[i][j] for i in range(len(alloc)) for j in range(len(available))):
        return None
    seq = _bankers_safe_sequence(alloc, max_claim, available)
    return {**base, "allocation": alloc, "max_claim": max_claim, "available": available,
            "is_safe": bool(seq), "safe_sequence": seq}


def _grade_deadlock_bankers(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    if not isinstance(submission, dict) or "is_safe" not in submission:
        return {"ok": False, "score": 0.0, "feedback": "Say whether the state is safe, and give a sequence if it is.",
                "details": {}}
    expected_safe = bool(item.get("is_safe", False))
    if bool(submission.get("is_safe")) != expected_safe:
        return {"ok": False, "score": 0.0, "feedback": "Not quite: recheck whether every process can finish.", "details": {}}
    if not expected_safe:
        return {"ok": True, "score": 1.0, "feedback": "Right: no order lets every process finish, so the state is unsafe.",
                "details": {}}
    alloc = item.get("allocation") or []
    max_c = item.get("max_claim") or []
    work = list(item.get("available") or [])
    n_proc, n_res = len(alloc), len(work)
    raw = submission.get("sequence")
    try:
        seq = [int(x) for x in raw] if isinstance(raw, list) else []
    except (TypeError, ValueError):
        seq = []
    if sorted(seq) != list(range(n_proc)):
        return {"ok": False, "score": 0.5,
                "feedback": f"Safe is right. Now list each of the {n_proc} processes exactly once, in an order that works.",
                "details": {"valid": False}}
    for step, i in enumerate(seq):
        if any(max_c[i][j] - alloc[i][j] > work[j] for j in range(n_res)):
            return {"ok": False, "score": 0.5,
                    "feedback": f"Safe is right, but step {step + 1} (P{i}) needs more than is available then.",
                    "details": {"valid": False, "stalled_at": step}}
        for j in range(n_res):
            work[j] += alloc[i][j]
    return {"ok": True, "score": 1.0, "feedback": "Valid safe sequence: every process finishes.", "details": {"valid": True}}


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
