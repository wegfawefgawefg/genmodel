; Scoobee assembly: which part plugs into which socket, and the rest pose. The root stands
; so the feet meet the ground (y = 0). (mirror) builds the left part as a reflected copy.
;
; (part name (model m) (on parent socket) (mirror) (at x y z) (turn axis deg ...))
; (ram name (from part x y z) (to part x y z) (r radius))  a sliding ram across a joint
; turns are about the part's own joint; +x pitches forward/down for the body, a leg's -x
; swings it forward

(assembly scoobee
  ; hunched forward over its legs
  (part torso (at 0 3.9 0) (turn x 4))
  (part head (on torso neck) (turn x 0))
  (part pelvis (on torso waist) (turn x -4))

  ; knees well bent, feet flat
  (part thigh_r (model thigh) (on pelvis hip_r) (turn x -34 z 4))
  (part shin_r (model shin) (on thigh_r knee) (turn x 58))
  (part foot_r (model foot) (on shin_r ankle) (turn x -24))
  (part toes_r (model toes) (on foot_r ball))
  (part thigh_l (model thigh) (on pelvis hip_l) (mirror) (turn x -34 z -4))
  (part shin_l (model shin) (on thigh_l knee) (mirror) (turn x 58))
  (part foot_l (model foot) (on shin_l ankle) (mirror) (turn x -24))
  (part toes_l (model toes) (on foot_l ball) (mirror))

  ; arms hanging forward, elbows bent, the rifle carried low
  (part upper_arm_r (model upper_arm) (on torso shoulder_r) (turn x -14 z 28))
  (part forearm_r (model forearm) (on upper_arm_r elbow) (turn x 18 z -16))
  (part claw_r (model claw) (on forearm_r wrist) (turn x -10))
  (part rifle (on claw_r grip) (turn x -32))
  (part upper_arm_l (model upper_arm) (on torso shoulder_l) (mirror) (turn x -8 z -28))
  (part forearm_l (model forearm) (on upper_arm_l elbow) (mirror) (turn x 28 z 16))
  (part claw_l (model claw) (on forearm_l wrist) (mirror) (turn x 15))

  ; working rams across the joints: the cylinder rides one part, the rod the next, and the
  ; rod slides as the joint turns. Points are in each part's own frame.
  ; knee extensors on the outer front of each thigh, driving horns ahead of the knee axis
  (ram knee_ram_r (from thigh_r 0.33 -0.24 0.16) (to shin_r 0.35 -0.2 0.27) (r 0.05))
  (ram knee_ram_l (from thigh_l -0.33 -0.24 0.16) (to shin_l -0.35 -0.2 0.27) (r 0.05))
  ; calf rams pulling on heel levers behind the ankles
  (ram ankle_ram_r (from shin_r 0 -0.6 -0.47) (to foot_r 0 -0.18 -0.33) (r 0.045))
  (ram ankle_ram_l (from shin_l 0 -0.6 -0.47) (to foot_l 0 -0.18 -0.33) (r 0.045))
  ; biceps from the upper arm front to a pin on the forearm by the elbow
  (ram elbow_ram_r (from upper_arm_r 0 -0.22 0.19) (to forearm_r 0 -0.22 0.2) (r 0.035))
  (ram elbow_ram_l (from upper_arm_l 0 -0.22 0.19) (to forearm_l 0 -0.22 0.2) (r 0.035)))
