; lofi: the crunch look for models built for it (liedersanger_lo). Geometry comes straight
; from the primitives as clean low polygons (no contouring, no decimation, no needles);
; texture as in crunch.sexp but realistic rather than toy-like: little speckle, full
; grime, streaky rust, and the model's own colours toned down.

(style lofi
  (mesher poly)         ; primitives emit clean polygons (chamfered boxes, prisms, lofts)
  (facets 8)
  (normals flat 50)     ; prism sides and chamfers shade soft, square edges stay hard
  (texture 256 nearest)
  (grain 0.1)
  (grain-tint 0.02)
  (rust-specks 0.003)
  (chips 0.06)
  (grime 1.0)           ; full soft grime and occlusion: weathering reads as stains, not dots
  (rust 0.7)            ; streaky rust patches at most of the model's own amount
  (cool-edges 0.15)
  ; realistic paint: dirtier teal, off-white, duller red
  (palette
    (teal 98 162 154)
    (white 198 198 192)
    (red 168 60 52)))
