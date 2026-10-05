import re
from collections import Counter
from dictionary import HIERARCHY, ANCHOR_PATTERNS


def get_root_category(node: str) -> str:
    """
    Recursively traces up the HIERARCHY dictionary to identify 
    the primary Root category (e.g., MONTHLY_BILL, TECHNICAL_ISSUE, etc.)
    """
    if node not in HIERARCHY:
        return None
    curr = node
    while curr in HIERARCHY and HIERARCHY[curr] != "ROOT":
        curr = HIERARCHY[curr]
    return curr


class ConversationState:
    """
    Maintains conversation context across speaker turns / sentences:
      - locked_root: Locked primary root category for the entire transcript
      - active_path: List representing current branch path from ROOT to active node
      - recent_nodes: Bounded list of recently detected nodes
      - recent_turns: Bounded list of recent sentences for context disambiguation
    """
    def __init__(self, history_size=3):
        self.locked_root = None
        self.active_path = ["ROOT"]
        self.recent_nodes = []
        self.recent_turns = []
        self.history_size = history_size

    def filter_labels_by_locked_root(self, labels: list) -> list:
        """
        Locks the root branch upon detecting the first valid label.
        Subsequent labels that belong to a different root branch are rejected.
        """
        valid_labels = []

        for label in labels:
            node_root = get_root_category(label)
            if not node_root:
                continue

            # Lock the root branch on the first detected label's root
            if self.locked_root is None:
                self.locked_root = node_root
                valid_labels.append(label)
            # Only keep labels that match the already locked root branch
            elif node_root == self.locked_root:
                valid_labels.append(label)

        return valid_labels

    def add_turn(self, sentence: str, detected_nodes: list):
        self.recent_turns.append(sentence)
        if len(self.recent_turns) > self.history_size:
            self.recent_turns.pop(0)

        for node in detected_nodes:
            if node in HIERARCHY:
                self.recent_nodes.append(node)
                if len(self.recent_nodes) > self.history_size:
                    self.recent_nodes.pop(0)
                self._update_active_path(node)

    def _update_active_path(self, node: str):
        path = [node]
        curr = node
        while curr in HIERARCHY and HIERARCHY[curr] != "ROOT":
            curr = HIERARCHY[curr]
            path.append(curr)
        path.append("ROOT")
        self.active_path = path[::-1]

    def reset(self):
        self.locked_root = None
        self.active_path = ["ROOT"]
        self.recent_nodes.clear()
        self.recent_turns.clear()


def is_question_sentence(sent: str) -> bool:
    sent = sent.strip()
    question_patterns = [
        r"[?؟]$", r"ද$", r"ද[?.!]$", r"වද$", r"වද[?.!]$",
        r"නේද$", r"නේද[?.!]$", r"කීයකින්", r"කීයද", r"කොච්චර",
        r"කොහොමද", r"ඇයි", r"කවදාද", r"කොහෙද", r"වගේද",
        r"දෙනවද", r"නැද්ද", r"පුළුවන්ද", r"කරන්නද", r"දාන්නද",
        r"යොමු\s*කරන්නද", r"කරමුද", r"දාමුද",
    ]
    return any(re.search(p, sent, re.IGNORECASE) for p in question_patterns)


def split_into_sentences(text: str):
    text = re.sub(r"(Customer|Agent)\s*:", "", text)
    text = re.sub(r"\[(SI|EN|TA)\]", "", text)
    raw = re.split(r"(?<=[.!?।])\s+|\n+", text)
    return [s.strip() for s in raw if len(s.strip()) >= 3]


def classify_sentence(sent: str):
    labels = []
    is_q = is_question_sentence(sent)

    for label, patterns in ANCHOR_PATTERNS.items():
        if label == "PAYMENT_DONE" and is_q:
            continue
        for pattern in patterns:
            if re.search(pattern, sent, re.IGNORECASE):
                labels.append(label)
                break
    return labels


def needs_context(current_sentence: str, labels: list) -> bool:
    sent = current_sentence.strip()
    if not labels:
        return True
    if len(sent.split()) <= 5:
        return True
    if is_question_sentence(sent):
        return True
    context_words = ["එහෙම නම්", "එහෙනම්", "තාම", "තවම", "ඒක", "ඒ සම්බන්ධව", "ඒ ගැන", "ඒකට", "එක", "ඒ"]
    return any(w in sent for w in context_words)


def resolve_label_conflicts(labels: list, state: ConversationState) -> list:
    """
    Disambiguates and resolves multi-node collisions using:
      1. Hierarchy active path state
      2. Leaf level specificity preference
    """
    labels = list(set(labels))
    if len(labels) <= 1:
        return labels

    # Conflict 1: TECHNICAL_ESCALATION vs COMPLAINT
    if "TECHNICAL_ESCALATION" in labels and "COMPLAINT" in labels:
        labels.remove("COMPLAINT")

    # Conflict 2: NEW_CONNECTION_INQUIRY vs INTERNET_ISSUE
    if "INTERNET_ISSUE" in labels and "NEW_CONNECTION_INQUIRY" in labels:
        labels.remove("NEW_CONNECTION_INQUIRY")

    # Conflict 3: NOT_UPDATED vs ISSUE_NOT_RESOLVED using Conversation State Branch
    if "NOT_UPDATED" in labels and "ISSUE_NOT_RESOLVED" in labels:
        active_root = state.active_path[1] if len(state.active_path) > 1 else None
        if active_root == "TECHNICAL_ISSUE":
            labels.remove("NOT_UPDATED")
        elif active_root == "MONTHLY_BILL":
            labels.remove("ISSUE_NOT_RESOLVED")
        else:
            context_str = " ".join(state.recent_turns)
            if re.search(r"(තාක්ෂණික|කාර්මික|නඩත්තු|technician|ටෙක්නිකල්|බලන්න|චෙක්|පරීක්ෂා|හදන්න|රවුටර්|ඉන්ටනෙට්)", context_str, re.IGNORECASE):
                labels.remove("NOT_UPDATED")
            else:
                labels.remove("ISSUE_NOT_RESOLVED")

    return labels


