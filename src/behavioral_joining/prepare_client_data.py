"""prepare_client_data.py -- runs the data mart + BPI once, saves CSVs + a pickle
for PDF generation to reuse without recomputation."""
import sys
sys.path.insert(0, ".")
import pickle
import pandas as pd
from src.behavioral_joining.build_client_data_mart import build_all_and_save
from src.behavioral_joining.build_bpi_mvp import build_stage_priority, build_stage_scenario_behavior_priority

OUT_DATA = "reports/behavioral_joining/client_intelligence/data/"

tables, D = build_all_and_save(OUT_DATA)
bpi_stage = build_stage_priority(tables["stage_summary"])
bpi_detail = build_stage_scenario_behavior_priority(tables["stage_scenario_matrix"])
bpi_stage.to_csv(OUT_DATA + "stage_priority_bpi_mvp.csv", index=False)
bpi_detail.to_csv(OUT_DATA + "stage_scenario_behavior_priority_bpi_mvp.csv", index=False)

apps = D["apps"]
discovery_pop = apps[apps.research_split == "discovery"]
offer_pop = discovery_pop[discovery_pop.offer_accepted.astype(str) == "True"]
joined_rate = offer_pop.final_disposition.isin(["joined_on_time", "joined_late"]).mean()
n_with_behavior = tables["stage_behavior_scenario_map"].application_id.nunique()

apps_summary = {
    "Total Applications (Discovery)": len(discovery_pop),
    "Overall Joining Rate": f"{joined_rate:.0%}",
    "Overall Drop-off Rate": f"{1-joined_rate:.0%}",
    "Apps w/ Approved Behavioral Evidence": n_with_behavior,
}

with open("/tmp/client_intel_data.pkl", "wb") as f:
    pickle.dump({"tables": tables, "bpi_stage": bpi_stage, "bpi_detail": bpi_detail,
                 "apps_summary": apps_summary, "apps": apps, "discovery_pop": discovery_pop}, f)

print("saved. shapes:")
for k, v in tables.items():
    print(" ", k, v.shape)
print(" bpi_stage", bpi_stage.shape)
print(" bpi_detail", bpi_detail.shape)
print(apps_summary)
