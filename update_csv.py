import pandas as pd

df = pd.read_csv("enrichment-automated-script-output.csv")
for field in [
    "company_name_resolved",
    "company_country",
    "website",
    "linkedin",
    "contact_name",
    "contact_role",
    "contact_email",
    "source_url",
    "notes",
]:
    df[field] = df[field].astype("string")
df.to_csv("enrichment-automated-script-output-clean.csv", index=False)