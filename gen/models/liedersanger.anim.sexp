; Liedersanger firing loop. Units are the exported model's (about metres), angles in degrees,
; times in seconds. Edit while scripts/run.sh is open: the viewer reloads on save.
;
; (rate (seg t0 t1 from to ease)...)  shots per second; shots fall where its integral ticks over
; (on-shot (every n k) track...)      tracks fired by shots whose index % n == k
; (kick parts (move x y z) (rot ax ay az deg) (scale s) (glow r g b)
;       (attack secs ease) (release secs ease | release secs spring hz damping) (vary 0..1)
;       (roll ax ay az deg) (spread first last) (at secs))
; (step parts motion (over secs ease))  adds the motion once per shot, eased in
; (feed path (over secs ease))          moves the path's links on one pitch per shot
; (throw parts (vel x y z) (jitter x y z) (gravity g) (spin deg/s) (life secs))
; (shake | wave | glow | lean parts motion (by rate|heat|idle k [ease]) (freq hz))
;   lean holds motion * driver (muzzle climb that builds with the fire rate)
; (puff | spark part (from x y z) (count n) (launch forward random up) (drag k) (rise r)
;       (size start end grow-secs) (life secs) (color r g b alpha) (warm secs) (wind x y z))
;   on-shot bursts from a point carried by `part`; a spark's rise is gravity, it glows additively
; (wisp part (from x y z) (by heat k) (points n) (life secs) (rise speed accel) (curl amp hz)
;       (size start end grow-secs) (color r g b alpha) (wind x y z))
;   a smoke ribbon trailing off the point; each parcel keeps the meander of when it left
; (sound cue (pan p) (gain g) [(at secs)])  plays a cue from liedersanger.sound.sexp on shots
; (hum cue (by driver k) (pitch lo hi) (gain g))  a looping cue whose level and pitch follow
; drivers: rate (shots/s), heat, idle (1 when not firing), smoulder (heat * idle: hot, settled)
; eases: linear smooth expo-in expo-out expo-inout superexp back spring, or (mix a b w)

