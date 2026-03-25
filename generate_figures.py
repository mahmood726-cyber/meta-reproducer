"""Generate 4 figures for MetaReproducer BMJ manuscript."""
import csv, json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), 'figures')
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(os.path.dirname(__file__), 'data', 'results', 'summary_table.csv'), encoding='utf-8') as f:
    reviews = list(csv.DictReader(f))

for r in reviews:
    r['k'] = int(r['total_k'])
    r['pdf'] = int(r['n_with_pdf'])
    r['strict'] = int(r['matched_strict'])
    r['mod'] = int(r['matched_moderate'])
    r['cov'] = r['pdf'] / r['k'] if r['k'] > 0 else 0

TIER_COLORS = {'reproduced': '#2ecc71', 'minor_discrepancy': '#f39c12',
               'major_discrepancy': '#e74c3c', 'insufficient': '#bdc3c7'}

# ── FIGURE 1: OA Coverage Distribution ──
print("Figure 1: OA coverage...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

# Left: pie of accessible vs not
total_k = sum(r['k'] for r in reviews)
total_pdf = sum(r['pdf'] for r in reviews)
ax1.pie([total_pdf, total_k - total_pdf],
        labels=[f'Open Access\n{total_pdf} ({total_pdf/total_k*100:.1f}%)',
                f'Not Accessible\n{total_k-total_pdf} ({(total_k-total_pdf)/total_k*100:.1f}%)'],
        colors=['#2ecc71', '#e74c3c'], startangle=90, autopct='', textprops={'fontsize': 11},
        explode=(0.05, 0))
ax1.set_title(f'Open Access Coverage\n({total_k:,} studies across 501 reviews)', fontsize=12)

# Right: histogram of per-review coverage
covs = [r['cov'] * 100 for r in reviews]
ax2.hist(covs, bins=np.arange(0, 105, 5), color='#3498db', edgecolor='white')
ax2.axvline(x=30, color='#e74c3c', linestyle='--', linewidth=1.5, label='30% threshold')
n_above = sum(1 for c in covs if c >= 30)
ax2.text(32, ax2.get_ylim()[1] * 0.9 if ax2.get_ylim()[1] > 0 else 50,
         f'{n_above} reviews\n>=30%', fontsize=9, color='#e74c3c')
ax2.set_xlabel('Open Access Coverage (%)', fontsize=11)
ax2.set_ylabel('Number of Reviews', fontsize=11)
ax2.set_title('Distribution of Per-Review OA Coverage', fontsize=12)
ax2.legend(fontsize=9)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

plt.tight_layout()
fig.savefig(os.path.join(OUT, 'figure1_oa_coverage.png'), dpi=300, bbox_inches='tight')
fig.savefig(os.path.join(OUT, 'figure1_oa_coverage.pdf'), bbox_inches='tight')
print("  Saved")
plt.close(fig)

# ── FIGURE 2: Review Classification ──
print("Figure 2: Classification...")
from collections import Counter
tiers = Counter(r['review_tier'] for r in reviews)
fig, ax = plt.subplots(figsize=(7, 5))
cats = ['reproduced', 'minor_discrepancy', 'major_discrepancy', 'insufficient']
labels = ['Reproduced', 'Minor\nDiscrepancy', 'Major\nDiscrepancy', 'Insufficient\nCoverage']
counts = [tiers.get(c, 0) for c in cats]
colors = [TIER_COLORS[c] for c in cats]
bars = ax.bar(range(4), counts, color=colors, edgecolor='white', width=0.65)
for bar, count in zip(bars, counts):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
            f'{count}\n({count/501*100:.1f}%)', ha='center', fontsize=10, fontweight='bold')
ax.set_xticks(range(4))
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylabel('Number of Reviews', fontsize=11)
ax.set_title('Review-Level Reproducibility Classification (501 Reviews)', fontsize=12, pad=10)
ax.set_ylim(0, max(counts) * 1.15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT, 'figure2_classification.png'), dpi=300, bbox_inches='tight')
fig.savefig(os.path.join(OUT, 'figure2_classification.pdf'), bbox_inches='tight')
print("  Saved")
plt.close(fig)

