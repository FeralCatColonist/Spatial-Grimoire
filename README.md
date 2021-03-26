# Spatial-Grimoire
This is a spellbook for spatial things.

## ArcPy_IngestREST.py
This is used to download features from a REST service; fully operational but a work-in-progress
- uses the Requests library for grabbing data as JSON files
- uses timers to prevent stressing/triggering flare blocks
- batches features as json, creates feature classes, reduces to one feature class
