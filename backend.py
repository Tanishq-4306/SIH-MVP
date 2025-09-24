from flask import Flask, jsonify
import pandas as pd
import json
from typing import Dict, Optional, Tuple


app = Flask(__name__)


def _load_network() -> Dict:
    with open("network.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _load_trains() -> pd.DataFrame:
    return pd.read_csv("trains.csv")


def _build_station_to_edge_map(network: Dict) -> Dict[str, str]:
    # Build adjacency and map stations with degree 1 to their single connected edge id
    adjacency: Dict[str, list[Tuple[str, str]]] = {}
    for edge in network.get("edges", []):
        from_node = edge.get("from")
        to_node = edge.get("to")
        edge_id = edge.get("id")
        adjacency.setdefault(from_node, []).append((to_node, edge_id))
        adjacency.setdefault(to_node, []).append((from_node, edge_id))

    station_to_edge: Dict[str, str] = {}
    for node in network.get("nodes", []):
        node_id = node.get("id")
        neighbors = adjacency.get(node_id, [])
        if len(neighbors) == 1:
            # Degree-1 station: assume being at the station implies occupying its single connecting edge
            station_to_edge[node_id] = neighbors[0][1]
    return station_to_edge


@app.get("/api/optimize")
def optimize():
    network = _load_network()
    trains_df = _load_trains()

    node_id_to_name: Dict[str, str] = {n.get("id"): n.get("name", n.get("id")) for n in network.get("nodes", [])}
    station_to_edge = _build_station_to_edge_map(network)

    def get_recommendations() -> Dict:
        # Expecting at least two trains for a simple pairwise check
        if len(trains_df) < 2:
            return {"status": "No conflicts found."}

        # Consider the first two trains (extendable for more complex logic)
        t1 = trains_df.iloc[0]
        t2 = trains_df.iloc[1]

        t1_location = str(t1.get("current_location"))
        t2_location = str(t2.get("current_location"))

        # Map station locations to their single connecting edge (if any)
        t1_edge: Optional[str] = station_to_edge.get(t1_location)
        t2_edge: Optional[str] = station_to_edge.get(t2_location)

        # Conflict if both are on the same track segment
        if t1_edge is not None and t1_edge == t2_edge:
            # Higher priority value means higher priority
            t1_priority = int(t1.get("priority", 0))
            t2_priority = int(t2.get("priority", 0))

            if t1_priority == t2_priority:
                # Same priority: simple fallback — no recommendation
                return {"status": "No conflicts found."}

            # Determine which train to hold (lower priority value)
            hold_train, pass_train = (t1, t2) if t1_priority < t2_priority else (t2, t1)

            hold_train_id = str(hold_train.get("train_id"))
            hold_train_type = str(hold_train.get("train_type"))
            hold_location_id = str(hold_train.get("current_location"))
            hold_location_name = node_id_to_name.get(hold_location_id, hold_location_id)

            pass_train_id = str(pass_train.get("train_id"))
            pass_train_type = str(pass_train.get("train_type"))

            recommendation = (
                f"Hold Train {hold_train_id} ({hold_train_type}) at {hold_location_name} "
                f"to let Train {pass_train_id} ({pass_train_type}) pass."
            )
            return {"recommendation": recommendation}

        return {"status": "No conflicts found."}

    result = get_recommendations()
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)


