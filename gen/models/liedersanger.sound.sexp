; Liedersanger sound bank. Samples are cut and treated once by tools/sounds.py into
; out/liedersanger/sounds/<name>.wav; cues are read live by the viewer, which reloads on save.
;
; (sample name (file f) (cut start [end]) (fade in out) (gain g) (lowpass hz) (highpass hz)
;         (room amount) (loop))   cut/fade in seconds; room bakes a short tail into the clip
; (cue name (layer sample-or-(pick a b ...) (gain lo hi) (pitch lo hi) (delay lo hi)
;           (pan p) (spread s)) ...)
;   every trigger draws its own gain, pitch, delay and pick from the ranges; a layer pans
;   with its trigger unless it gives (pan p); spread adds random pan
; triggers live in the animation: (sound cue (pan p) (gain g)) on shots or (at secs),
; and (hum cue (by driver k) (pitch lo hi) (gain g)) for loops that follow a driver

(sounds liedersanger
  (dir "ref/sounds")

  (sample boom (file shot_50bmg.mp3) (cut 0.2 1.15) (fade 0.002 0.45) (room 0.12))
  (sample crack (file heavy_mg_50cal.mp3) (cut 0 0.11) (fade 0.001 0.03) (highpass 700))
  (sample thump (file thump_cannon.mp3) (cut 0 1.1) (fade 0.002 0.4) (lowpass 160))
  (sample clank (file clank1.mp3) (cut 0.09) (fade 0.002 0.05) (room 0.08))
  (sample cycle (file mechanical1.mp3) (cut 0.33) (fade 0.002 0.05) (room 0.08))
  (sample case-a (file casing_5.mp3) (cut 0.66) (fade 0.002 0.1) (room 0.15))
  (sample case-b (file casing_7.mp3) (fade 0.002 0.2) (room 0.15))
  (sample settle (file impact_heavy_4.mp3) (cut 0 1.6) (fade 0.002 0.4) (room 0.2))
  (sample whine (file gear_spin_loop.mp3) (loop))

  ; one round: the boom and crack of the barrel that fired, a thump for weight,
  ; then the feed clanks and the action cycles
  (cue shot
    (layer boom (gain 0.27 0.33) (pitch 0.96 1.04))
    (layer crack (gain 0.26 0.32) (pitch 0.86 0.94))
    (layer thump (gain 0.45) (pitch 0.95 1.05) (pan 0))
    (layer clank (gain 0.24 0.32) (pitch 0.92 1.08) (delay 0.04 0.05) (pan 0.1))
    (layer cycle (gain 0.1 0.14) (pitch 0.95 1.1) (delay 0.065 0.075) (pan 0.1)))

  ; the spent case lands a beat later, off to the side
  (cue case
    (layer (pick case-a case-b) (gain 0.1 0.2) (pitch 0.85 1.2) (delay 0.7 1.05) (pan 0.6) (spread 0.2)))

  (cue settle
    (layer settle (gain 0.5)))

  (cue whine
    (layer whine (gain 0.12))))
