; Scoobee assembly: which part plugs into which socket. The root stands so the feet meet
; the ground (y = 0). (mirror) builds the left part as a reflected copy of the right one.
;
; (part name (model m) (on parent socket) (mirror) (at x y z))

(assembly scoobee
  (part torso (at 0 3.02 0))
  (part head (on torso neck))
  (part pelvis (on torso waist))

  (part thigh_r (model thigh) (on pelvis hip_r))
  (part shin_r (model shin) (on thigh_r knee))
  (part foot_r (model foot) (on shin_r ankle))
  (part thigh_l (model thigh) (on pelvis hip_l) (mirror))
  (part shin_l (model shin) (on thigh_l knee) (mirror))
  (part foot_l (model foot) (on shin_l ankle) (mirror))

  (part upper_arm_r (model upper_arm) (on torso shoulder_r))
  (part forearm_r (model forearm) (on upper_arm_r elbow))
  (part claw_r (model claw) (on forearm_r wrist))
  (part rifle (on claw_r grip))
  (part upper_arm_l (model upper_arm) (on torso shoulder_l) (mirror))
  (part forearm_l (model forearm) (on upper_arm_l elbow) (mirror))
  (part claw_l (model claw) (on forearm_l wrist) (mirror)))
