import json
import uuid
import time
from dictionary import HIERARCHY, SINHALA_LABELS

def create_node(node_key, count, children_nodes, node_id=None):
    """
    JSON Schema එකට අනුව Node එකක් සාදයි.
    """
    now_ms = int(time.time() * 1000)
    label = SINHALA_LABELS.get(node_key, node_key)
    topic_str = f"{label} ({count})"
    
    return {
        "id": node_id or str(uuid.uuid4()),
        "topic": topic_str,
        "children": children_nodes,
        "createdAt": now_ms,
        "modifiedAt": now_ms,
        "collapsed": False
    }

def build_tree_structure(counts, total_transcripts):
    """
    HIERARCHY dictionary එක පදනම් කරගෙන Parent-Child Hierarchy tree එක සාදයි.
    """
    # 1. Child-to-Parent සිතියම පදනම් කරගෙන Parent-to-Children adjacency list එකක් සෑදීම
    children_map = {}
    for child, parent in HIERARCHY.items():
        children_map.setdefault(parent, []).append(child)

    # 2. Recursive ශ්‍රිතයක් මගින් Tree එක පතුලේ සිට ඉහළට ගොඩනැගීම
    def build_node(node_key):
        child_keys = children_map.get(node_key, [])
        
        # Child nodes සාදයි
        child_objects = []
        sub_counts_sum = 0
        
        for ck in child_keys:
            child_node, child_count = build_node(ck)
            # Sub-category එකක් යටතේ counts තිබේ නම් පමණක් හෝ direct detect වී ඇත්නම් add කරයි
            if child_count > 0 or len(child_node["children"]) > 0:
                child_objects.append(child_node)
                sub_counts_sum += child_count

        # Node එකට අදාළ direct frequency count එක
        direct_count = counts.get(node_key, 0)
        total_node_count = direct_count + sub_counts_sum

        node_obj = create_node(
            node_key, 
            total_node_count, 
            child_objects, 
            node_id="root" if node_key == "ROOT_CENTER" else None
        )
        
        return node_obj, total_node_count

    # ROOT යටතේ ඇති ප්‍රධාන කණ්ඩායම් ලබා ගැනීම
    root_children_keys = children_map.get("ROOT", [])
    root_children_objects = []
    
    for rk in root_children_keys:
        r_node, r_count = build_node(rk)
        if r_count > 0 or len(r_node["children"]) > 0:
            root_children_objects.append(r_node)

    root_topic = f"{SINHALA_LABELS.get('ROOT_CENTER', 'Call Center Analytics')} ({total_transcripts})"
    
    root_node = {
        "id": "root",
        "topic": root_topic,
        "children": root_children_objects,
        "createdAt": int(time.time() * 1000),
        "modifiedAt": int(time.time() * 1000),
        "collapsed": False
    }

    return {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()),
        "title": root_topic,
        "root": root_node,
        "meta": {
            "source": "Call Center Analytics"
        }
    }

def save_tree_to_json(tree_data, filename="tree_structure.json"):
    """
    සිංහල අකුරු නිවැරදිව පෙන්වීමට ensure_ascii=False යොදා UTF-8 වලින් JSON එක save කරයි.
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)