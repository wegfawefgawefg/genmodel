; lofi: the crunch look for models built for it (liedersanger_lo). Geometry comes straight
; from the primitives as clean low polygons (no contouring, no decimation, no needles);
; texture settings as in crunch.sexp. Palette omitted: the model keeps its own colours.

(style lofi
  (mesher poly)         ; primitives emit clean polygons (chamfered boxes, prisms, lofts)
  (facets 8)
  (normals flat 50)     ; prism sides and chamfers shade soft, square edges stay hard
  (texture 256 nearest)
  (grain 0.26)
  (grain-tint 0.04)
  (rust-specks 0.022)
  (chips 0.3)
  (grime 0.5)
  (cool-edges 0.35))