(anim liedersanger
  (length 9.0)

  ; a heavy gun: a slow double-exponential wind-up to 8 rounds a second, a long burst,
  ; and a wind-down where the last few shots come apart
  (rate
    (seg 1.2 2.6 0 8 superexp)
    (seg 2.6 6.0 8 8)
    (seg 6.0 7.0 8 0 expo-out))
  (heat (gain 0.07) (cool 1.9))

  ; flashes and spent cases stay hidden until something calls for them
  (rest upper_barrel_flash lower_barrel_flash (scale 0))
  (rest case.* (scale 0))

  ; the gunner braces before the burst and lets go after it
  (kick root (at 0.6) (move 0.02 -0.015 0) (rot 0 0 1 1.8) (attack 0.55 expo-inout) (release 2.6 smooth))
  (kick root (at 7.0) (move -0.03 0.012 0) (rot 0 0 1 -2.2) (attack 0.1 expo-out) (release 1.6 spring 1.3 0.3))
  (kick drum (at 7.0) (rot 1 0 0 5) (attack 0.14 expo-out) (release 1.8 spring 1.1 0.16))

  ; the barrels take turns: even shots fire the top one. Each slams back a long way
  ; and comes home on a soft spring, overshooting forward once.
  (on-shot (every 2 0)
    (kick upper_barrel (move 0.24 0 0) (attack 0.014 expo-out) (release 0.62 spring 5 0.32) (vary 0.1))
    (kick upper_barrel_spring.* (move 0.24 0 0) (spread 1 0.04) (attack 0.014 expo-out) (release 0.62 spring 5 0.32))
    (kick upper_barrel_flash (scale 1.35) (attack 0.004 linear) (release 0.1 expo-in) (vary 0.3) (roll 1 0 0 14)))
  (on-shot (every 2 1)
    (kick lower_barrel (move 0.24 0 0) (attack 0.014 expo-out) (release 0.62 spring 5 0.32) (vary 0.1))
    (kick lower_barrel_spring.* (move 0.24 0 0) (spread 1 0.04) (attack 0.014 expo-out) (release 0.62 spring 5 0.32))
    (kick lower_barrel_flash (scale 1.35) (attack 0.004 linear) (release 0.1 expo-in) (vary 0.3) (roll 1 0 0 14)))

  ; every shot throws the whole gun back and up, then it fights its way down again
  (on-shot
    (kick root (move 0.075 0.012 0) (rot 0 0 1 -3.2) (attack 0.02 expo-out) (release 0.6 spring 2.6 0.38) (vary 0.2))
    (kick root (rot 1 0 0 0.9) (attack 0.03 expo-out) (release 0.5 spring 3.3 0.3) (vary 0.9))
    (kick cover (rot 0 0 1 -10) (attack 0.012 expo-out) (release 0.2 spring 12 0.35))
    (step gear (rot 0 0 1 -20) (over 0.08 (mix expo-out back 0.7)))
    (step drum_face (rot 0.866 0.5 0 -12) (over 0.11 back))
    (feed belt (over 0.075 (mix expo-out back 0.45)))
    ; the belt is yanked taut, then its weight swings it back out
    (kick belt_h1 (move 0.05 -0.04 -0.1) (attack 0.025 expo-out) (release 0.9 spring 2.2 0.2))
    (kick belt_h2 (move -0.01 -0.02 -0.03) (attack 0.02 expo-out) (release 0.6 spring 3 0.25))
    (kick drum (rot 1 0 0 2.2) (move 0 -0.012 0) (attack 0.03 expo-out) (release 1.1 spring 2 0.17) (vary 0.35))
    (kick lens (glow 3 0.5 0.25) (attack 0.002 linear) (release 0.12 expo-out))
    (throw case.* (vel 0.5 1.35 1.05) (jitter 0.2 0.3 0.3) (gravity -4) (spin 900) (life 1.25)))

  ; sustained fire walks the muzzle up and rattles everything
  (lean root (by rate 0.11) (rot 0 0 1 -1) (move 0.002 0 0))
  (shake root (by rate 0.0006) (freq 17) (move 0.6 1 0.5) (rot 0 0 1 18))
  (shake drum (by rate 0.12) (freq 5) (rot 1 0 0 1.4))
  (shake belt_h1 belt_h2 (by rate 0.004) (freq 4) (move 1 1 1.4))

  ; at rest it breathes
  (wave root (by idle 1) (freq 0.31) (rot 0 0 1 0.5))
  (wave root (by idle 1) (freq 0.2) (move 0 0.006 0.003))
  (wave belt_h1 belt_h2 (by idle 1) (freq 0.45) (move 0.004 0 0.01))
  (glow lens (by idle 1) (glow 0.5 0.05 0.03))

  ; heat soaks into the barrels and bleeds away slowly:
  ; dull red first, then orange-yellow only when it is really cooking
  (glow upper_barrel lower_barrel (by heat 1.0 expo-in) (glow 1.0 0.05 0.0))
  (glow upper_barrel lower_barrel (by heat 0.9 superexp) (glow 0.7 0.3 0.04))
  (glow upper_barrel_spring.* lower_barrel_spring.* (by heat 0.9 expo-in) (glow 0.85 0.04 0.0))

  ; blast smoke and sparks from each muzzle brake
  (on-shot (every 2 0)
    ; the brake throws most of the gas out of both side ports, a little back
    (puff upper_barrel (from -1.78 0.2875 0.075) (dir 0.35 0 1) (count 6) (launch 2.2 0.3 0.04) (drag 5) (rise 0.12)
      (size 0.04 0.28 0.5) (life 2.2) (color 0.6 0.6 0.62 0.32) (warm 0.08) (wind 0.07 0 -0.03))
    (puff upper_barrel (from -1.78 0.2875 -0.125) (dir 0.35 0 -1) (count 6) (launch 2.2 0.3 0.04) (drag 5) (rise 0.12)
      (size 0.04 0.28 0.5) (life 2.2) (color 0.6 0.6 0.62 0.32) (warm 0.08) (wind 0.07 0 -0.03))
    (puff upper_barrel (from -2.0 0.2875 -0.025) (count 3) (launch 1.6 0.25 0.04) (drag 5) (rise 0.12)
      (size 0.03 0.2 0.5) (life 1.8) (color 0.6 0.6 0.62 0.26) (warm 0.06) (wind 0.07 0 -0.03))
    (spark upper_barrel (from -1.78 0.2875 0.075) (dir 0.3 0 1) (count 5) (launch 4 1.3 0.4) (drag 1.5) (rise -3.5)
      (size 0.013 0.01 0.2) (life 0.38) (color 1.5 0.62 0.18 1))
    (spark upper_barrel (from -1.78 0.2875 -0.125) (dir 0.3 0 -1) (count 5) (launch 4 1.3 0.4) (drag 1.5) (rise -3.5)
      (size 0.013 0.01 0.2) (life 0.38) (color 1.5 0.62 0.18 1)))
  (on-shot (every 2 1)
    ; the brake throws most of the gas out of both side ports, a little back
    (puff lower_barrel (from -2.03 -0.15 0.175) (dir 0.35 0 1) (count 6) (launch 2.2 0.3 0.04) (drag 5) (rise 0.12)
      (size 0.04 0.28 0.5) (life 2.2) (color 0.6 0.6 0.62 0.32) (warm 0.08) (wind 0.07 0 -0.03))
    (puff lower_barrel (from -2.03 -0.15 -0.025) (dir 0.35 0 -1) (count 6) (launch 2.2 0.3 0.04) (drag 5) (rise 0.12)
      (size 0.04 0.28 0.5) (life 2.2) (color 0.6 0.6 0.62 0.32) (warm 0.08) (wind 0.07 0 -0.03))
    (puff lower_barrel (from -2.25 -0.15 0.075) (count 3) (launch 1.6 0.25 0.04) (drag 5) (rise 0.12)
      (size 0.03 0.2 0.5) (life 1.8) (color 0.6 0.6 0.62 0.26) (warm 0.06) (wind 0.07 0 -0.03))
    (spark lower_barrel (from -2.03 -0.15 0.175) (dir 0.3 0 1) (count 5) (launch 4 1.3 0.4) (drag 1.5) (rise -3.5)
      (size 0.013 0.01 0.2) (life 0.38) (color 1.5 0.62 0.18 1))
    (spark lower_barrel (from -2.03 -0.15 -0.025) (dir 0.3 0 -1) (count 5) (launch 4 1.3 0.4) (drag 1.5) (rise -3.5)
      (size 0.013 0.01 0.2) (life 0.38) (color 1.5 0.62 0.18 1)))

  ; a breath of smoke out of the ejection port, and dust shaken off the drum
  (on-shot
    (puff root (from 1.34 0.29 0.25) (count 2) (launch 0 0.12 0.2) (drag 3) (rise 0.15)
      (size 0.03 0.16 0.5) (life 1.6) (color 0.66 0.66 0.68 0.22) (warm 0.02))
    (puff drum (from 1.05 -0.5 0.35) (count 3) (launch 0 0.3 0.15) (drag 2.5) (rise -0.5)
      (size 0.015 0.07 0.4) (life 1.1) (color 0.5 0.43 0.34 0.2) (warm 0)))

  ; cigarette smoke curling up off the hot muzzles once the gun settles (firing tears it apart):
  ; a thin bright core in a wider haze
  (wisp root (from -1.99 0.29 -0.025) (by smoulder 2.2) (points 96) (life 3.4) (rise 0.3 0.04)
    (curl 0.012 0.24) (wind 0.05 0 -0.02) (size 0.018 0.11 1.5) (color 0.84 0.86 0.9 0.8))
  (wisp root (from -1.99 0.29 -0.025) (by smoulder 2.2) (points 72) (life 3.0) (rise 0.26 0.04)
    (curl 0.022 0.17) (wind 0.06 0 -0.02) (size 0.03 0.26 1.2) (color 0.74 0.76 0.8 0.24))
  (wisp root (from -2.24 -0.15 0.075) (by smoulder 2.2) (points 96) (life 3.4) (rise 0.3 0.04)
    (curl 0.012 0.21) (wind 0.05 0 -0.02) (size 0.018 0.11 1.5) (color 0.84 0.86 0.9 0.8))
  (wisp root (from -2.24 -0.15 0.075) (by smoulder 2.2) (points 72) (life 3.0) (rise 0.26 0.04)
    (curl 0.022 0.15) (wind 0.06 0 -0.02) (size 0.03 0.26 1.2) (color 0.74 0.76 0.8 0.24))

  ; sound: every shot, panned toward the barrel that fired; cases land on their own cue;
  ; the motor whine climbs with the fire rate; the settle gets its own thud
  (on-shot (every 2 0) (sound shot (pan -0.3)))
  (on-shot (every 2 1) (sound shot (pan 0.3)))
  (on-shot (sound case))
  (sound settle (at 7.0))
  (hum whine (by rate 0.125) (pitch 0.55 1.3)))
