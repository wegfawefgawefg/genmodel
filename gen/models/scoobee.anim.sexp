; Scoobee locomotion: stands, walks off, picks up to a jog, eases back to a walk and stops.
; The gait plants each foot on the ground (the grid slides back at the mech's speed) and
; reaches it with two-bone IK; the body and arms follow the step timing.
;
; (gait (body part)
;       (leg thigh shin foot (phase p) (toe m) (heel m))  toe/heel: ahead of/behind the ankle
;       (arm upper_arm forearm (phase p))                 swings with the leg of that phase
;       (speed (seg t0 t1 from to)...)                    m/s, smoothed
;       (walk style) (jog style))                         blended by speed between the two
; style: (speed v) (cadence cycles/s) (duty stance share) (lift m) (bob m) (sway m) (lean deg)
;        (crouch m) (arms deg) (elbows deg) (toe-off deg) (strike deg) (twist deg) (impact m)
;        (flex deg) (shove m/s2) (reach m) (invert deg) (give deg)
; (leg thigh shin foot [toes] [spur] ...): toes stay planted as the heel rolls; the spur folds
; under load like a sprung damper
; walk/jog/sprint are styles at their speeds; the gait blends between the two nearest. A walk
; has duty > 0.5 (both feet down at times) and bob > 0 (the body rides high over the stance
; leg); runs have duty < 0.5 (a flight phase) and bob < 0 (the body dips into each step).
; impact and flex are the feet working as dampers: the body sinks into each footfall and the
; toes spring up off it, both critically damped.
; the body is a mass moved by the stance feet's ground forces: vertical pushes carry its weight
; (one hump per stance when running, two when walking) and fling it into flight; shove brakes
; it as a foot lands ahead and drives it on as the foot pushes off behind. bob adds on top.
; reach throws the swing foot out past its landing spot before it pulls back to strike;
; invert rolls it in to meet the ground.
; (hips part) turns with the stride against the body; (head part) holds its gaze steady;
; (spring hz damping) is how the body lags its targets

(anim scoobee
  (length 26.0)

  (gait
    (body torso)
    (hips pelvis)
    (head head)
    (spring 1.7 0.55)
    (leg thigh_r shin_r foot_r toes_r spur_r (phase 0) (heel 0.3))
    (leg thigh_l shin_l foot_l toes_l spur_l (phase 0.5) (heel 0.3))
    (arm upper_arm_r forearm_r (phase 0.5))
    (arm upper_arm_l forearm_l (phase 0))
    ; stand, walk off, jog, open up into a sprint, wind back down and stop
    (speed
      (seg 1.0 3.0 0 1.8)
      (seg 3.0 6.0 1.8 1.8)
      (seg 6.0 7.5 1.8 4.2)
      (seg 7.5 10.5 4.2 4.2)
      (seg 10.5 12.0 4.2 8.0)
      (seg 12.0 15.5 8.0 8.0)
      (seg 15.5 17.5 8.0 4.2)
      (seg 17.5 19.0 4.2 4.2)
      (seg 19.0 20.5 4.2 1.8)
      (seg 20.5 22.5 1.8 1.8)
      (seg 22.5 24.5 1.8 0))
    (walk (speed 1.8) (cadence 0.56) (duty 0.62) (lift 0.3) (bob 0.02) (sway 0.08) (lean 2)
          (crouch 0) (arms 5) (elbows 0) (toe-off 22) (strike 10) (twist 9) (impact 0.04) (flex 10) (shove 1.0) (reach 0.05) (invert 2))
    (jog (speed 4.2) (cadence 0.86) (duty 0.4) (lift 0.55) (bob 0.0) (sway 0.04) (lean 5)
         (crouch 0.2) (arms 14) (elbows -12) (toe-off 30) (strike 6) (twist 12) (impact 0.07) (flex 14) (shove 3.0) (reach 0.3) (invert 5))
    (sprint (speed 8.0) (cadence 1.15) (duty 0.28) (lift 0.7) (bob 0.0) (sway 0.02) (lean 9)
            (crouch 0.22) (arms 22) (elbows -18) (toe-off 38) (strike 2) (twist 15) (impact 0.1) (flex 18) (shove 6.0) (reach 0.6) (invert 9)))

  ; and glances about now and then
  (wave head (rot 0 1 0 8) (freq 0.11))

  ; the cup flaps over the intakes snap open as it gets moving and ease shut as it slows,
  ; fluttering in the airflow while they're open
  (lean flap_r (by throttle 1 smooth) (rot 0 1 0 -24))
  (lean flap_l (by throttle 1 smooth) (rot 0 1 0 24))
  (shake flap_r flap_l (by throttle 1) (freq 8) (rot 0 1 0 2.5))
  (lean shin_flap_r (by throttle 1 smooth) (rot 0 0 1 18))
  (lean shin_flap_l (by throttle 1 smooth) (rot 0 0 1 -18))
  (shake shin_flap_r shin_flap_l (by throttle 1) (freq 9) (rot 0 0 1 2))

  ; the engine breathes out of its stacks all the time, more when it works
  (wisp torso (from 0.24 5.1 -1.365) (by one) (points 56) (life 2.6) (rise 0.35 0.05) (curl 0.03 0.25)
    (wind 0 0.05 -0.5) (size 0.08 0.8 1.0) (color 0.32 0.31 0.3 0.3))
  (wisp torso (from -0.24 5.02 -1.35) (by one) (points 56) (life 2.4) (rise 0.32 0.05) (curl 0.03 0.22)
    (wind 0 0.05 -0.5) (size 0.08 0.75 1.0) (color 0.3 0.29 0.28 0.28))

  ; round tail lamps that leave a glow behind them as the body moves
  (lamp torso (from 0.18 4.522 -1.64) (by one) (color 1.8 0.16 0.08) (size 0.13) (count 10) (life 0.14))
  (lamp torso (from -0.18 4.522 -1.64) (by one) (color 1.8 0.16 0.08) (size 0.13) (count 10) (life 0.14)))
