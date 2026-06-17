# staged.csv — data source & attribution

`staged.csv` is the **real** UCI #316 dataset, pre-staged so the demo runs offline (objective #4).

- **Dataset:** Condition Based Maintenance of Naval Propulsion Plants (UCI ML Repository, id=316)
- **What:** real frigate gas-turbine (CODLAG) decay data — 11,934 instances, 16 features + 2 decay-coefficient targets. We predict `gt_compressor_decay`.
- **License:** CC BY 4.0 (redistribution permitted with attribution).
- **Source:** https://archive.ics.uci.edu/dataset/316/condition+based+maintenance+of+naval+propulsion+plants
- **Citation:** Coraddu, Oneto, Ghio, Savio, Anguita, Figari — "Machine Learning Approaches for Improving Condition-Based Maintenance of Naval Propulsion Plants," J. Engineering for the Maritime Environment, 2016.

Column names in `staged.csv` are our own short labels for the 18 space-separated columns of the original `data.txt`. To re-fetch: `python3 demo/stage_data.py` (or pull the zip from the source URL).
