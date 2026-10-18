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
    (kick upper_barrel_flash (scale 1.8) (attack 0.004 linear) (release 0.09 expo-in) (vary 0.35) (roll 1 0 0 180)))
  (on-shot (every 2 1)
    (kick lower_barrel (move 0.24 0 0) (attack 0.014 expo-out) (release 0.62 spring 5 0.32) (vary 0.1))
    (kick lower_barrel_spring.* (move 0.24 0 0) (spread 1 0.04) (attack 0.014 expo-out) (release 0.62 spring 5 0.32))
    (kick lower_barrel_flash (scale 1.8) (attack 0.004 linear) (release 0.09 expo-in) (vary 0.35) (roll 1 0 0 180)))

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
  (glow upper_barrel_spring.* lower_barrel_spring.* (by heat 0.9 expo-in) (glow 0.85 0.04 0.0)))
