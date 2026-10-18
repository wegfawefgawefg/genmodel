; Liedersanger sound bank. Samples are cut and treated once by tools/sounds.py into
; out/liedersanger/sounds/<name>.wav; cues are read live by the viewer, which reloads on save.
;
; (sample name (file f) (cut start [end]) (fade in out) (gain g) (lowpass hz) (highpass hz)
;         (room amount) (loop))   cut/fade in seconds; room bakes a short tail into the clip
; (sample name (synth whirr|sizzle|hiss) (length secs) ...)  made up instead of read from a file
; (cue name (layer sample-or-(pick a b ...) (gain lo hi) (pitch lo hi) (delay lo hi)
;           (pan p) (spread s)) ...)
;   every trigger draws its own gain, pitch, delay and pick from the ranges; a layer pans
;   with its trigger unless it gives (pan p); spread adds random pan
; triggers live in the animation: (sound cue (pan p) (gain g)) on shots or (at secs),
; and (hum cue (by driver k) (pitch lo hi) (gain g)) for loops that follow a driver

(sounds liedersanger
  (dir "ref/sounds")

  (sample boom (file shot_50bmg.mp3) (cut 0.2 1.15) (fade 0.002 0.45) (highpass 90) (room 0.12))
  (sample snap (file shot_50bmg.mp3) (cut 0.2 0.5) (fade 0.001 0.15) (highpass 2500))
  (sample crack (file heavy_mg_50cal.mp3) (cut 0 0.11) (fade 0.001 0.03) (highpass 1200))
  (sample thump (file thump_cannon.mp3) (cut 0 1.1) (fade 0.002 0.4) (lowpass 160))
  (sample clank (file clank1.mp3) (cut 0.09) (fade 0.002 0.05) (highpass 400) (room 0.08))
  (sample cycle (file mechanical1.mp3) (cut 0.33) (fade 0.002 0.05) (room 0.08))
  (sample case-a (file casing_5.mp3) (cut 0.66) (fade 0.002 0.1) (room 0.15))
  (sample case-b (file casing_7.mp3) (fade 0.002 0.2) (room 0.15))
  (sample whine (file gear_spin_loop.mp3) (loop))
  (sample whirr (synth whirr) (length 2) (loop))
  (sample sizzle (synth sizzle) (length 4) (loop))
  (sample hiss (synth hiss) (length 1.6) (fade 0.001 0.3))

  ; one round: the boom and crack of the barrel that fired, a thump for weight,
  ; then the feed clanks and the action cycles
  (cue shot
    (layer boom (gain 0.36 0.44) (pitch 0.96 1.04))
    (layer snap (gain 0.7 0.85) (pitch 0.95 1.08))
    (layer crack (gain 0.7 0.85) (pitch 0.86 0.94))
    (layer thump (gain 0.26) (pitch 0.95 1.05) (pan 0))
    (layer clank (gain 0.4 0.5) (pitch 0.95 1.15) (delay 0.04 0.05) (pan 0.1))
    (layer cycle (gain 0.1 0.14) (pitch 0.95 1.1) (delay 0.065 0.075) (pan 0.1)))

  ; the spent case lands a beat later, off to the side
  (cue case
    (layer (pick case-a case-b) (gain 0.1 0.2) (pitch 0.85 1.2) (delay 0.7 1.05) (pan 0.6) (spread 0.2)))

  ; after the burst: a soft low settle and the vent letting go
  (cue settle
    (layer thump (gain 0.22) (pitch 0.65) (pan 0))
    (layer hiss (gain 0.3) (delay 0.06 0.08) (pitch 0.95 1.05)))

  ; loops driven by the animation: gear whine with the fire rate, the motor's wind-up,
  ; and the hot barrels sizzling
  (cue whine
    (layer whine (gain 0.08)))
  (cue whirr
    (layer whirr (gain 0.11)))
  (cue sizzle
    (layer sizzle (gain 0.09))))