# ── FIGURE 3: Coverage vs Match Rate Scatter ──
print("Figure 3: Coverage vs match rate...")
fig, ax = plt.subplots(figsize=(8, 6))
with_pdf = [r for r in reviews if r['pdf'] > 0]
covs_scatter = [r['cov'] * 100 for r in with_pdf]
match_rates = [r['strict'] / r['pdf'] * 100 if r['pdf'] > 0 else 0 for r in with_pdf]
colors_scatter = [TIER_COLORS[r['review_tier']] for r in with_pdf]
sizes = [max(10, min(100, r['k'] * 2)) for r in with_pdf]

ax.scatter(covs_scatter, match_rates, c=colors_scatter, s=sizes, alpha=0.6, edgecolors='white', linewidth=0.3)
ax.axvline(x=30, color='#e74c3c', linestyle='--', linewidth=1, alpha=0.5, label='30% coverage threshold')
ax.set_xlabel('Open Access Coverage (%)', fontsize=11)
ax.set_ylabel('Strict Match Rate (%)', fontsize=11)
ax.set_title('Per-Review: Coverage vs Match Rate\n(dot size = number of studies)', fontsize=12, pad=10)
patches = [mpatches.Patch(color=c, label=l) for l, c in
           [('Reproduced', '#2ecc71'), ('Minor disc.', '#f39c12'),
            ('Major disc.', '#e74c3c'), ('Insufficient', '#bdc3c7')]]
ax.legend(handles=patches, loc='upper right', fontsize=9)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT, 'figure3_coverage_vs_match.png'), dpi=300, bbox_inches='tight')
fig.savefig(os.path.join(OUT, 'figure3_coverage_vs_match.pdf'), bbox_inches='tight')
print("  Saved")
plt.close(fig)

# ── FIGURE 4: Barrier Decomposition ──
print("Figure 4: Barrier decomposition...")
fig, ax = plt.subplots(figsize=(7, 5))
barriers = ['No OA PDF\navailable', 'PDF found but\nno effect extracted', 'Effect extracted\nbut no match',
            'Moderate match\n(within 10%)', 'Strict match\n(within 5%)']
total_studies = sum(r['k'] for r in reviews)
total_pdf_count = sum(r['pdf'] for r in reviews)
total_mod = sum(r['mod'] for r in reviews)
total_strict = sum(r['strict'] for r in reviews)

# Compute stages
no_pdf = total_studies - total_pdf_count
no_extract = total_pdf_count - total_mod  # PDF but no match at all
mod_only = total_mod - total_strict
strict_count = total_strict

vals = [no_pdf, no_extract, 0, mod_only, strict_count]  # placeholder for no-extract vs no-match
# Actually: PDF available = total_pdf_count, of which matched_moderate, of which matched_strict
# no_extract = pdf - moderate_match
vals = [no_pdf, total_pdf_count - total_mod, total_mod - total_strict, 0, total_strict]
labels_bar = [f'No PDF\n{no_pdf:,}', f'No match\n{total_pdf_count-total_mod:,}',
              f'Moderate only\n{total_mod-total_strict:,}', '', f'Strict\n{total_strict}']
colors_bar = ['#e74c3c', '#e67e22', '#f1c40f', '#95a5a6', '#2ecc71']

# Stacked horizontal bar
cumsum = 0
for val, color, label in zip(vals, colors_bar, labels_bar):
    if val > 0:
        ax.barh(0, val, left=cumsum, color=color, edgecolor='white', height=0.5)
        if val > 300:
            ax.text(cumsum + val/2, 0, label, ha='center', va='center', fontsize=8, fontweight='bold')
        cumsum += val

ax.set_xlim(0, total_studies)
ax.set_yticks([])
ax.set_xlabel(f'Studies (n={total_studies:,})', fontsize=11)
ax.set_title('The Reproducibility Funnel: Where Studies Are Lost', fontsize=12, pad=10)

patches_bar = [mpatches.Patch(color=c, label=f'{l.split(chr(10))[0]}: {v:,} ({v/total_studies*100:.1f}%)')
               for v, c, l in zip(vals, colors_bar, labels_bar) if v > 0]
ax.legend(handles=patches_bar, loc='upper right', fontsize=8, framealpha=0.9)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT, 'figure4_barrier_funnel.png'), dpi=300, bbox_inches='tight')
fig.savefig(os.path.join(OUT, 'figure4_barrier_funnel.pdf'), bbox_inches='tight')
print("  Saved")
plt.close(fig)

print(f"\nAll figures in {OUT}/:")
for f in sorted(os.listdir(OUT)):
    print(f"  {f} ({os.path.getsize(os.path.join(OUT, f))/1024:.0f} KB)")
