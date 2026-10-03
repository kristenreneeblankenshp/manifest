# RCC-004 MASR Registry & Candidate Pipeline Console

Design canvas source for the RCC-004 console, built from
`Manifest_Workbench_CISC-001_MOPS-003_RCC-004_MASR_Registry_Candidate_Pipeline_v0_4.xlsx`.

- `Main.dc.html` — the console artboard (1440×1920), interactive
- `canvas.json` — canvas index (frame, title, launch settings)

Live canvas: https://claude.ai/artifact/BwyJESNBUJPhuHYkREcFXe

The artboard loads `./support.js` from the Design canvas runtime, so it renders
inside the canvas, not as a standalone page. Data is a snapshot of the workbook
(47 certified holdings, 9 research candidates, 10 pipeline records); stage-gate
logic mirrors the workbook's `24 RCC-004 Candidate Pipeline` column Z formula.
