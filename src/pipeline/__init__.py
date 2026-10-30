"""
Scheduled refresh pipeline for the mental health clinical trials project.

The same download, cleaning and grouping steps as 01_trials_pipeline.ipynb
(parts B and C), written as plain Python with no third-party packages so it
runs on AWS Lambda without layers. The notebook stays the record of the
published analysis (download of 1 October 2026); this package produces the
refreshed snapshots.
"""
