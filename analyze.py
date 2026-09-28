"""
analyze.py
----------
Reads the newest scrape in data/ and produces:
  - analysis/price_by_brand.png
  - analysis/price_distribution.png
  - analysis/top_discounts.png
  - analysis/summary.md

Usage:
    py scraper.py     # collect data first
    py analyze.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save charts to files, no pop-up window
import matplotlib.pyplot as plt
import pandas as pd

DATA_DIR = Path("data")
OUT_DIR = Path("analysis")


def load_latest() -> tuple[pd.DataFrame, Path]:
    files = sorted(DATA_DIR.glob("jumia_smartphones_*.csv"))
    if not files:
        raise SystemExit("No data found. Run `py scraper.py` first.")
    path = files[-1]
    return pd.read_csv(path, encoding="utf-8-sig"), path


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["price_ksh"]).copy()
    df["brand"] = df["name"].str.split().str[0].str.title()
    # '13%' -> 13 ; 'No discount' -> 0
    df["discount_pct"] = (
        df["discount"].astype(str).str.extract(r"(\d+)")[0].astype(float).fillna(0)
    )
    return df


def chart_price_by_brand(df: pd.DataFrame) -> None:
    top = df["brand"].value_counts().head(10).index
    stats = (
        df[df["brand"].isin(top)]
        .groupby("brand")["price_ksh"]
        .agg(["mean", "count"])
        .sort_values("mean")
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(stats.index, stats["mean"], color="#2b6cb0")
    for bar, n in zip(bars, stats["count"]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  n={n}", va="center", fontsize=9)
    ax.set_title("Average price by brand (top 10 brands by listings)")
    ax.set_xlabel("Average price (KSh)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "price_by_brand.png", dpi=150)
    plt.close(fig)


def chart_price_distribution(df: pd.DataFrame) -> None:
    median = df["price_ksh"].median()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(df["price_ksh"], bins=20, color="#38a169", edgecolor="white")
    ax.axvline(median, color="red", linestyle="--", label=f"Median: KSh {median:,.0f}")
    ax.set_title("Smartphone price distribution")
    ax.set_xlabel("Price (KSh)")
    ax.set_ylabel("Number of phones")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "price_distribution.png", dpi=150)
    plt.close(fig)


def chart_top_discounts(df: pd.DataFrame) -> None:
    top = df.nlargest(10, "discount_pct").sort_values("discount_pct")
    labels = top["name"].str.slice(0, 40)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(labels, top["discount_pct"], color="#dd6b20")
    ax.set_title("Top 10 discounts")
    ax.set_xlabel("Discount (%)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "top_discounts.png", dpi=150)
    plt.close(fig)


def write_summary(df: pd.DataFrame, source: Path) -> str:
    cheapest = df.loc[df["price_ksh"].idxmin()]
    priciest = df.loc[df["price_ksh"].idxmax()]
    best = df.loc[df["discount_pct"].idxmax()]
    discounted = df[df["discount_pct"] > 0]
    top_brand = df["brand"].value_counts().idxmax()

    text = f"""# Jumia Kenya smartphones - summary

Source file: `{source.name}`

- Phones analysed: **{len(df)}**
- Median price: **KSh {df['price_ksh'].median():,.0f}**
- Average price: **KSh {df['price_ksh'].mean():,.0f}**
- Cheapest: {cheapest['name']} (KSh {cheapest['price_ksh']:,.0f})
- Most expensive: {priciest['name']} (KSh {priciest['price_ksh']:,.0f})
- Phones on discount: **{len(discounted)}** ({len(discounted) / len(df):.0%})
- Average discount (discounted phones): **{discounted['discount_pct'].mean() if len(discounted) else 0:.0f}%**
- Biggest discount: {best['name']} ({best['discount_pct']:.0f}% off)
- Most listed brand: **{top_brand}**
"""
    (OUT_DIR / "summary.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    df, source = load_latest()
    df = clean(df)
    chart_price_by_brand(df)
    chart_price_distribution(df)
    chart_top_discounts(df)
    print(write_summary(df, source))
    print(f"Charts saved in the '{OUT_DIR}' folder.")


if __name__ == "__main__":
    main()