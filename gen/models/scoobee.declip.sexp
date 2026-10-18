; knobs tools/declip.py may turn to stop parts passing through each other over the animation:
; (knob part axis min max) in degrees, written as rest rotations into the anim's declip block.
; (penalty k) charges k per degree squared for moving away from the authored pose.

(declip scoobee
  (penalty 0.003)
  (knob upper_arm_r x -20 20) (knob upper_arm_r z -12 12)
  (knob upper_arm_l x -20 20) (knob upper_arm_l z -12 12)
  (knob forearm_r x -25 25) (knob forearm_r z -15 15)
  (knob forearm_l x -25 25) (knob forearm_l z -15 15)
  (knob claw_r x -20 20)
  (knob rifle x -20 20) (knob rifle z -15 15)
  (knob pelvis x -8 8))
