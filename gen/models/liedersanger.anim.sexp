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
; (shake | wave | glow parts motion (by rate|heat|idle k [ease]) (freq hz))
; eases: linear smooth expo-in expo-out expo-inout superexp back spring, or (mix a b w)

(anim liedersanger
  (length 8.0)

  ; nothing, then a double-exponential spin-up, a long burst, and a fast wind-down
  (rate
    (seg 1.1 2.7 0 26 superexp)
    (seg 2.7 5.4 26 26)
    (seg 5.4 6.5 26 0 expo-out))
  (heat (gain 0.022) (cool 1.7))

  ; flashes and spent cases stay hidden until something calls for them
  (rest upper_barrel_flash lower_barrel_flash (scale 0))
  (rest case.* (scale 0))

  ; the gunner braces before the burst and settles after it
  (kick root (at 0.55) (move 0.012 -0.01 0) (rot 0 0 1 1.2) (attack 0.5 expo-inout) (release 2.2 smooth))
  (kick root (at 6.45) (move -0.02 0.008 0) (rot 0 0 1 -1.6) (attack 0.09 expo-out) (release 1.2 spring 1.6 0.3))
  (kick drum (at 6.45) (rot 1 0 0 3.5) (attack 0.12 expo-out) (release 1.4 spring 1.3 0.18))

  ; the barrels take turns: even shots fire the top one
  (on-shot (every 2 0)
    (kick upper_barrel (move 0.1 0 0) (attack 0.007 expo-out) (release 0.3 spring 11 0.3) (vary 0.12))
    (kick upper_barrel_spring.* (move 0.1 0 0) (spread 1 0.05) (attack 0.007 expo-out) (release 0.3 spring 11 0.3))
    (kick upper_barrel_flash (scale 1.2) (attack 0.003 linear) (release 0.06 expo-in) (vary 0.45) (roll 1 0 0 180)))
  (on-shot (every 2 1)
    (kick lower_barrel (move 0.1 0 0) (attack 0.007 expo-out) (release 0.3 spring 11 0.3) (vary 0.12))
    (kick lower_barrel_spring.* (move 0.1 0 0) (spread 1 0.05) (attack 0.007 expo-out) (release 0.3 spring 11 0.3))
    (kick lower_barrel_flash (scale 1.2) (attack 0.003 linear) (release 0.06 expo-in) (vary 0.45) (roll 1 0 0 180)))

  ; every shot shoves the whole gun, indexes the feed and throws a case
  (on-shot
    (kick root (move 0.016 0 0) (rot 0 0 1 -0.45) (attack 0.01 expo-out) (release 0.2 spring 7 0.35) (vary 0.3))
    (kick cover (rot 0 0 1 -5) (attack 0.01 expo-out) (release 0.12 spring 18 0.4))
    (step gear (rot 0 0 1 -20) (over 0.045 (mix expo-out back 0.6)))
    (step drum_face (rot 0.866 0.5 0 -12) (over 0.06 back))
    (feed belt (over 0.042 (mix expo-out back 0.35)))
    ; the belt is yanked taut, then its weight swings it back out
    (kick belt_h1 (move 0.025 -0.02 -0.05) (attack 0.016 expo-out) (release 0.45 spring 3.6 0.22))
    (kick belt_h2 (move -0.01 -0.03 -0.06) (attack 0.012 expo-out) (release 0.4 spring 4.4 0.22))
    (kick drum (rot 1 0 0 0.5) (move 0 -0.005 0) (attack 0.02 expo-out) (release 0.6 spring 3 0.2) (vary 0.4))
    (kick lens (glow 3 0.5 0.25) (attack 0.002 linear) (release 0.08 expo-out))
    (throw case.* (vel 0.3 0.95 0.8) (jitter 0.15 0.25 0.25) (gravity -3.4) (spin 1100) (life 0.95)))

  ; sustained fire rattles everything; the drum and belt lag behind on their own weight
  (shake root (by rate 0.00035) (freq 31) (move 0.6 1 0.5) (rot 0 0 1 20))
  (shake drum (by rate 0.03) (freq 8) (rot 1 0 0 1.6))
  (shake belt_h1 belt_h2 (by rate 0.0018) (freq 6) (move 1 1 1.4))

  ; at rest it breathes
  (wave root (by idle 1) (freq 0.31) (rot 0 0 1 0.5))
  (wave root (by idle 1) (freq 0.2) (move 0 0.006 0.003))
  (wave belt_h1 belt_h2 (by idle 1) (freq 0.45) (move 0.004 0 0.01))
  (glow lens (by idle 1) (glow 0.5 0.05 0.03))

  ; heat soaks into the barrels and bleeds away slowly
  ; dull red first, then orange-yellow only when it is really cooking
  (glow upper_barrel lower_barrel (by heat 1.0 expo-in) (glow 1.0 0.05 0.0))
  (glow upper_barrel lower_barrel (by heat 0.9 superexp) (glow 0.7 0.3 0.04))
  (glow upper_barrel_spring.* lower_barrel_spring.* (by heat 0.9 expo-in) (glow 0.85 0.04 0.0)))
