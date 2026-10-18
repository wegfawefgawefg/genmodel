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

  ; the 50BMG recording holds two full reports (a faint click comes before each)
  (sample boom-a (file shot_50bmg.mp3) (cut 1.585 2.7) (fade 0.001 0.55) (highpass 60) (room 0.08))
  (sample boom-b (file shot_50bmg.mp3) (cut 8.745 9.86) (fade 0.001 0.55) (highpass 60) (room 0.08))
  (sample body (file gunshot_shawny4.mp3) (cut 0 0.45) (fade 0.001 0.2) (highpass 120))
  (sample snap (file sniper_rifle.mp3) (cut 0 0.25) (fade 0.001 0.1) (highpass 1500))
  (sample crack (file heavy_mg_50cal.mp3) (cut 0 0.11) (fade 0.001 0.03) (highpass 250))
  (sample thump (file thump_cannon.mp3) (cut 0 1.1) (fade 0.002 0.4) (lowpass 160))
  (sample clank (file clank1.mp3) (cut 0.09) (fade 0.002 0.05) (highpass 400) (room 0.08))
  (sample cycle (file mechanical1.mp3) (cut 0.33) (fade 0.002 0.05) (room 0.08))
  (sample case-a (file casing_5.mp3) (cut 0.66) (fade 0.002 0.1) (room 0.15))
  (sample case-b (file casing_7.mp3) (fade 0.002 0.2) (room 0.15))
  (sample whine (file gear_spin_loop.mp3) (loop))
  ; the motor and gear train: steady stretches of real machines, looped and pitched down
  (sample motor (file machine_startup.mp3) (cut 3.0 9.0) (loop))
  (sample gears (file gearbox.mp3) (cut 4.0 10.0) (loop))
  (sample sizzle (synth sizzle) (length 4) (loop))
  (sample hiss (synth hiss) (length 1.6) (fade 0.001 0.3))

  ; one round: the report is the gun (a 50BMG report, a rifle's body and snap, the MG's
  ; crack, a little thump); the feed's clank and the action sit well under it
  (cue shot
    (layer (pick boom-a boom-b) (gain 0.9 1.0) (pitch 0.94 1.02))
    (layer body (gain 0.3 0.38) (pitch 0.92 1.0))
    (layer snap (gain 0.22 0.28) (pitch 0.97 1.05))
    (layer crack (gain 0.25 0.3) (pitch 0.9 0.98))
    (layer thump (gain 0.18) (pitch 0.95 1.05) (pan 0))
    (layer clank (gain 0.1 0.14) (pitch 0.95 1.1) (delay 0.045 0.055) (pan 0.1))
    (layer cycle (gain 0.04 0.06) (pitch 0.95 1.1) (delay 0.07 0.08) (pan 0.1)))

  ; the spent case lands a beat later, off to the side
  (cue case
    (layer (pick case-a case-b) (gain 0.05 0.1) (pitch 0.85 1.2) (delay 0.7 1.05) (pan 0.6) (spread 0.2)))

  ; the vent letting go as the burst ends
  (cue settle
    (layer hiss (gain 0.3) (pitch 0.95 1.05)))

  ; loops driven by the animation: gear whine with the fire rate, the motor and gears
  ; winding up and down on the spin curve, and the hot barrels sizzling
  (cue whine
    (layer whine (gain 0.03)))
  (cue motor
    (layer motor (gain 0.2)))
  (cue gears
    (layer gears (gain 0.16)))
  (cue sizzle
    (layer sizzle (gain 0.09))))
