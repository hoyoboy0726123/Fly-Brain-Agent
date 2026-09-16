# Test fixtures

`tiny_connectome.json` is a **SYNTHETIC** connectome used only to exercise the ingestion
pipeline (DATA.md §6). Every identifier, type, class and edge in it is invented. It contains
no biological data and must never be presented as connectome evidence. The file carries
`"synthetic": true`, and every normalized row produced from it carries `synthetic = true`.
