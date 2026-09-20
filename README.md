# Carbon Project Collaborator Data Enrichment

**Prepared by:** Ee Hann
**Scope:** Southeast Asian Hard-Tail Carbon Collaborator Enrichment (CDM, JCM, GCC)
**Main Deliverable:** `ds-intern-collaborator-enrichment-final.csv`

---

## Overview

This repository contains a two-stage data pipeline designed to identify, normalize, and enrich carbon project developers and third-party verification bodies (VVBs) across un-aggregated Southeast Asian carbon registry records.

* **Stage 1 (`1.full_enrichment_pipeline.py`):** Cross-references project titles against official Institute for Global Environmental Strategies (IGES) master databases (covering 12,000+ CDM and JCM projects) to resolve official entity names and countries, then queries Google via Serper.dev API to index digital footprints (websites, LinkedIn profiles, and public search snippets).
* **Stage 2 (`2.enrichment_cleaner_pipeline.py`):** Standardizes canonical entity names and headquarters countries, normalizes diplomatic country aliases (e.g., Vietnam vs. Viet Nam) to isolate genuine cross-border developers, derives corporate domain inquiry emails (`info@domain`), and filters out aggregator/news domains to ensure data integrity.

---

## Quick Start / How to Run

### 1. Prerequisites

Install the required Python dependencies:

```bash
pip install pandas openpyxl requests
```

### 2. File Requirements

Ensure the following files are present in the working directory:

* `ds-intern-collaborator-enrichment.csv` *(Original input dataset)*
* `IGES_CDM_DB_v13.7_20250226.xlsx` *(Official IGES CDM master file), stored in "iges-registry-data" folder*
* `IGES_JCM_Database_20241029.xlsx` *(Official IGES JCM master file), stored in "iges-registry-data" folder*
* `1.full_enrichment_pipeline.py`
* `2.enrichment_cleaner_pipeline.py`

*(Note: If re-executing Stage 1 search queries, set your Serper API key at the top of `1.full_enrichment_pipeline.py`.)*

### 3. Execution Instruction

Execute the entire pipeline in sequence with the single command:

```bash
python 1.full_enrichment_pipeline.py; python 2.enrichment_cleaner_pipeline.py;
```

*(On Windows Command Prompt, use `&` instead of `;`: `python 1.full_enrichment_pipeline.py & python 2.enrichment_cleaner_pipeline.py`)*

---

## Expected Pipeline Outputs

* `ds-intern-collaborator-enrichment-resolved.csv`: Intermediate dataset generated after Stage 1 registry matching and web search.
* `ds-intern-collaborator-enrichment-final.csv`: Final cleaned and enriched dataset containing canonical entity names, verified countries, organization types, digital footprints, and corporate inquiry contacts.

---

## Key Results

* **Total Rows Processed:** 597
* **Verifiers (VVBs) Resolved:** 297 / 297 (100.0%)
* **Developers Resolved:** 280 / 300 (93.3%)
* **Overall Resolution Rate:** 577 / 597 (96.6%)
* **Contact Emails Populated:** 537 / 597 (89.9%)
* **Genuine Foreign Entities Flagged:** 4
* **Unresolved Long-Tail Left Blank:** 20 rows (deliberately omitted with audit notes to maintain precision over volume)
