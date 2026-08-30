import json
import re
import time
import pandas as pd
import requests
import os
from dotenv import load_dotenv

load_dotenv()
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

if not SERPER_API_KEY:
    raise ValueError("API Key not found. Please check your .env file.")

INPUT_CSV = "ds-intern-collaborator-enrichment.csv"
OUTPUT_CSV = "enrichment-output.csv"


def clean_org_name(name):
    """Normalize raw organization strings for clustering and searching."""
    if not isinstance(name, str) or not name.strip():
        return ""
    # Remove common clutter and excess whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def query_serper(query, num_results=3):
    """Perform a Google search via Serper.dev API."""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": num_results}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error querying Serper for '{query}': {e}")
    return {}


def enrich_organization(org_name, country):
    """Resolve website, LinkedIn, and public contact information via search."""
    if not org_name:
        return {}

    # 1. Search for official website
    web_query = f"{org_name} {country} official website"
    web_res = query_serper(web_query, num_results=3)

    website = ""
    source_url = ""
    if "organic" in web_res and len(web_res["organic"]) > 0:
        first_hit = web_res["organic"][0]
        website = first_hit.get("link", "")
        source_url = website

    # 2. Search for LinkedIn Company Page
    li_query = f'site:linkedin.com/company "{org_name}"'
    li_res = query_serper(li_query, num_results=1)

    linkedin = ""
    if "organic" in li_res and len(li_res["organic"]) > 0:
        candidate = li_res["organic"][0].get("link", "")
        if "linkedin.com/company" in candidate:
            linkedin = candidate
            if not source_url:
                source_url = linkedin

    # 3. Baseline confidence heuristic
    confidence = 0.0
    notes = []

    if website and linkedin:
        confidence = 0.85
        notes.append("Automated match: found both official website and LinkedIn.")
    elif website:
        confidence = 0.65
        notes.append("Automated match: found website only.")
    elif linkedin:
        confidence = 0.60
        notes.append("Automated match: found LinkedIn only.")
    else:
        notes.append("No authoritative web presence found via search.")

    return {
        "company_name_resolved": org_name,
        "company_country": country,
        "website": website,
        "linkedin": linkedin,
        "contact_name": "",  # To be reviewed in manual audit or filled via info@
        "contact_role": "",
        "contact_email": "",
        "confidence": confidence,
        "source_url": source_url,
        "notes": "; ".join(notes),
    }


def main():
    print(f"Loading input data from {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)

    # Clean raw string
    df["org_name_cleaned"] = df["org_name_raw"].apply(clean_org_name)

    # Deduplicate unique (org_name, country) pairs
    unique_entities = (
        df[["org_name_cleaned", "country"]]
        .drop_duplicates()
        .dropna(subset=["org_name_cleaned"])
    )
    print(f"Found {len(df)} total rows across {len(unique_entities)} unique entities.")

    # Query Serper for each unique entity
    cache = {}
    for idx, row in unique_entities.iterrows():
        org = row["org_name_cleaned"]
        country = row["country"]

        print(f"Enriching: {org} ({country})...")
        enriched_data = enrich_organization(org, country)
        cache[(org, country)] = enriched_data
        time.sleep(0.2)  # Respect rate limits

    # Map enriched data back to original dataframe
    for idx, row in df.iterrows():
        key = (row["org_name_cleaned"], row["country"])
        if key in cache:
            item = cache[key]
            for field in [
                "company_name_resolved",
                "company_country",
                "website",
                "linkedin",
                "contact_name",
                "contact_role",
                "contact_email",
                "confidence",
                "source_url",
                "notes",
            ]:
                # Only populate if currently blank/null
                if pd.isna(df.at[idx, field]) or df.at[idx, field] == "":
                    df.at[idx, field] = item.get(field, "")

    # Drop temporary cleaning column and export
    df.drop(columns=["org_name_cleaned"], inplace=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Pipeline complete! Output saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()