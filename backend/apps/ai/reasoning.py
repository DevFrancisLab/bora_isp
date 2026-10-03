import re
from pathlib import Path

RULES_PATH = Path(__file__).with_name("isp_rules.metta")

DECISIONS = (
    "human-escalation-required",
    "technician-required",
    "billing-action-required",
    "troubleshooting-required",
    "service-appears-online",
)
DECISION_SET = set(DECISIONS)


def load_rule_lines():
    lines = []
    for raw in RULES_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("!"):
            line = line[1:].strip()
        lines.append(line)
    return lines


def decide(facts):
    asserted = sorted({str(fact).strip() for fact in facts if str(fact).strip()})
    if _hyperon_available():
        matched = _decide_with_hyperon(asserted)
        engine = "hyperon"
    else:
        matched = _decide_with_rules(asserted)
        engine = "metta-file"
    ordered = []
    for name in matched:
        if name in DECISION_SET and name not in ordered:
            ordered.append(name)
    return {
        "facts": asserted,
        "decisions": ordered,
        "decision": _primary(ordered),
        "engine": engine,
    }


def _primary(decisions):
    for name in DECISIONS:
        if name in decisions:
            return name
    return ""


def _hyperon_available():
    try:
        import hyperon  # noqa: F401
    except ImportError:
        return False
    return True


def _decide_with_hyperon(facts):
    from hyperon import MeTTa

    metta = MeTTa()
    for fact in facts:
        metta.space().add_atom(metta.parse_single(f"(fact {fact})"))
    found = []
    for line in load_rule_lines():
        for group in metta.run(f"!{line}") or []:
            for atom in group or []:
                name = str(atom).strip().strip('"')
                if name in DECISION_SET:
                    found.append(name)
    return found


def _decide_with_rules(facts):
    found = []
    known = set(facts)
    for line in load_rule_lines():
        result = _eval_match(parse_sexpr(line), known)
        if result in DECISION_SET:
            found.append(result)
    return found


def parse_sexpr(text):
    tokens = re.findall(r"\(|\)|[^\s()]+", text)
    if not tokens:
        raise ValueError("Empty MeTTa expression.")

    def read(index):
        if tokens[index] != "(":
            return tokens[index], index + 1
        index += 1
        items = []
        while index < len(tokens) and tokens[index] != ")":
            item, index = read(index)
            items.append(item)
        if index >= len(tokens):
            raise ValueError("Unclosed MeTTa expression.")
        return items, index + 1

    expr, end = read(0)
    if end != len(tokens):
        raise ValueError("Unexpected tokens in MeTTa expression.")
    return expr


def _eval_match(expr, facts):
    if isinstance(expr, str):
        return expr
    if not expr or expr[0] != "match" or len(expr) != 4:
        return None
    pattern = expr[2]
    if not isinstance(pattern, list) or len(pattern) != 2 or pattern[0] != "fact":
        return None
    if pattern[1] not in facts:
        return None
    return _eval_match(expr[3], facts)
