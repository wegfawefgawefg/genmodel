; Scoobee joint test (not a real animation yet): every joint swings through a range so you
; can see the parts stay joined. Hinges turn about their socket's x axis.

(anim scoobee
  (length 6.0)

  ; knees bend back 0..60 degrees, hips swing to follow, feet keep level-ish
  (lean shin_r shin_l (rot 1 0 0 30))
  (wave shin_r (rot 1 0 0 30) (freq 0.33))
  (wave shin_l (rot 1 0 0 -30) (freq 0.33))
  (wave thigh_r (rot 1 0 0 -20) (freq 0.33))
  (wave thigh_l (rot 1 0 0 20) (freq 0.33))
  (lean foot_r foot_l (rot 1 0 0 -20))

  ; arms: shoulders swing, elbows and wrists flex
  (wave upper_arm_r (rot 1 0 0 25) (freq 0.25))
  (wave upper_arm_l (rot 1 0 0 -25) (freq 0.25))
  (wave forearm_r forearm_l (rot 1 0 0 20) (freq 0.5))
  (wave claw_r claw_l (rot 1 0 0 25) (freq 0.7))

  ; head looks about, the body sways on the waist
  (wave head (rot 0 1 0 30) (freq 0.17))
  (wave pelvis (rot 0 1 0 6) (freq 0.17)))
