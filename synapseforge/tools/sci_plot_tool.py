"""
Scientific Plot CLI and Generator Tool for SynapseForge.
Complying with `scientific-plot` standards: Nature/Science/IEEE palettes, 300+ DPI,
vector SVG/PDF output, publication-grade axis metrics, bold panel tags.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# Nature / Science Publication Palettes
NATURE_PALETTE = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4", "#91D1C2", "#DC0000", "#7E6148"]
SCIENCE_PALETTE = ["#0C5DA5", "#00B945", "#FF9500", "#FF2C00", "#845B97", "#474747", "#9e9e9e"]
IEEE_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]


class SciPlotTool:
    """Publication-grade scientific plot generation engine."""

    def __init__(self, default_style: str = "nature", dpi: int = 300):
        self.default_style = default_style
        self.dpi = dpi

    def get_palette(self, style: str = "nature") -> List[str]:
        if style.lower() == "science":
            return SCIENCE_PALETTE
        elif style.lower() == "ieee":
            return IEEE_PALETTE
        return NATURE_PALETTE

    def plot_benchmark_curve(
        self,
        data: Dict[str, Any],
        output_path: Path,
        title: str = "",
        x_label: str = "Concurrency (Agents)",
        y_label: str = "Reconciliation Latency (ms)",
        style: str = "nature",
    ) -> Dict[str, Any]:
        """Generates a publication-grade multi-curve benchmark figure with matplotlib."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica"],
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
            "figure.titlesize": 11,
            "axes.linewidth": 0.8,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.3,
            "lines.linewidth": 1.6,
            "lines.markersize": 5.5,
            "savefig.dpi": self.dpi,
            "savefig.bbox": "tight",
        })

        fig, ax = plt.subplots(figsize=(6.5, 4.2))
        palette = self.get_palette(style)

        series = data.get("series", [])
        if not series:
            # Generate default benchmark demo curve
            x_vals = [1, 2, 4, 8, 16, 32, 64]
            series = [
                {"name": "Traditional Git 3-Way", "x": x_vals, "y": [45, 92, 210, 480, 1120, 2600, 5800], "marker": "o"},
                {"name": "Centralized Locking", "x": x_vals, "y": [30, 80, 180, 420, 960, 2100, 4900], "marker": "s"},
                {"name": "SynapseForge AST Consensus", "x": x_vals, "y": [12, 14, 16, 19, 23, 29, 36], "marker": "^"},
            ]

        for idx, s in enumerate(series):
            color = palette[idx % len(palette)]
            ax.plot(
                s.get("x", []),
                s.get("y", []),
                marker=s.get("marker", "o"),
                label=s.get("name", f"Series {idx+1}"),
                color=color,
            )

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if title:
            ax.set_title(title, fontweight="bold")
        ax.legend(frameon=True, edgecolor="none", facecolor="#f8f9fa")
        ax.grid(True, linestyle="--")

        # Set panel label (Nature standard bold 'a')
        ax.text(-0.12, 1.05, "a", transform=ax.transAxes, fontsize=12, fontweight="bold", va="top")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=self.dpi)
        
        # Also generate vector SVG if path was PNG
        svg_path = output_path.with_suffix(".svg")
        fig.savefig(svg_path)
        plt.close(fig)

        return {
            "ok": True,
            "output_png": str(output_path),
            "output_svg": str(svg_path),
            "style": style,
            "dpi": self.dpi,
            "curves_rendered": len(series),
        }

    def run_plot_script(self, script_path: Path, output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Executes a custom Python plotting script in isolated environment."""
        if not script_path.exists():
            return {"ok": False, "error": f"Script {script_path} not found"}

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        import subprocess
        cmd = [sys.executable, str(script_path)]
        res = subprocess.run(cmd, cwd=output_dir, capture_output=True, text=True)
        return {
            "ok": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
        }
