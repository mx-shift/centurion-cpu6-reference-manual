# centurion-isa

The **Centurion CPU6 Instruction Set Reference Manual** — documentation of
the Warrex Centurion CPU6 minicomputer architecture in the style of ARM's
Architecture Reference Manuals, written in [Typst](https://typst.app).

Built on the Centurion community's reverse-engineering work: the
[Nakazoto CenturionComputer wiki](https://github.com/Nakazoto/CenturionComputer/wiki)
and [Meisaka's webCenREE emulator](https://github.com/Meisaka/webCenREE).
See [NOTICE](NOTICE).

## Building

Requires `typst` (>= 0.12) and optionally `just`:

```
just build        # or: typst compile manual.typ centurion-cpu6-isa.pdf
just watch        # live preview
just check        # documentation status totals
```

Fonts: Noto Serif, Noto Sans, Source Code Pro.

The ISA manual's addressing-mode diagrams use the
[CeTZ](https://typst.app/universe/package/cetz) package. Typst downloads
and caches it automatically on the first build, so an online build needs
no manual step; for a fully offline build, pre-populate the Typst
package cache.

## License

CC-BY-4.0 (see [LICENSE](LICENSE)). Reproduced/derived material retains
its own terms as enumerated in [NOTICE](NOTICE).
