; crunch: chunky late-90s console look (ref/style_crunch.png). Built with
;   python gen/build.py liedersanger --style crunch   ->  out/liedersanger-crunch/
;
; (facets n)        round primitives become n-sided prisms
; (tris k)          scales every piece's triangle budget (small parts keep at least 28)
; (voxel k)         scales contouring voxels (coarser picks up less detail)
; (normals flat d)  hard shading: faces bending more than d degrees split
; (texture px nearest|linear)
; (grain k)         per-texel brightness noise; (grain-tint k) adds a little colour to it
; (rust-specks k)   share of texels that turn rust orange, more on edges and in creases
; (chips k)         white chips on convex edges
; (grime k)         scales the soft grime and occlusion
; (rust k)          scales the model's rust patches (default 0.12 in a style)
; (cool-edges k)    blue-white sheen on upward-facing bevels
; (palette (material r g b) ...)  repaints materials by name

(style crunch
  (facets 8)
  (tris 0.32)
  (voxel 1.25)
  (normals flat 22)
  (texture 256 nearest)
  (grain 0.3)
  (grain-tint 0.04)
  (rust-specks 0.025)
  (chips 0.3)
  (grime 0.45)
  (cool-edges 0.35)
  (palette
    (teal 118 120 124)
    (white 164 164 160)
    (red 150 74 66)
    (gunmetal 112 112 116)
    (brass 150 148 116)
    (black 150 76 68)
    (steel 150 150 154)
    (rubber 52 52 54)))