def apply_context_rules(current_sentence: str, state: ConversationState, labels: list):
    current = current_sentence.strip()
    context = " ".join(state.recent_turns)

    # RULE 1: Ambiguous negative responses ("එහෙම නම් තාම නැහැ" / "තාම නැහැ")
    if re.search(r"(එහෙම නම්|එහෙනම්|තාම|තවම).{0,30}(නැහැ|නෑ|නැද්ද)", current, re.IGNORECASE):
        has_pay = re.search(r"(update|updated|අප්ඩේට්|යාවත්කාලීන|payment|පේමන්ට්|ගෙවීම)", context, re.IGNORECASE)
        has_tech = re.search(r"(තාක්ෂණික|කාර්මික|නඩත්තු|technician|ටෙක්නිකල්|බලන්න|චෙක්|පරීක්ෂා|හදන්න|repair|fix|රවුටර්|ඉන්ටනෙට්|ලයින්)", context, re.IGNORECASE)

        active_branch = state.active_path[1] if len(state.active_path) > 1 else ""
        if active_branch == "TECHNICAL_ISSUE" or has_tech:
            if "ISSUE_NOT_RESOLVED" not in labels:
                labels.append("ISSUE_NOT_RESOLVED")
        elif active_branch == "MONTHLY_BILL" or has_pay:
            if "NOT_UPDATED" not in labels:
                labels.append("NOT_UPDATED")

    # RULE 2: COMPLAINT action
    actual_complaint = re.search(
        r"(?:කම්ප්ලේන්|කොම්ප්ලේන්).{0,20}(?:දාන්නම්|දාලා|දාපු|දාල|දැම්මා|යොමු\s*කරා|යොමු\s*කළා|යොමු\s*කරන්නම්|කරලා\s*තියෙනවා)",
        current, re.IGNORECASE
    ) or re.search(r"පැමිණිල්ල.{0,20}(?:යොමු|දාලා|කරලා|දැම්මා)", current, re.IGNORECASE)

    if actual_complaint and "COMPLAINT" not in labels:
        labels.append("COMPLAINT")

    # RULE 3: TECHNICAL_ESCALATION
    escalation_action = re.search(
        r"(?:තාක්ෂණික|කාර්මික|ටෙක්නිකල්|නඩත්තු).{0,25}(?:අංශ|section|team).{0,30}(?:යොමු|දැනුවත්|දැනුම්|චෙක්|පරීක්ෂා)",
        current, re.IGNORECASE
    ) or re.search(
        r"(?:කම්ප්ලේන්|කොම්ප්ලේන්|පැමිණිල්ල).{0,30}(?:කාර්මික|තාක්ෂණික|නඩත්තු).{0,30}(?:යොමු|දා|දාලා|කරලා)",
        current, re.IGNORECASE
    )

    if escalation_action and "TECHNICAL_ESCALATION" not in labels:
        labels.append("TECHNICAL_ESCALATION")

    return labels


def classify_sentence_with_state(sentences, index, state: ConversationState):
    current_sentence = sentences[index]
    labels = classify_sentence(current_sentence)

    if needs_context(current_sentence, labels):
        labels = apply_context_rules(current_sentence, state, labels)

    labels = resolve_label_conflicts(labels, state)
    
    # ENFORCE ROOT LOCK: Reject labels from other root branches
    labels = state.filter_labels_by_locked_root(labels)
    
    state.add_turn(current_sentence, labels)
    return labels


def get_present_nodes(transcript_text):
    state = ConversationState()
    present = set()
    sentences = split_into_sentences(transcript_text)

    for idx in range(len(sentences)):
        labels = classify_sentence_with_state(sentences, idx, state)
        for l in labels:
            present.add(l)
    return present


def compute_graph_frequencies(transcripts):
    counts = Counter()
    for t in transcripts:
        nodes = get_present_nodes(t)
        for node in nodes:
            counts[node] += 1
    return counts


def generate_test_report(transcripts):
    rows = []
    for transcript_number, transcript in enumerate(transcripts, 1):
        state = ConversationState()
        sentences = split_into_sentences(transcript)
        for index, sent in enumerate(sentences):
            labels = classify_sentence_with_state(sentences, index, state)
            rows.append({
                "Transcript": transcript_number,
                "Sentence": sent,
                "Detected Labels": ",".join(labels) if labels else "NONE",
                "Active Path": " -> ".join(state.active_path)
            })
    return rows