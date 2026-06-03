out := "centurion-cpu6-isa.pdf"

# Build the PDF
build:
    typst compile manual.typ {{out}}

# Live-rebuild on change
watch:
    typst watch manual.typ {{out}}

# Report documentation status totals from data/status.yaml
check:
    @grep -oE 'status: [a-z]+' data/status.yaml | sort | uniq -c
