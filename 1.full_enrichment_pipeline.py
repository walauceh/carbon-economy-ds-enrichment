import json
import os
import re
import time
import pandas as pd
import requests
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION & FILE PATHS    
# ==========================================
load_dotenv()
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

INPUT_CSV = "ds-intern-collaborator-enrichment.csv"
OUTPUT_CSV = "ds-intern-collaborator-enrichment-resolved.csv"
CDM_EXCEL = "./iges-registry-data/IGES_CDM_DB_v13.7_20250226.xlsx"
JCM_EXCEL = "./iges-registry-data/IGES_JCM_Database_20241029.xlsx"


# ==========================================
# HELPER FUNCTIONS
# ==========================================
def normalize_str(text):
    """Normalize strings for fuzzy and clean title matching."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def query_serper(query, num_results=3):
    """Perform a Google search using Serper.dev API."""
    if not SERPER_API_KEY or "YOUR_SERPER" in SERPER_API_KEY:
        return {}

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = json.dumps({"q": query, "num": num_results})

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error querying Serper for '{query}': {e}")
    return {}


def search_web_and_linkedin(company_name, country):
    """Fetch website, linkedin, and public snippets using Serper."""
    if not company_name:
        return {"website": "", "linkedin": "", "source_url": ""}

    # 1. Search for official website
    web_res = query_serper(f"{company_name} {country} official website", num_results=3)
    website = ""
    source_url = ""

    if "organic" in web_res and len(web_res["organic"]) > 0:
        first_hit = web_res["organic"][0]
        website = first_hit.get("link", "")
        source_url = website

    # 2. Search for LinkedIn company page
    li_res = query_serper(f'site:linkedin.com/company "{company_name}"', num_results=1)
    linkedin = ""
    if "organic" in li_res and len(li_res["organic"]) > 0:
        cand = li_res["organic"][0].get("link", "")
        if "linkedin.com/company" in cand:
            linkedin = cand
            if not source_url:
                source_url = linkedin

    return {"website": website, "linkedin": linkedin, "source_url": source_url}


# ==========================================
# MAIN EXECUTION PIPELINE
# ==========================================
def main():
    print(f"[*] Step 1/4: Loading input dataset: {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    df["norm_project_name"] = df["project_name"].apply(normalize_str)

    # Ensure required target columns exist
    target_columns = [
        "company_name_resolved", "company_country", "org_type", 
        "website", "linkedin", "contact_name", "contact_role", 
        "contact_email", "confidence", "source_url", "notes"
    ]
    for col in target_columns:
        if col not in df.columns:
            df[col] = ""

    # --------------------------------------------------
    # Step 2: Ingest Registry Data (IGES CDM & JCM)
    # --------------------------------------------------
    print(f"[*] Step 2/4: Loading IGES CDM and JCM Master Databases...")
    
    # Ingest CDM
    cdm_dict = {}
    if os.path.exists(CDM_EXCEL):
        cdm_df = pd.read_excel(CDM_EXCEL, sheet_name="AllProjects", skiprows=1)
        cdm_df["norm_title"] = cdm_df["Name of CDM Project Activity"].astype(str).apply(normalize_str)
        for _, r in cdm_df.iterrows():
            t = r["norm_title"]
            if t:
                cdm_dict[t] = {
                    "ref": str(r.get("CDM-EB Ref", "")),
                    "host_party": str(r.get("Host Party", "")),
                    "participants_host": str(r.get("Project Participants \n(Authorized by Host Party)", "")),
                    "participants_other": str(r.get("Project Participants \n(Authorized by other Parties involved)", "")),
                    "validator": str(r.get("Validator", ""))
                }
    else:
        print(f"Warning: {CDM_EXCEL} not found. Skipping CDM matching.")

    # Ingest JCM
    jcm_dict = {}
    if os.path.exists(JCM_EXCEL):
        jcm_df = pd.read_excel(JCM_EXCEL, sheet_name="Project Data", skiprows=3)
        jcm_df["norm_title"] = jcm_df["Title"].astype(str).apply(normalize_str)
        for _, r in jcm_df.iterrows():
            t = r["norm_title"]
            if t:
                jcm_dict[t] = {
                    "ref": str(r.get("Project reference number", "")),
                    "host_country": str(r.get("Host Country", "")),
                    "host_partner": str(r.get("Participant (Host Country)", "")),
                    "japan_partner": str(r.get("Participant (Japan)", "")),
                    "tpe": str(r.get("TPE", ""))
                }
    else:
        print(f"Warning: {JCM_EXCEL} not found. Skipping JCM matching.")

    # --------------------------------------------------
    # Step 3: Match Entities with Official Registries
    # --------------------------------------------------
    print("[*] Step 3/4: Resolving organizations via Registry Ground Truth...")
    for idx, row in df.iterrows():
        proj_norm = row["norm_project_name"]
        role = str(row.get("role", "")).lower()

        # Match CDM
        if proj_norm in cdm_dict:
            rec = cdm_dict[proj_norm]
            if "verifier" in role or "vvb" in role:
                df.at[idx, "company_name_resolved"] = rec["validator"]
                df.at[idx, "org_type"] = "certification body"
                df.at[idx, "confidence"] = 0.95
                df.at[idx, "source_url"] = f"https://cdm.unfccc.int/Projects/DB/ (Ref: {rec['ref']})"
                df.at[idx, "notes"] = f"Matched via IGES CDM DB (Ref: {rec['ref']}). Validated DOE."
            else:
                proponent = rec["participants_host"] if rec["participants_host"] != "nan" else rec["participants_other"]
                primary_prop = proponent.split(";")[0].strip() if proponent else ""
                df.at[idx, "company_name_resolved"] = primary_prop or row["org_name_raw"]
                df.at[idx, "company_country"] = rec["host_party"]
                df.at[idx, "org_type"] = "private company"
                df.at[idx, "confidence"] = 0.90
                df.at[idx, "source_url"] = f"https://cdm.unfccc.int/Projects/DB/ (Ref: {rec['ref']})"
                df.at[idx, "notes"] = f"Matched via IGES CDM DB (Ref: {rec['ref']})."

        # Match JCM
        elif proj_norm in jcm_dict:
            rec = jcm_dict[proj_norm]
            if "verifier" in role or "vvb" in role:
                df.at[idx, "company_name_resolved"] = rec["tpe"]
                df.at[idx, "org_type"] = "certification body"
                df.at[idx, "confidence"] = 0.95
                df.at[idx, "source_url"] = f"https://www.jcm.go.jp/projects/{rec['ref']}"
                df.at[idx, "notes"] = f"Matched via IGES JCM DB (Ref: {rec['ref']}). Designated TPE."
            else:
                partner = rec["host_partner"] if rec["host_partner"] != "nan" else rec["japan_partner"]
                primary_part = partner.split(",")[0].strip() if partner else ""
                df.at[idx, "company_name_resolved"] = primary_part or row["org_name_raw"]
                df.at[idx, "company_country"] = rec["host_country"]
                df.at[idx, "org_type"] = "private company"
                df.at[idx, "confidence"] = 0.90
                df.at[idx, "source_url"] = f"https://www.jcm.go.jp/projects/{rec['ref']}"
                df.at[idx, "notes"] = f"Matched via IGES JCM DB (Ref: {rec['ref']})."

        # Fallback for entities not present in CDM/JCM (e.g., GCC or others)
        else:
            if not df.at[idx, "company_name_resolved"]:
                df.at[idx, "company_name_resolved"] = row["org_name_raw"]
                df.at[idx, "company_country"] = row.get("country", "")
                df.at[idx, "confidence"] = 0.50
                df.at[idx, "notes"] = "Unmatched in CDM/JCM master records; using raw entity name."

    # --------------------------------------------------
    # Step 4: Web & LinkedIn Enrichment via Serper
    # --------------------------------------------------
    print("[*] Step 4/4: Enriching digital footprint (Website, LinkedIn) via Serper.dev...")
    # Deduplicate unique companies to minimize API credits
    unique_entities = (
        df[["company_name_resolved", "company_country"]]
        .drop_duplicates()
        .dropna(subset=["company_name_resolved"])
    )
    print(f"[*] Found {len(unique_entities)} unique companies to search.")

    serper_cache = {}
    for _, r in unique_entities.iterrows():
        c_name = str(r["company_name_resolved"]).strip()
        c_country = str(r["company_country"]).strip()
        if c_name:
            print(f"    Searching web footprint for: {c_name}...")
            res = search_web_and_linkedin(c_name, c_country)
            serper_cache[(c_name, c_country)] = res
            time.sleep(0.2)  # avoid rate limits

    # Map search results back to main dataframe
    for idx, row in df.iterrows():
        key = (str(row["company_name_resolved"]).strip(), str(row["company_country"]).strip())
        if key in serper_cache:
            hit = serper_cache[key]
            if hit["website"]:
                df.at[idx, "website"] = hit["website"]
            if hit["linkedin"]:
                df.at[idx, "linkedin"] = hit["linkedin"]
            # If source_url was still empty, populate from search
            if not df.at[idx, "source_url"] and hit["source_url"]:
                df.at[idx, "source_url"] = hit["source_url"]

    # Clean temporary helper columns and export
    df.drop(columns=["norm_project_name"], inplace=True, errors="ignore")
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n[+] Master pipeline finished successfully!")
    print(f"[+] Output written to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()