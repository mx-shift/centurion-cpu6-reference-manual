out := "centurion-cpu6-isa.pdf"

# Build the manual
build:
    typst compile manual.typ {{out}}

# Live-rebuild the manual on change
watch:
    typst watch manual.typ {{out}}

# Report documentation status totals from data/status.yaml
check:
    @grep -oE 'status: [a-z]+' data/status.yaml | sort | uniq -c
