# -*- coding: utf-8 -*-

from pathlib import Path
import csv

from classifier import (
    compute_graph_frequencies,
    generate_test_report
)

from visualization import (
    build_tree_structure,
    save_tree_to_json
)

def load_transcripts():

    folder = Path("transcripts")

    transcripts = []

    for file in sorted(folder.glob("*.txt")):

        txt = file.read_text(
            encoding="utf-8"
        ).strip()

        if txt:
            transcripts.append(txt)

    return transcripts

def save_csv(rows):

    with open(
        "classification_results.csv",
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Transcript",
                "Sentence",
                "Detected Labels",
                "Active Path"
            ]
        )

        writer.writeheader()
        writer.writerows(rows)

def main():

    transcripts = load_transcripts()

    counts = compute_graph_frequencies(transcripts)

    tree = build_tree_structure(
        counts,
        len(transcripts)
    )

    save_tree_to_json(
        tree,
        "tree_structure.json"
    )

    rows = generate_test_report(transcripts)

    save_csv(rows)

    print("Completed.")

if __name__ == "__main__":
    main()