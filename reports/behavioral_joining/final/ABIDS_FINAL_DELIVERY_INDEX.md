# ABIDS Final Delivery Index

**Demonstration run — purpose-built synthetic dataset. Not VDart's or any client's real historical data.**

Branch: `feature/behavioral-joining-intelligence`

---

## CLIENT FILES

| Filename | Repo Path | Purpose | Question It Answers |
|---|---|---|---|
| 01_ABIDS_Behavioral_Leakage_Map.pdf | `reports/behavioral_joining/final/client_reports/01_ABIDS_Behavioral_Leakage_Map.pdf` | Places behavioral evidence inside business leakage | Which behavioral patterns show up around where candidates disengage? |
| 02_ABIDS_Behavioral_Priority_Index.pdf | `reports/behavioral_joining/final/client_reports/02_ABIDS_Behavioral_Priority_Index.pdf` | Interim descriptive ranking of behavioral patterns (BPI score pending) | What should we pay attention to first? |
| 03_ABIDS_Behavioral_Uncertainty_Matrix.pdf | `reports/behavioral_joining/final/client_reports/03_ABIDS_Behavioral_Uncertainty_Matrix.pdf` | Shows what evidence does/doesn't support | How confident can we be in each finding? |
| 04_ABIDS_Candidate_Scenario_Matrix.pdf | `reports/behavioral_joining/final/client_reports/04_ABIDS_Candidate_Scenario_Matrix.pdf` | Translates mechanisms into recognizable recruiting situations | What does this look like in a real conversation? |
| 05_ABIDS_Behavioral_Journey_Map.pdf | `reports/behavioral_joining/final/client_reports/05_ABIDS_Behavioral_Journey_Map.pdf` | Shows where/when patterns emerge in the candidate journey | When should we intervene? |
| 06_ABIDS_Intervention_Intelligence_Matrix.pdf | `reports/behavioral_joining/final/client_reports/06_ABIDS_Intervention_Intelligence_Matrix.pdf` | Evidence-led recruiter questions/pilot ideas | What should we actually try doing differently? |
| ABIDS_Demonstration_Executive_Report.pdf | `reports/behavioral_joining/final/ABIDS_Demonstration_Executive_Report.pdf` | Full story in plain business English | Why does this matter and how does ABIDS work? |

## PRODUCT MANAGER FILES

| Filename | Repo Path | Purpose | Question It Answers |
|---|---|---|---|
| ABIDS_Product_Manager_Review.pdf | `reports/behavioral_joining/final/ABIDS_Product_Manager_Review.pdf` | Internal, plain-English breakdown + PASS/REVIEW/PENDING checklist | What actually happened in this run, stage by stage? |
| ABIDS_Full_Demonstration_Analysis.xlsx | `reports/behavioral_joining/final/ABIDS_Full_Demonstration_Analysis.xlsx` | 19-sheet master analytical workbook, every dataset in one file | Where do I go to inspect any specific number myself? |
| ABIDS_Hypothesis_and_Statistical_Results.pdf | `reports/behavioral_joining/final/ABIDS_Hypothesis_and_Statistical_Results.pdf` | Every tested hypothesis explained plainly, one section each | What was tested, how, and what did it mean? |

## DATA FILES

| Filename | Repo Path | Purpose |
|---|---|---|
| candidate_master.csv | `data/behavioral_joining/processed/final/candidate_master.csv` | All 2,500 applications, structured fields |
| behavioral_evidence.csv | `data/behavioral_joining/processed/final/behavioral_evidence.csv` | All 6,749 extracted evidence items |
| behavioral_mappings.csv | `data/behavioral_joining/processed/final/behavioral_mappings.csv` | Every evidence item mapped to a mechanism (or not), with `mapping_source` provenance |
| scenario_library.csv | `data/behavioral_joining/processed/final/scenario_library.csv` | 5,749 generated behavioral scenarios |
| application_behavior_mechanisms.csv | `data/behavioral_joining/processed/final/application_behavior_mechanisms.csv` | Clean application × mechanism bridge table |
| behavior_outcome_dataset.csv | `data/behavioral_joining/processed/final/behavior_outcome_dataset.csv` | Bridge joined to outcomes (discovery + hypothesis_generation only) |
| abids_hypotheses.csv | `data/behavioral_joining/processed/final/abids_hypotheses.csv` | All 14 formally proposed hypotheses |
| abids_statistical_results.csv | `data/behavioral_joining/processed/final/abids_statistical_results.csv` | All 11 actual test results |
| behavioral_leakage_map.csv | `data/behavioral_joining/processed/final/behavioral_leakage_map.csv` | Leakage Map report table |
| behavioral_priority_index.csv | `data/behavioral_joining/processed/final/behavioral_priority_index.csv` | BPI report table (priority_score = METHODOLOGY_PENDING) |
| behavioral_uncertainty_matrix.csv | `data/behavioral_joining/processed/final/behavioral_uncertainty_matrix.csv` | Uncertainty Matrix report table |
| candidate_scenario_matrix.csv | `data/behavioral_joining/processed/final/candidate_scenario_matrix.csv` | Scenario Matrix report table |
| behavioral_journey_map.csv | `data/behavioral_joining/processed/final/behavioral_journey_map.csv` | Journey Map report table |
| intervention_intelligence_matrix.csv | `data/behavioral_joining/processed/final/intervention_intelligence_matrix.csv` | Intervention Matrix report table |

## TECHNICAL / QA FILES

| Filename | Repo Path | Purpose | Question It Answers |
|---|---|---|---|
| ABIDS_QA_and_Methodology_Report.pdf | `reports/behavioral_joining/final/ABIDS_QA_and_Methodology_Report.pdf` | Test results, governance safeguard verification, methodology-pending list | Is this run scientifically and technically safe to rely on? |
| ABIDS_FINAL_DELIVERY_INDEX.md | `reports/behavioral_joining/final/ABIDS_FINAL_DELIVERY_INDEX.md` | This file | Where is everything? |
