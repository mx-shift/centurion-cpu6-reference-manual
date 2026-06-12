// Effective-address diagrams for the addressing-modes chapter (A5).
//
// Two builders:
//   ea-flow(stages, arrows)  — a horizontal chain of labelled boxes joined
//                              by labelled arrows, used to show how each
//                              memory-reference mode derives its operand.
//   idx-pipeline(steps)      — a vertical pipeline of always/optional stages,
//                              used for the indexed-mode EA computation.
//
// Both render through CeTZ. The look (muted accent highlight, gray role
// labels, mono bodies) tracks theme.typ.

#import "@preview/cetz:0.4.2"
#import "theme.typ": *

#let _hi-fill = accent.lighten(86%)
#let _box-stroke = luma(60)

// One stage of an ea-flow chain:
//   role:  small gray label above the box (e.g. "instruction", "memory")
//   addr:  small gray tag below the box (e.g. an address like "X+3"); none to omit
//   body:  box contents
//   hi:    true to flag this as the final operand (accent fill)
#let stage(body, role: none, addr: none, hi: false) = (
  role: role, addr: addr, body: body, hi: hi,
)

// Horizontal EA flow. `arrows` has one label per gap (stages.len() - 1).
#let ea-flow(stages, arrows) = {
  let W = 2.7      // box width
  let H = 0.78     // box height
  let GAP = 1.95   // centre-to-centre spacing beyond one box width
  let pitch = W + GAP
  align(center, cetz.canvas(length: 1cm, {
    import cetz.draw: *
    set-style(content: (padding: 0pt))
    for (i, s) in stages.enumerate() {
      let cx = i * pitch
      rect(
        (cx - W / 2, -H / 2), (cx + W / 2, H / 2),
        fill: if s.hi { _hi-fill } else { white },
        stroke: _box-stroke + (if s.hi { 1pt } else { 0.5pt }),
        radius: 0.05,
      )
      content((cx, 0), text(font: mono-font, size: 8pt)[#s.body])
      if s.role != none {
        content((cx, H / 2 + 0.28),
          text(font: heading-font, size: 6.5pt, fill: rule-gray)[#upper(s.role)])
      }
      if s.addr != none {
        content((cx, -H / 2 - 0.26),
          text(font: mono-font, size: 6.5pt, fill: rule-gray)[#s.addr])
      }
    }
    for (i, lbl) in arrows.enumerate() {
      let x0 = i * pitch + W / 2
      let x1 = (i + 1) * pitch - W / 2
      line((x0, 0), (x1, 0), mark: (end: ">", fill: _box-stroke, scale: 0.7),
           stroke: _box-stroke)
      content(((x0 + x1) / 2, 0.26),
        text(font: heading-font, size: 6.5pt, fill: rule-gray)[#lbl])
    }
  }))
}

// One step of the indexed-mode pipeline:
//   body:     the operation, e.g. `base ← base + disp`
//   gate:     none for an always-applied step, else the enabling bit/marker
//             text shown to the left (e.g. "disp = 1")
//   final:    true to flag the EA result (accent fill)
#let step-row(body, gate: none, final: false) = (
  body: body, gate: gate, final: final,
)

// Vertical indexed-mode pipeline.
#let idx-pipeline(steps) = {
  let W = 6.4
  let H = 0.62
  let VGAP = 0.5
  let pitch = H + VGAP
  align(center, cetz.canvas(length: 1cm, {
    import cetz.draw: *
    set-style(content: (padding: 0pt))
    for (i, st) in steps.enumerate() {
      let cy = -i * pitch
      let optional = st.gate != none
      rect(
        (-W / 2, cy - H / 2), (W / 2, cy + H / 2),
        fill: if st.final { _hi-fill } else { white },
        stroke: (
          paint: _box-stroke,
          thickness: if st.final { 1pt } else { 0.5pt },
          dash: if optional { "dashed" } else { none },
        ),
        radius: 0.05,
      )
      content((0, cy), text(font: mono-font, size: 8.5pt)[#st.body])
      if st.gate != none {
        content((-W / 2 - 0.25, cy),
          text(font: heading-font, size: 6.5pt, fill: rule-gray)[#st.gate],
          anchor: "east")
      }
      if i + 1 < steps.len() {
        line((0, cy - H / 2), (0, cy - H / 2 - VGAP),
             mark: (end: ">", fill: _box-stroke, scale: 0.7), stroke: _box-stroke)
      }
    }
  }))
}
