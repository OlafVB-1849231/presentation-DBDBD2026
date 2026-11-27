"""Create five charts per optimization: python plot_timings.py [CSV] [--output-dir DIR].

Each comparison gets its own subfolder with PDFs and a TXT range list.
PNG/SVG files in the output directory are removed after successful chart generation.
Edit COMPARISONS below to change columns, folder names, and inclusive condensed ranges.
Missing comparison columns are reported and skipped; unrelated timings are never substituted.
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl-timings")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

# Speedup = reference / candidate. Seconds saved = reference - candidate.
# Inclusive ranges chosen to collect modest gains and retain the larger gains individually.
COMPARISONS = [
    {"folder": "base_to_edge",
     "reference": "datafusion-Base", "candidate": "datafusion-Base-Edge",
     "condensed_range": (1.001, 1.043)},
    {"folder": "edge_to_aaj",
     "reference": "datafusion-Base-Edge", "candidate": "datafusion-Base-Edge-AAJ",
     "condensed_range": (1.001, 1.062)},
    {"folder": "aaj_to_parttc",
     "reference": "datafusion-Base-Edge-AAJ", "candidate": "datafusion-Base-Edge-AAJ-PartTC",
     "condensed_range": (1.001, 1.070)},
    {"folder": "base_to_edge_aaj_parttc",
     "reference": "datafusion-Base", "candidate": "datafusion-Base-Edge-AAJ-PartTC",
     "condensed_range": (1.001, 1.100)},
]


def save_chart(fig, directory, stem, pdf_metadata):
    fig.savefig(directory / f"{stem}.pdf", facecolor="white",
                bbox_inches="tight", pad_inches=0.04, metadata=pdf_metadata)
    plt.close(fig)


def plot_comparison(raw, source_name, output_root, config):
    reference, candidate = config["reference"], config["candidate"]
    lower, upper = config["condensed_range"]
    if not (np.isfinite(lower) and np.isfinite(upper) and 0 < lower < upper):
        raise ValueError(f"Invalid condensed range for {config['folder']}: {(lower, upper)}")
    valid = (raw[[reference, candidate]].notna().all(axis=1)
             & np.isfinite(raw[[reference, candidate]]).all(axis=1)
             & (raw[[reference, candidate]] > 0).all(axis=1))
    data = raw.loc[valid, ["Benchmarks", reference, candidate]].copy()
    if data.empty:
        print(f"SKIPPED {config['folder']}: no paired positive finite timings")
        return
    data["seconds_saved"] = data[reference] - data[candidate]
    data["speedup"] = data[reference] / data[candidate]
    data = data.sort_values("speedup", ascending=False).reset_index(drop=True)
    labels = data.Benchmarks.str.removeprefix("TC on ")
    n, excluded = len(data), len(raw) - len(data)
    output_dir = output_root / config["folder"]
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_label = reference.removeprefix("datafusion-").replace("-", "+")
    candidate_label = candidate.removeprefix("datafusion-").replace("-", "+")
    run_ids = "\n".join(raw.loc[valid, "Run"].astype(str))
    provenance = (
        f"Source: {source_name}. Exact CSV columns: '{reference}' (reference) and '{candidate}' (candidate), "
        "paired within the same benchmark row and Run ID. "
        "Speedup = T_reference / T_candidate; both timings are in seconds. "
        "1x means equal runtime, above 1x means the candidate is faster, below 1x means it is slower. "
        "Runtime saved (seconds) = T_reference - T_candidate; positive favors the candidate. "
        f"{n} paired positive finite timings included; {excluded} unavailable/invalid pairs excluded. "
        "Bar charts are sorted by decreasing speedup. Values use reported CSV timings without further aggregation. "
        "Repeat-level variability is unavailable.\nSource Run IDs:\n" + run_ids
    )

    def metadata(title, subject):
        return {"Title": f"{title}: {candidate_label} versus {reference_label}", "Subject": subject,
                "Keywords": f"DataFusion, {reference}, {candidate}, speedup, seconds saved",
                "Creator": "plot_timings.py (Matplotlib)"}

    # Match beamerthemeDSI.sty: Computer Modern Sans, UHred, UHblack, white.
    with plt.rc_context({"text.usetex": True, "font.family": "sans-serif",
                         "font.sans-serif": ["Computer Modern Sans Serif"],
                         "text.latex.preamble": r"\usepackage{sfmath}",
                         "text.color": "#1c1d1a", "axes.labelcolor": "#1c1d1a"}):
        fig, ax = plt.subplots(figsize=(16, 7), facecolor="white")
        fig.subplots_adjust(left=0.065, right=0.995, bottom=0.30, top=0.97)
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="both", length=0, labelcolor="#1c1d1a")
        ax.grid(axis="y", color="#e8e8e8", linewidth=0.6)
        ax.set_axisbelow(True)
        values = data.speedup.to_numpy()
        x = np.arange(n)
        bar_colors = np.where(values >= 1, "#e03c31", "#6b6c6a")
        ax.bar(x, values - 1, bottom=1, width=0.76, color=bar_colors, zorder=3)
        ax.axhline(1, color="#777875", linewidth=0.8)
        tex_labels = [label.replace("_", r"\_") for label in labels]
        ax.set_xticks(x, tex_labels, rotation=65, ha="right", fontsize=11)
        ax.set_xlim(-0.8, n - 0.2)
        ax.set_ylim(min(0.8, values.min() - 0.12), max(1.2, values.max() + 0.2))
        ax.set_ylabel(f"Speedup ({reference_label} / {candidate_label})", fontsize=15, labelpad=10)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: rf"{v:.1f}$\times$"))
        ax.tick_params(axis="y", labelsize=12)
        for xi, value, color in zip(x, values, bar_colors):
            ax.annotate(rf"{value:.3f}$\times$", (xi, value),
                        xytext=(0, 4 if value >= 1 else -4), textcoords="offset points",
                        ha="center", va="bottom" if value >= 1 else "top", rotation=90,
                        fontsize=9, color=color)
        save_chart(fig, output_dir, "edge_relative_improvement_vertical",
                   metadata("Runtime speedup", provenance +
                            " Individual bars extend from 1x to measured speedup; labels use three decimals."))
        # Condense small speedups into an interval, never an average or sum.
        lower, upper = config["condensed_range"]
        in_range = data.speedup.between(lower, upper, inclusive="both")
        grouped = data.loc[in_range]
        entries = []
        range_added = False
        for index, row in data.iterrows():
            if in_range.loc[index]:
                if not range_added:
                    entries.append((f"{len(grouped)} datasets", None))
                    range_added = True
            else:
                entries.append((row.Benchmarks.removeprefix("TC on "), row.speedup))
        fig, ax = plt.subplots(figsize=(16, 7), facecolor="white")
        fig.subplots_adjust(left=0.065, right=0.995, bottom=0.22, top=0.95)
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="both", length=0, labelcolor="#1c1d1a")
        ax.grid(axis="y", color="#e8e8e8", linewidth=0.6)
        ax.set_axisbelow(True)
        for xi, (label, speedup) in enumerate(entries):
            if speedup is None:
                ax.bar(xi, upper - lower, bottom=lower, width=0.76,
                       facecolor="#fce8e6", edgecolor="#a82b20", hatch="////",
                       linewidth=1.1, zorder=3)
                ax.hlines([lower, upper], xi - 0.47, xi + 0.47,
                          color="#a82b20", linewidth=1.5, zorder=4)
                ax.annotate(rf"{lower:.3f}--{upper:.3f}$\times$ range", (xi, upper),
                            xytext=(0, 8), textcoords="offset points", ha="center",
                            va="bottom", rotation=90, fontsize=10, color="#a82b20")
            else:
                color = "#e03c31" if speedup >= 1 else "#6b6c6a"
                ax.bar(xi, speedup - 1, bottom=1, width=0.76, color=color, zorder=3)
                ax.annotate(rf"{speedup:.3f}$\times$", (xi, speedup),
                            xytext=(0, 5 if speedup >= 1 else -5), textcoords="offset points",
                            ha="center", va="bottom" if speedup >= 1 else "top",
                            rotation=90, fontsize=10, color=color)
        ax.axhline(1, color="#777875", linewidth=0.8)
        ax.set_xticks(np.arange(len(entries)),
                      [label.replace("_", r"\_") for label, _ in entries],
                      rotation=55, ha="right", fontsize=12)
        ax.set_xlim(-0.8, len(entries) - 0.2)
        ax.set_ylim(min(0.8, values.min() - 0.12), max(1.25, values.max() + 0.18))
        ax.set_ylabel(f"Speedup ({reference_label} / {candidate_label})", fontsize=15, labelpad=10)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: rf"{v:.1f}$\times$"))
        ax.tick_params(axis="y", labelsize=12)
        group_labels = sorted(grouped.Benchmarks.str.removeprefix("TC on "))
        list_filename = "edge_speedup_condensed_datasets.txt"
        (output_dir / list_filename).write_text(
            "\n".join(group_labels) + "\n", encoding="utf-8"
        )
        save_chart(fig, output_dir, "edge_speedup_condensed_vertical", metadata(
            "Condensed runtime speedup",
            provenance + f" Speedups in the inclusive interval [{lower:.3f}, {upper:.3f}] "
            "are represented by one hatched interval bar spanning exactly those bounds, with caps on both ends. "
            "The range bar is not a mean, sum, or measured group speedup. "
            f"{len(grouped)} dataset names are listed separately in {list_filename}."))
        # One bar per dataset: absolute runtime difference, rather than paired runtimes.
        fig, ax = plt.subplots(figsize=(16, 7), facecolor="white")
        fig.subplots_adjust(left=0.065, right=0.995, bottom=0.30, top=0.97)
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="both", length=0, labelcolor="#1c1d1a")
        ax.grid(axis="y", color="#e8e8e8", linewidth=0.6)
        ax.set_axisbelow(True)
        differences = data.seconds_saved.to_numpy()
        diff_colors = np.where(differences >= 0, "#e03c31", "#6b6c6a")
        ax.bar(x, differences, width=0.76, color=diff_colors, zorder=3)
        ax.axhline(0, color="#777875", linewidth=0.8)
        ax.set_xticks(x, tex_labels, rotation=65, ha="right", fontsize=11)
        ax.set_xlim(-0.8, n - 0.2)
        ax.set_ylim(min(-0.4, differences.min() - 0.3), max(0.4, differences.max() + 0.4))
        ax.set_ylabel("Runtime saved (seconds)", fontsize=15, labelpad=10)
        ax.tick_params(axis="y", labelsize=12)
        for xi, value, color in zip(x, differences, diff_colors):
            ax.annotate(f"{value:+.3f}", (xi, value),
                        xytext=(0, 4 if value >= 0 else -4), textcoords="offset points",
                        ha="center", va="bottom" if value >= 0 else "top", rotation=90,
                        fontsize=9, color=color)
        save_chart(fig, output_dir, "edge_absolute_difference_vertical", metadata(
            "Absolute runtime difference", provenance +
            " One bar per dataset shows T_reference - T_candidate in seconds, with labels rounded to three decimals."))
        # Align speedup parity (1x) with zero seconds saved.
        fig, speed_ax = plt.subplots(figsize=(16, 7), facecolor="white")
        fig.subplots_adjust(left=0.065, right=0.93, bottom=0.30, top=0.91)
        sec_ax = speed_ax.twinx()
        speed_ax.set_facecolor("white")
        for axis in (speed_ax, sec_ax):
            for spine in axis.spines.values():
                spine.set_visible(False)
            axis.tick_params(axis="both", length=0, labelcolor="#1c1d1a")
        speed_ax.grid(axis="y", color="#e8e8e8", linewidth=0.6)
        speed_ax.set_axisbelow(True)
        speed_bars = speed_ax.bar(x - 0.20, values - 1, bottom=1, width=0.38, color="#e03c31",
                              label=r"Speedup ($\times$, left axis)", zorder=3)
        sec_bars = sec_ax.bar(x + 0.20, differences, width=0.38, color="#6b6c6a",
                              label="Runtime saved (seconds, right axis)", zorder=3)
        speed_span = max(0.1, (values.max() - 1) * 1.18)
        sec_top = max(0.001, differences.max() * 1.18)
        negative_fraction = max(0.12, (1 - values.min()) / speed_span * 1.25,
                                -differences.min() / sec_top * 1.25)
        speed_ax.set_ylim(1 - negative_fraction * speed_span, 1 + speed_span)
        sec_ax.set_ylim(-negative_fraction * sec_top, sec_top)
        speed_ax.axhline(1, color="#777875", linewidth=0.8)
        speed_ax.set_xticks(x, tex_labels, rotation=65, ha="right", fontsize=11)
        speed_ax.set_xlim(-0.8, n - 0.2)
        speed_ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: rf"{v:.1f}$\times$"))
        speed_ax.set_ylabel(f"Speedup ({reference_label} / {candidate_label})", color="#e03c31", fontsize=15, labelpad=10)
        sec_ax.set_ylabel("Runtime saved (seconds)", color="#6b6c6a", fontsize=15, labelpad=10)
        speed_ax.tick_params(axis="y", labelsize=12, labelcolor="#e03c31")
        sec_ax.tick_params(axis="y", labelsize=12, labelcolor="#6b6c6a")
        speed_ax.legend(handles=[speed_bars, sec_bars], loc="lower right",
                      bbox_to_anchor=(1, 1.02), frameon=False, ncol=2, fontsize=12)
        save_chart(fig, output_dir, "edge_relative_and_absolute_vertical", metadata(
            "Speedup and absolute runtime difference", provenance +
            " Red bars on the left axis show speedup; grey bars on the right axis show seconds saved. "
            "Both axes are linear with separate scales; 1x speedup aligns with zero seconds saved. "
            "Heights across the two metrics have different units and are not directly comparable."))

        # Identical logarithmic scales keep short and long queries visible together.
        fig, ax = plt.subplots(figsize=(8, 6.5), facecolor="white")
        fig.subplots_adjust(left=0.15, right=0.97, bottom=0.16, top=0.96)
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xscale("log")
        ax.set_yscale("log")
        runtime_values = data[[reference, candidate]].to_numpy()
        low, high = runtime_values.min() / 1.5, runtime_values.max() * 1.5
        ax.set_xlim(low, high)
        ax.set_ylim(low, high)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(which="major", color="#e8e8e8", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.plot([low, high], [low, high], color="#777875", linestyle="--",
                linewidth=1, label="Equal runtime", zorder=2)
        ax.scatter(data[reference], data[candidate], s=38, c=bar_colors,
                   edgecolors="white", linewidths=0.5, alpha=0.85, zorder=3)
        ax.set_xlabel(f"{reference_label} runtime (seconds)", fontsize=13, labelpad=10)
        ax.set_ylabel(f"{candidate_label} runtime (seconds)", fontsize=13, labelpad=10)
        ax.tick_params(axis="both", which="both", length=0, labelcolor="#1c1d1a", labelsize=11)
        ax.legend(loc="upper left", frameon=False, fontsize=11)
        save_chart(fig, output_dir, "runtime_scatter", metadata(
            "Runtime scatter plot", provenance +
            f" Each dot represents one dataset: x = {reference} runtime in seconds, "
            f"y = {candidate} runtime in seconds. Both axes use identical logarithmic scales "
            "and limits. The dashed y=x line marks equal runtime; points below it favor the candidate. "
            "Red points indicate candidate speedup >= 1x; grey points indicate regressions. "
            "No datasets are condensed or aggregated in this scatter plot."))
        # Show relative differences directly instead of compressing them near y=x.
        fig, ax = plt.subplots(figsize=(8, 6.5), facecolor="white")
        fig.subplots_adjust(left=0.15, right=0.97, bottom=0.16, top=0.96)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xscale("log")
        ax.set_ylim(min(0.95, data.speedup.min() - 0.04), data.speedup.max() + 0.08)
        ax.grid(which="major", color="#e8e8e8", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.axhline(1, color="#777875", linestyle="--", linewidth=1,
                   label="Equal runtime", zorder=2)
        ax.scatter(data[reference], data.speedup, s=38, c=bar_colors,
                   edgecolors="white", linewidths=0.5, alpha=0.85, zorder=3)
        ax.set_xlabel(f"{reference_label} runtime (seconds, log scale)", fontsize=13, labelpad=10)
        ax.set_ylabel(f"Speedup ({reference_label} / {candidate_label})", fontsize=13, labelpad=10)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.2f}x"))
        ax.tick_params(axis="both", which="both", length=0, labelsize=11)
        ax.legend(loc="upper left", frameon=False, fontsize=11)
        save_chart(fig, output_dir, "speedup_scatter", metadata(
            "Speedup scatter plot", provenance +
            " Each dataset is shown individually. X is reference runtime in seconds on a log scale; "
            "y is speedup on a linear scale. The dashed horizontal line at 1x marks equal runtime. "
            "Points above 1x favor the candidate. Red indicates speedup >= 1x, grey indicates regression."))
    grouped_count = data.speedup.between(lower, upper, inclusive="both").sum()
    print(f"{config['folder']}: {reference_label} / {candidate_label}; "
          f"{n} pairs, {int((data.speedup > 1).sum())} faster, "
          f"geometric mean {np.exp(np.log(data.speedup).mean()):.4f}x; "
          f"{grouped_count} condensed in [{lower:.3f}, {upper:.3f}]")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?", default=Path("timings.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("charts"))
    args = parser.parse_args()
    raw = pd.read_csv(args.csv)
    missing = {"Benchmarks", "Run"} - set(raw.columns)
    if missing:
        parser.error(f"Missing required columns: {sorted(missing)}")
    columns = {config[key] for config in COMPARISONS for key in ("reference", "candidate")}
    for column in columns & set(raw.columns):
        raw[column] = pd.to_numeric(
            raw[column].astype(str).str.strip().str.replace(r"\s*s$", "", regex=True),
            errors="coerce")
    plt.rcParams.update({"font.size": 10, "pdf.fonttype": 42})
    for config in COMPARISONS:
        missing = {config["reference"], config["candidate"]} - set(raw.columns)
        if missing:
            print(f"SKIPPED {config['folder']}: missing CSV column(s): {', '.join(sorted(missing))}")
            continue
        plot_comparison(raw, args.csv.name, args.output_dir, config)
    removed = 0
    if args.output_dir.is_dir():
        for path in args.output_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".svg"}:
                path.unlink()
                removed += 1
    if removed:
        print(f"Removed {removed} PNG/SVG files; charts are exported as PDF only.")
    print(f"Output directory: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
