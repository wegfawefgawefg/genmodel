; Scoobee assembly: which part plugs into which socket, and the rest pose. The root stands
; so the feet meet the ground (y = 0). (mirror) builds the left part as a reflected copy.
;
; (part name (model m) (on parent socket) (mirror) (at x y z) (turn axis deg ...))
; turns are about the part's own joint; +x pitches forward/down for the body, a leg's -x
; swings it forward

(assembly scoobee
  ; hunched forward over its legs
  (part torso (at 0 3.8 0) (turn x 12))
  (part head (on torso neck) (turn x -8))
  (part pelvis (on torso waist) (turn x -12))

  ; knees well bent, feet flat
  (part thigh_r (model thigh) (on pelvis hip_r) (turn x -34 z 4))
  (part shin_r (model shin) (on thigh_r knee) (turn x 58))
  (part foot_r (model foot) (on shin_r ankle) (turn x -24))
  (part thigh_l (model thigh) (on pelvis hip_l) (mirror) (turn x -34 z -4))
  (part shin_l (model shin) (on thigh_l knee) (mirror) (turn x 58))
  (part foot_l (model foot) (on shin_l ankle) (mirror) (turn x -24))

  ; arms hanging forward, elbows bent, the rifle carried low
  (part upper_arm_r (model upper_arm) (on torso shoulder_r) (turn x -18 z 8))
  (part forearm_r (model forearm) (on upper_arm_r elbow) (turn x 35))
  (part claw_r (model claw) (on forearm_r wrist) (turn x -10))
  (part rifle (on claw_r grip) (turn x -32))
  (part upper_arm_l (model upper_arm) (on torso shoulder_l) (mirror) (turn x -10 z -8))
  (part forearm_l (model forearm) (on upper_arm_l elbow) (mirror) (turn x 45))
  (part claw_l (model claw) (on forearm_l wrist) (mirror) (turn x 15)))
