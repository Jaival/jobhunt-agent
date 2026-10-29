---
name: remap-cv
description: Map the candidate's master CV and cover letter again (cv/layout.yaml) so the builder can tailor them. Use when the user says "remap my CV", after they changed their master CV or letter, or when setup_check.py or the builder warns that the CV map doesn't match.
---
Follow "Map the CV" in engine/ONBOARDING.md round 5 (the format is at the top of engine/tools/cv_map.py), then run
`python engine/tools/cv_map.py check` and `python engine/tools/setup_check.py` until the map check is ok. This
replaces the daily routine for this conversation. Never edit the master CV or letter themselves.
