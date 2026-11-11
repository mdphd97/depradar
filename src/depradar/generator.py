"""HTML Generator for DepRadar."""

import json
from pathlib import Path
from .models import GraphData

def generate_html(graph_data: GraphData, output_path: Path) -> Path:
    template_file = Path(__file__).parent / "templates" / "viewer.html"
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found at {template_file}")

    template_content = template_file.read_text(encoding="utf-8")
    json_str = json.dumps(graph_data.to_dict(), indent=2)

    rendered = template_content.replace("/* __GRAPH_DATA__ */ { \"nodes\": [], \"links\": [], \"metadata\": {} }", json_str)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path
